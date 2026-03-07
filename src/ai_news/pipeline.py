"""AI News pipeline orchestrator."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_news.config import PipelineConfig
from ai_news.fetchers.base import FetchResult
from ai_news.fetchers import (
    huggingface,
    reddit,
    hackernews,
    techcrunch,
    ai_news_site,
    the_batch,
    smol_news,
    simonwillison,
)

logger = logging.getLogger("ai_news")

ALL_FETCHERS = {
    "huggingface": huggingface.fetch,
    "reddit": reddit.fetch,
    "hackernews": hackernews.fetch,
    "techcrunch": techcrunch.fetch,
    "ai-news": ai_news_site.fetch,
    "the_batch": the_batch.fetch,
    "smol.ai": smol_news.fetch,
    "simonwillison": simonwillison.fetch,
}


@dataclass
class PipelineResult:
    success: bool
    report_path: Path | None = None
    html_path: Path | None = None
    upload_url: str | None = None
    newsletter_sent: int = 0
    sources_ok: list[str] = field(default_factory=list)
    sources_failed: list[str] = field(default_factory=list)
    total_items: int = 0
    errors: list[str] = field(default_factory=list)


async def fetch_all_sources(days: int) -> dict[str, FetchResult]:
    """Fetch from all sources concurrently."""

    async def fetch_one(name: str, fetcher) -> tuple[str, FetchResult]:
        logger.info(f"Fetching from {name}...")
        result = await fetcher(days)
        if result.success:
            logger.info(f"  {name}: {result.items_found} items")
        else:
            logger.warning(f"  {name}: FAILED - {result.error}")
        return name, result

    tasks = [fetch_one(name, fetcher) for name, fetcher in ALL_FETCHERS.items()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    fetch_results = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Fetcher crashed: {result}")
            continue
        name, fetch_result = result
        fetch_results[name] = fetch_result

    return fetch_results


async def analyze_and_generate(
    fetch_results: dict[str, FetchResult],
    start_date: str,
    end_date: str,
    days: int,
    max_budget_usd: float = 5.0,
) -> str:
    """Run the full analysis pipeline: explore -> consolidate -> generate."""
    from ai_news.analysis.agents import (
        run_exploration,
        run_consolidation,
        generate_report,
    )

    logger.info("Phase 2: Running exploration agents...")
    exploration = await run_exploration(
        fetch_results, max_budget_usd=max_budget_usd * 0.4
    )

    logger.info("Phase 3: Running consolidation agents...")
    synthesis = await run_consolidation(
        exploration, max_budget_usd=max_budget_usd * 0.3
    )

    logger.info("Phase 4: Generating report...")
    report = await generate_report(
        fetch_results=fetch_results,
        exploration_results=exploration,
        synthesis_results=synthesis,
        start_date=start_date,
        end_date=end_date,
        days=days,
        max_budget_usd=max_budget_usd * 0.3,
    )

    return report


async def publish_report(
    report_md: str,
    start_date: str,
    end_date: str,
    days: int,
    sources_ok: list[str],
    sources_failed: list[str],
    total_items: int,
    config: PipelineConfig,
) -> PipelineResult:
    """Run the publishing pipeline: persist -> render -> upload -> newsletter."""
    from ai_news.publishing.persist import write_report
    from ai_news.publishing.renderer import render_html
    from ai_news.publishing.cloudflare import upload_report
    from ai_news.publishing.newsletter import send_newsletter

    result = PipelineResult(
        success=True,
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        total_items=total_items,
    )

    # Step 1: Persist
    logger.info("Publishing: Writing report to disk...")
    persist_result = await write_report(
        content=report_md,
        start_date=start_date,
        end_date=end_date,
        days=days,
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        total_items=total_items,
        base_dir=config.reports_dir,
    )
    result.report_path = persist_result.filepath
    logger.info(
        f"  Saved: {persist_result.filepath} ({persist_result.bytes_written} bytes)"
    )

    # Step 2: Render HTML
    logger.info("Publishing: Rendering HTML...")
    render_result = await render_html(persist_result.filepath)
    result.html_path = render_result.html_path
    logger.info(f"  Rendered: {render_result.html_path}")

    # Step 3: Upload to Cloudflare (if configured)
    if config.admin_api_secret and not config.dry_run:
        logger.info("Publishing: Uploading to Cloudflare...")
        upload_result = await upload_report(
            html_path=render_result.html_path,
            start_date=start_date,
            end_date=end_date,
            days=days,
            total_items=total_items,
            api_secret=config.admin_api_secret,
            api_base=config.api_base_url,
        )
        if upload_result.success:
            result.upload_url = upload_result.url
            logger.info(f"  Uploaded: {upload_result.url}")
        else:
            result.errors.append(f"Upload failed: {upload_result.error}")
            logger.warning(f"  Upload failed: {upload_result.error}")
    elif config.dry_run:
        logger.info("Publishing: Skipping upload (dry run)")

    # Step 4: Send newsletter (if configured)
    if not config.dry_run:
        logger.info("Publishing: Sending newsletter...")
        newsletter_result = await send_newsletter(
            report_html_path=render_result.html_path,
            manifest_path=config.reports_dir / "manifest.jsonl",
            email_config_path=config.email_config_path,
            api_url=(
                f"{config.api_base_url}/api/subscribers"
                if config.admin_api_secret
                else None
            ),
            api_secret=config.admin_api_secret,
        )
        result.newsletter_sent = newsletter_result.sent_count
        if newsletter_result.errors:
            result.errors.extend(newsletter_result.errors)
        logger.info(
            f"  Sent: {newsletter_result.sent_count}, "
            f"Skipped: {newsletter_result.skipped_count}"
        )
    else:
        logger.info("Publishing: Skipping newsletter (dry run)")

    return result


async def run_pipeline(
    days: int = 2,
    dry_run: bool = False,
    skip_newsletter: bool = False,
    skip_upload: bool = False,
    config: PipelineConfig | None = None,
) -> PipelineResult:
    """Run the complete AI News pipeline.

    Args:
        days: Number of days to look back
        dry_run: Skip upload and newsletter
        skip_newsletter: Skip newsletter only
        skip_upload: Skip Cloudflare upload only
        config: Pipeline configuration (auto-loaded if None)

    Returns:
        PipelineResult with all outcomes
    """
    if config is None:
        config = PipelineConfig.from_env()

    config.days = days
    config.dry_run = dry_run or config.dry_run

    # Calculate date range
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%d"
    )

    logger.info(f"AI News Pipeline: {start_date} to {end_date} ({days} days)")
    logger.info(f"  Dry run: {config.dry_run}")
    logger.info(f"  Budget: ${config.max_budget_usd}")

    # Phase 1: Fetch
    logger.info("Phase 1: Fetching from all sources...")
    fetch_results = await fetch_all_sources(days)

    sources_ok = [name for name, r in fetch_results.items() if r.success]
    sources_failed = [name for name, r in fetch_results.items() if not r.success]
    total_items = sum(r.items_found for r in fetch_results.values() if r.success)

    logger.info(f"  Sources OK: {len(sources_ok)}/{len(ALL_FETCHERS)}")
    logger.info(f"  Total items: {total_items}")

    if len(sources_ok) < 2:
        return PipelineResult(
            success=False,
            sources_ok=sources_ok,
            sources_failed=sources_failed,
            errors=["Fewer than 2 sources succeeded - aborting"],
        )

    # Phase 2-4: Analyze (Agent SDK)
    report_md = await analyze_and_generate(
        fetch_results=fetch_results,
        start_date=start_date,
        end_date=end_date,
        days=days,
        max_budget_usd=config.max_budget_usd,
    )

    # Phase 5: Publish
    if skip_upload:
        config.admin_api_secret = None  # Disable upload
    if skip_newsletter:
        config.dry_run = True  # Disable newsletter

    pipeline_result = await publish_report(
        report_md=report_md,
        start_date=start_date,
        end_date=end_date,
        days=days,
        sources_ok=sources_ok,
        sources_failed=sources_failed,
        total_items=total_items,
        config=config,
    )

    logger.info("Pipeline complete!")
    return pipeline_result
