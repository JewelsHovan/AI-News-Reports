"""Agent definitions and orchestration for AI news analysis."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
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


async def _run_single_query(prompt: str, options: ClaudeAgentOptions) -> str:
    """Run a single agent query and extract the text response.

    Prefers the ``ResultMessage.result`` field when available, falling back
    to accumulating ``TextBlock`` content from ``AssistantMessage`` chunks.
    """
    text_parts: list[str] = []
    final_result: str | None = None

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            if message.result:
                final_result = message.result
            if message.is_error:
                logger.error("Agent query ended with error (session %s)", message.session_id)
        elif isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)

    if final_result is not None:
        return final_result
    return "\n".join(text_parts)


# ---------------------------------------------------------------------------
# Phase 1: Exploration -- 4 domain-specific subagents in parallel
# ---------------------------------------------------------------------------

async def run_exploration(
    fetch_results: dict[str, FetchResult],
    max_budget_usd: float = 2.0,
) -> dict[str, str]:
    """Run 4 exploration subagents in parallel.

    Each explorer receives only the data relevant to its domain so it can
    focus its analysis.  All explorers run concurrently.

    Args:
        fetch_results: Raw fetch results keyed by source name.
        max_budget_usd: Total budget across all explorers.

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
        result = await _run_single_query(full_prompt, options)
        logger.info("Exploration agent finished: %s (%d chars)", name, len(result))
        return name, result

    tasks = [
        _run_explorer(name, prompt, data)
        for name, prompt, data in explorer_configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    exploration: dict[str, str] = {}
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Explorer failed: %s", result)
            continue
        name, text = result  # type: ignore[misc]
        exploration[name] = text

    return exploration


# ---------------------------------------------------------------------------
# Phase 2: Consolidation -- 3 synthesis subagents in parallel
# ---------------------------------------------------------------------------

async def run_consolidation(
    exploration_results: dict[str, str],
    max_budget_usd: float = 2.0,
) -> dict[str, str]:
    """Run 3 consolidation subagents in parallel.

    Each synthesizer receives all exploration outputs and focuses on a
    different aspect: top stories, major trends, or actionable implications.

    Args:
        exploration_results: Output from :func:`run_exploration`.
        max_budget_usd: Total budget across all synthesizers.

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
        result = await _run_single_query(full_prompt, options)
        logger.info("Synthesis agent finished: %s (%d chars)", name, len(result))
        return name, result

    tasks = [
        _run_synthesizer(name, prompt)
        for name, prompt in synthesizer_configs
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    synthesis: dict[str, str] = {}
    for result in results:
        if isinstance(result, BaseException):
            logger.error("Synthesizer failed: %s", result)
            continue
        name, text = result  # type: ignore[misc]
        synthesis[name] = text

    return synthesis


# ---------------------------------------------------------------------------
# Phase 3: Report generation -- single orchestrator with MCP tools
# ---------------------------------------------------------------------------

async def generate_report(
    fetch_results: dict[str, FetchResult],
    exploration_results: dict[str, str],
    synthesis_results: dict[str, str],
    start_date: str,
    end_date: str,
    days: int,
    max_budget_usd: float = 1.0,
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

    prompt = f"""{ORCHESTRATOR_PROMPT}

REPORT TEMPLATE TO FOLLOW:
{template_context}

DATE RANGE: {start_date} to {end_date} ({days} days)
TOTAL ITEMS: {total_items}
SOURCES: {sources}

Generate the complete report now. Use the tools to access all data."""

    options = ClaudeAgentOptions(
        model="claude-sonnet-4-5",
        max_turns=10,
        max_budget_usd=max_budget_usd,
        permission_mode="bypassPermissions",
        mcp_servers={"news": news_server},
        allowed_tools=[
            "mcp__news__get_fetched_data",
            "mcp__news__get_all_fetched_data",
            "mcp__news__get_source_items",
            "mcp__news__get_exploration_results",
            "mcp__news__get_synthesis_results",
        ],
    )

    logger.info("Starting orchestrator agent (budget=$%.2f)", max_budget_usd)
    report = await _run_single_query(prompt, options)
    logger.info("Orchestrator finished (%d chars)", len(report))
    return report
