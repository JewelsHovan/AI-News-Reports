"""Agent definitions and orchestration for AI news analysis."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from ai_news.analysis.prompts import (
    COMMUNITY_EXPLORER_PROMPT,
    EXPERT_EXPLORER_PROMPT,
    IMPLICATIONS_SYNTHESIZER_PROMPT,
    INDUSTRY_EXPLORER_PROMPT,
    ORCHESTRATOR_PROMPT,
    REPORT_TEMPLATE,
    RESEARCH_EXPLORER_PROMPT,
    STORY_SYNTHESIZER_PROMPT,
    TREND_SYNTHESIZER_PROMPT,
)
from ai_news.analysis.tools import create_news_tools
from ai_news.fetchers.base import FetchResult

logger = logging.getLogger(__name__)


def _build_fetch_data_dict(results: dict[str, FetchResult]) -> dict[str, Any]:
    """Convert FetchResult dict to serialisable dict for tools.

    Only includes sources that fetched successfully.
    """
    return {
        source: result.to_dict()
        for source, result in results.items()
        if result.success
    }


class AgentError(Exception):
    """Raised when an agent query fails."""

    def __init__(self, message: str, session_id: str | None = None, partial_text: str = ""):
        super().__init__(message)
        self.session_id = session_id
        self.partial_text = partial_text


# Default timeout for individual agent queries (20 minutes).
_DEFAULT_AGENT_TIMEOUT = 20 * 60


async def _run_single_query(
    prompt: str,
    options: ClaudeAgentOptions,
    *,
    timeout: float = _DEFAULT_AGENT_TIMEOUT,
) -> str:
    """Run a single agent query and extract the text response.

    Prefers the ``ResultMessage.result`` field when available, falling back
    to accumulating ``TextBlock`` content from ``AssistantMessage`` chunks.

    Raises:
        AgentError: If the agent ends with ``is_error`` or the SDK raises.
        asyncio.TimeoutError: If the query exceeds *timeout* seconds.
    """

    async def _inner() -> str:
        text_parts: list[str] = []
        final_result: str | None = None
        session_id: str | None = None
        had_error = False
        error_detail: str | None = None

        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    session_id = getattr(message, "session_id", None)
                    if message.result:
                        final_result = message.result
                    if message.is_error:
                        had_error = True
                        error_detail = message.result or "unknown error"
                        logger.error(
                            "Agent query ended with error (session %s): %s",
                            session_id,
                            error_detail,
                        )
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            text_parts.append(block.text)
        except Exception as exc:
            partial = "\n".join(text_parts)
            logger.error(
                "Agent SDK raised %s: %s (collected %d chars before failure)",
                type(exc).__name__,
                exc,
                len(partial),
            )
            raise AgentError(
                f"Agent SDK error: {exc}",
                session_id=session_id,
                partial_text=partial,
            ) from exc

        if had_error:
            partial = "\n".join(text_parts)
            raise AgentError(
                f"Agent returned error: {error_detail}",
                session_id=session_id,
                partial_text=partial,
            )

        # Return whichever is longer.  The ResultMessage.result is sometimes a
        # brief summary (e.g. "The report has been generated above") while the
        # actual content lives in the accumulated TextBlock stream.  Using the
        # longer of the two ensures we don't discard a full report in favour of
        # a one-paragraph recap.
        text = "\n".join(text_parts)
        if final_result is not None and len(final_result) >= len(text):
            return final_result
        if text:
            return text
        return final_result or ""

    return await asyncio.wait_for(_inner(), timeout=timeout)


# ---------------------------------------------------------------------------
# Phase 1: Exploration -- 4 domain-specific subagents in parallel
# ---------------------------------------------------------------------------

_MAX_RETRIES = 2
_RETRY_DELAY_BASE = 10  # seconds; doubles each retry


async def _run_with_retry(
    name: str,
    prompt: str,
    options: ClaudeAgentOptions,
    *,
    max_retries: int = _MAX_RETRIES,
    timeout: float = _DEFAULT_AGENT_TIMEOUT,
) -> tuple[str, str]:
    """Run an agent query with retries and exponential backoff.

    Returns:
        (name, result_text) on success.

    Raises:
        AgentError: If all retries are exhausted.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, max_retries + 2):  # +2 because range is exclusive and attempt 1 is the initial try
        try:
            result = await _run_single_query(prompt, options, timeout=timeout)
            if attempt > 1:
                logger.info("Agent '%s' succeeded on retry %d", name, attempt - 1)
            return name, result
        except (AgentError, asyncio.TimeoutError) as exc:
            last_exc = exc
            if isinstance(exc, asyncio.TimeoutError):
                logger.warning(
                    "Agent '%s' timed out after %ds (attempt %d/%d)",
                    name, timeout, attempt, max_retries + 1,
                )
            else:
                logger.warning(
                    "Agent '%s' failed (attempt %d/%d): %s",
                    name, attempt, max_retries + 1, exc,
                )
            if attempt <= max_retries:
                delay = _RETRY_DELAY_BASE * (2 ** (attempt - 1))
                logger.info("Retrying agent '%s' in %ds...", name, delay)
                await asyncio.sleep(delay)

    raise AgentError(
        f"Agent '{name}' failed after {max_retries + 1} attempts: {last_exc}",
        partial_text=getattr(last_exc, "partial_text", ""),
    )


async def run_exploration(
    fetch_results: dict[str, FetchResult],
    max_budget_usd: float = 2.0,
    *,
    min_success: int = 2,
) -> dict[str, str]:
    """Run 4 exploration subagents in parallel.

    Each explorer receives only the data relevant to its domain so it can
    focus its analysis.  All explorers run concurrently.  Failed agents
    are retried up to ``_MAX_RETRIES`` times with exponential backoff.

    Args:
        fetch_results: Raw fetch results keyed by source name.
        max_budget_usd: Total budget across all explorers.
        min_success: Minimum number of explorers that must succeed.
            Raises ``RuntimeError`` if fewer succeed.

    Returns:
        Dict mapping explorer name to its analysis text.
    """
    fetch_data = _build_fetch_data_dict(fetch_results)

    # Partition data by domain so each explorer gets a focused slice.
    community_data = json.dumps({
        "reddit": fetch_data.get("reddit", {}),
    }, indent=2)

    research_data = json.dumps({
        "huggingface": fetch_data.get("huggingface", {}),
    }, indent=2)

    industry_data = json.dumps({
        "techcrunch": fetch_data.get("techcrunch", {}),
        "ai-news": fetch_data.get("ai-news", {}),
    }, indent=2)

    expert_data = json.dumps({
        "the_batch": fetch_data.get("the_batch", {}),
        "simonwillison": fetch_data.get("simonwillison", {}),
        "smol.ai": fetch_data.get("smol.ai", {}),
    }, indent=2)

    explorer_configs = [
        ("community", COMMUNITY_EXPLORER_PROMPT, community_data),
        ("research", RESEARCH_EXPLORER_PROMPT, research_data),
        ("industry", INDUSTRY_EXPLORER_PROMPT, industry_data),
        ("expert", EXPERT_EXPLORER_PROMPT, expert_data),
    ]

    per_agent_budget = max_budget_usd / len(explorer_configs)

    async def _run_explorer(name: str, prompt: str, data: str) -> tuple[str, str]:
        full_prompt = f"{prompt}\n\nINPUT DATA:\n{data}"
        options = ClaudeAgentOptions(
            model="claude-sonnet-4-5",
            max_turns=3,
            max_budget_usd=per_agent_budget,
            permission_mode="bypassPermissions",
        )
        logger.info("Starting exploration agent: %s", name)
        name, result = await _run_with_retry(name, full_prompt, options)
        logger.info("Exploration agent finished: %s (%d chars)", name, len(result))
        return name, result

    tasks = [
        _run_explorer(name, prompt, data)
        for name, prompt, data in explorer_configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    exploration: dict[str, str] = {}
    failed: list[str] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Explorer failed after retries: %s", result)
            failed.append(str(result))
            continue
        name, text = result  # type: ignore[misc]
        exploration[name] = text

    if len(exploration) < min_success:
        raise RuntimeError(
            f"Exploration failed: only {len(exploration)}/{len(explorer_configs)} "
            f"agents succeeded (minimum {min_success} required). "
            f"Failures: {failed}"
        )

    if failed:
        logger.warning(
            "Exploration partially succeeded: %d/%d agents OK (failed: %s)",
            len(exploration), len(explorer_configs), ", ".join(failed),
        )

    return exploration


# ---------------------------------------------------------------------------
# Phase 2: Consolidation -- 3 synthesis subagents in parallel
# ---------------------------------------------------------------------------

async def run_consolidation(
    exploration_results: dict[str, str],
    max_budget_usd: float = 2.0,
    *,
    min_success: int = 2,
) -> dict[str, str]:
    """Run 3 consolidation subagents in parallel.

    Each synthesizer receives all exploration outputs and focuses on a
    different aspect: top stories, major trends, or actionable implications.
    Failed agents are retried up to ``_MAX_RETRIES`` times.

    Args:
        exploration_results: Output from :func:`run_exploration`.
        max_budget_usd: Total budget across all synthesizers.
        min_success: Minimum number of synthesizers that must succeed.
            Raises ``RuntimeError`` if fewer succeed.

    Returns:
        Dict mapping synthesizer name to its synthesis text.
    """
    all_explorations = json.dumps(exploration_results, indent=2)

    synthesizer_configs = [
        ("stories", STORY_SYNTHESIZER_PROMPT),
        ("trends", TREND_SYNTHESIZER_PROMPT),
        ("implications", IMPLICATIONS_SYNTHESIZER_PROMPT),
    ]

    per_agent_budget = max_budget_usd / len(synthesizer_configs)

    async def _run_synthesizer(name: str, prompt: str) -> tuple[str, str]:
        full_prompt = f"{prompt}\n\nEXPLORATION OUTPUTS:\n{all_explorations}"
        options = ClaudeAgentOptions(
            model="claude-sonnet-4-5",
            max_turns=3,
            max_budget_usd=per_agent_budget,
            permission_mode="bypassPermissions",
        )
        logger.info("Starting synthesis agent: %s", name)
        name, result = await _run_with_retry(name, full_prompt, options)
        logger.info("Synthesis agent finished: %s (%d chars)", name, len(result))
        return name, result

    tasks = [
        _run_synthesizer(name, prompt)
        for name, prompt in synthesizer_configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    synthesis: dict[str, str] = {}
    failed: list[str] = []
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Synthesizer failed after retries: %s", result)
            failed.append(str(result))
            continue
        name, text = result  # type: ignore[misc]
        synthesis[name] = text

    if len(synthesis) < min_success:
        raise RuntimeError(
            f"Consolidation failed: only {len(synthesis)}/{len(synthesizer_configs)} "
            f"agents succeeded (minimum {min_success} required). "
            f"Failures: {failed}"
        )

    if failed:
        logger.warning(
            "Consolidation partially succeeded: %d/%d agents OK (failed: %s)",
            len(synthesis), len(synthesizer_configs), ", ".join(failed),
        )

    return synthesis


# ---------------------------------------------------------------------------
# Phase 3: Report generation -- single orchestrator with MCP tools
# ---------------------------------------------------------------------------

def _recent_report_openings(reports_dir: Path | None, n: int = 3) -> str:
    """Return the opening paragraph of the N most recent reports, for anti-echo.

    Reads the most recent ``ai-news_*_to_*.md`` files and extracts the first
    non-empty paragraph after the ``## Executive Summary`` heading. Used to tell
    the orchestrator not to reuse the same opening structure/framing again.
    """
    if not reports_dir or not reports_dir.exists():
        return ""
    files = sorted(reports_dir.glob("ai-news_*_to_*.md"), reverse=True)[:n]
    openings: list[str] = []
    for fp in files:
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        after = text.split("## Executive Summary", 1)
        if len(after) < 2:
            continue
        para = next((p.strip() for p in after[1].split("\n\n") if p.strip()), "")
        if para:
            openings.append(f"- ({fp.stem}) {para[:400]}")
    return "\n".join(openings)


async def generate_report(
    fetch_results: dict[str, FetchResult],
    exploration_results: dict[str, str],
    synthesis_results: dict[str, str],
    start_date: str,
    end_date: str,
    days: int,
    max_budget_usd: float = 1.0,
    reports_dir: Path | None = None,
) -> str:
    """Run the orchestrator agent to produce the final markdown report.

    The orchestrator has access to all data via MCP tools (raw fetched items,
    exploration analyses, and synthesis outputs) so it can pull in details
    as needed while composing the report.

    Args:
        fetch_results: Raw fetch results keyed by source name.
        exploration_results: Output from :func:`run_exploration`.
        synthesis_results: Output from :func:`run_consolidation`.
        start_date: Human-readable start date for the report period.
        end_date: Human-readable end date for the report period.
        days: Number of days covered.
        max_budget_usd: Budget for the orchestrator agent.

    Returns:
        Complete markdown report string.
    """
    fetch_data = _build_fetch_data_dict(fetch_results)

    # Create MCP server exposing all data via tools.
    news_server = create_news_tools(
        fetch_results=fetch_data,
        exploration_results=exploration_results,
        synthesis_results=synthesis_results,
    )

    total_items = sum(
        len(data.get("items", [])) for data in fetch_data.values()
    )
    sources = ", ".join(sorted(fetch_data.keys()))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    template_context = REPORT_TEMPLATE.format(
        start_date=start_date,
        end_date=end_date,
        total_items=total_items,
        sources=sources,
        generated_at=now,
    )

    prior = _recent_report_openings(reports_dir)
    prior_block = (
        "\n\nRECENT PRIOR OPENINGS — DO NOT ECHO THESE "
        "(vary structure, subject, and framing):\n"
        f"{prior}\n"
        if prior
        else ""
    )

    prompt = f"""{ORCHESTRATOR_PROMPT}

REPORT TEMPLATE TO FOLLOW:
{template_context}
{prior_block}
DATE RANGE: {start_date} to {end_date} ({days} days)
TOTAL ITEMS: {total_items}
SOURCES: {sources}

Generate the complete report now. Use the tools to access all data."""

    # Create a save_report tool that captures the report via structured tool
    # call rather than relying on free-text response.  This prevents the agent
    # from writing to /tmp and returning a conversational summary instead.
    captured_report: list[str] = []  # mutable container for closure

    @tool("save_report", "Submit the final markdown report. Call this with the complete report content.", {
        "markdown": str,
    })
    async def save_report_tool(args: dict[str, Any]) -> dict[str, Any]:
        captured_report.append(args["markdown"])
        return {"content": [{"type": "text", "text": "Report saved successfully."}]}

    report_server = create_sdk_mcp_server(
        name="ai-news-report-output",
        version="1.0.0",
        tools=[save_report_tool],
    )

    # max_turns=20: on 2026-05-14 the agent hit the previous cap of 10
    # before emitting any report text. Exploration+synthesis are already
    # digested in text form, so the orchestrator should normally need only
    # 2-3 tool calls (get_exploration_results, get_synthesis_results) plus
    # one long composition turn. 20 is a generous defensive ceiling.
    #
    # Raw-fetch tools are intentionally NOT included: the exploration agents
    # already condensed the 8 sources into text. Exposing get_fetched_data
    # tempts the orchestrator to spider per-source and exhaust its turn
    # budget before composing anything.
    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5",
        max_turns=20,
        max_budget_usd=max_budget_usd,
        mcp_servers={"news": news_server, "output": report_server},
        allowed_tools=[
            "mcp__news__get_exploration_results",
            "mcp__news__get_synthesis_results",
            "mcp__output__save_report",
        ],
    )

    logger.info("Starting orchestrator agent (budget=$%.2f)", max_budget_usd)
    text_response = await _run_single_query(prompt, options, timeout=30 * 60)

    # Prefer the structured tool output; fall back to extracting report from
    # the agent's text response using the "# AI News Report:" marker.  This
    # handles the case where save_report fails due to MCP stream issues (e.g.
    # idle-timeout on a large payload after a long generation phase).
    if captured_report:
        report = captured_report[-1]
        logger.info("Report captured via save_report tool (%d chars)", len(report))
    else:
        # Try to extract the actual markdown report from accumulated text.
        report = text_response
        marker = "# AI News Report:"
        idx = text_response.find(marker)
        if idx >= 0:
            report = text_response[idx:]
            logger.info(
                "Report extracted from text response at offset %d (%d chars)",
                idx, len(report),
            )
        else:
            logger.warning(
                "Agent did not call save_report tool and no report marker found; "
                "using raw text response (%d chars)",
                len(report),
            )

    # Validate that the report looks like a real report, not a summary of
    # an error or a description of what the agent tried to do.  Abort the
    # pipeline rather than publishing a stub: on 2026-05-14 a 226-char
    # "I'll generate the AI news report..." preamble was emailed to all
    # subscribers because this check only logged instead of raising.
    if len(report) < 3000:
        raise RuntimeError(
            f"Orchestrator returned a suspiciously short report "
            f"({len(report)} chars). The agent likely never called "
            f"save_report (MCP stream/idle-timeout) and the fallback "
            f"captured only a conversational preamble. Aborting before "
            f"publish. Raw response: {report[:500]!r}"
        )

    logger.info("Orchestrator finished (%d chars)", len(report))
    return report
