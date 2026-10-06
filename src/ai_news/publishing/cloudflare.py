"""Upload HTML report to Cloudflare R2 + KV archive."""

import asyncio
import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from ai_news.publishing.branding import NEWSLETTER_NAME


@dataclass
class UploadResult:
    success: bool
    report_id: str | None = None
    url: str | None = None
    error: str | None = None


def _generate_report_id(end_date: str, generated_at: str) -> str:
    """Generate a unique report ID from end date and timestamp."""
    ts = generated_at.replace(":", "").replace("-", "")
    return f"{end_date}_{ts}"


def _generate_default_title(start_date: str, end_date: str) -> str:
    """Generate a human-readable title from date range."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start_str = start.strftime("%b %d")
    end_str = end.strftime("%b %d, %Y")
    return f"{NEWSLETTER_NAME}: {start_str} - {end_str}"


def _encode_listing(listing: dict) -> str:
    """Encode listing metadata for the X-Meta header (base64 UTF-8 JSON, since
    header values must be Latin-1 and headlines often contain em-dashes)."""
    return base64.b64encode(json.dumps(listing, ensure_ascii=False).encode("utf-8")).decode("ascii")


def issue_number_for(reports: list[dict], start_date: str, end_date: str) -> int:
    """Sequential issue number: 1 + distinct earlier date ranges in the archive.

    Duplicate uploads of the same range share a number, and re-running a range
    reproduces its number.
    """
    ranges = {(r["date_range_end"], r["date_range_start"]) for r in reports}
    return sum(1 for rng in ranges if rng < (end_date, start_date)) + 1


def _issue_number_sync(api_base: str, start_date: str, end_date: str) -> int | None:
    try:
        response = requests.get(f"{api_base}/archive", timeout=30)
        response.raise_for_status()
        reports = response.json()["data"]["reports"]
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return None
    return issue_number_for(reports, start_date, end_date)


async def fetch_issue_number(
    start_date: str,
    end_date: str,
    api_base: str = "https://ai-news-signup.julienh15.workers.dev",
) -> int | None:
    """Number for the issue covering start..end, from the public archive (None if unreachable)."""
    return await asyncio.to_thread(_issue_number_sync, api_base, start_date, end_date)


def _upload_sync(
    html_path: Path,
    start_date: str,
    end_date: str,
    days: int,
    total_items: int,
    api_secret: str,
    title: str | None,
    summary: str | None,
    api_base: str,
    listing: dict | None = None,
) -> UploadResult:
    """Synchronous implementation of the upload logic."""
    if not html_path.exists():
        return UploadResult(
            success=False,
            error=f"HTML file not found: {html_path}",
        )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_id = _generate_report_id(end_date, generated_at)

    if not title:
        title = _generate_default_title(start_date, end_date)

    if not summary:
        summary = f"AI news coverage with {total_items} items"

    try:
        html_content = html_path.read_text(encoding="utf-8")
    except OSError as exc:
        return UploadResult(success=False, error=f"Failed to read HTML file: {exc}")

    headers = {
        "Authorization": f"Bearer {api_secret}",
        "X-Report-Id": report_id,
        "X-Date-Start": start_date,
        "X-Date-End": end_date,
        "X-Generated-At": generated_at,
        "X-Title": title,
        "X-Summary": summary,
        "X-Days": str(days),
        "X-Total-Items": str(total_items),
        **({"X-Meta": _encode_listing(listing)} if listing else {}),
        "Content-Type": "text/html",
    }

    try:
        response = requests.post(
            f"{api_base}/archive",
            headers=headers,
            data=html_content.encode("utf-8"),
            timeout=60,
        )
    except requests.RequestException as exc:
        return UploadResult(success=False, error=f"Request failed: {exc}")

    if response.ok:
        return UploadResult(
            success=True,
            report_id=report_id,
            url=f"{api_base}/archive/{report_id}",
        )
    else:
        return UploadResult(
            success=False,
            error=f"{response.status_code}: {response.text}",
        )


async def upload_report(
    html_path: Path,
    start_date: str,
    end_date: str,
    days: int,
    total_items: int,
    api_secret: str,
    title: str | None = None,
    summary: str | None = None,
    api_base: str = "https://ai-news-signup.julienh15.workers.dev",
    listing: dict | None = None,
) -> UploadResult:
    """Upload HTML report to Cloudflare R2 + KV archive.

    Args:
        html_path: Path to the rendered HTML report file.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        days: Number of days covered by the report.
        total_items: Total number of news items in the report.
        api_secret: Admin API secret for the Cloudflare Worker.
        title: Custom title. Defaults to auto-generated from dates.
        summary: Brief summary. Defaults to auto-generated.
        api_base: Base URL of the Cloudflare Worker API.
        listing: Archive-card metadata (headline, tldr, top_stories, tags).

    Returns:
        UploadResult indicating success/failure with report ID and URL on success.
    """
    return await asyncio.to_thread(
        _upload_sync,
        html_path,
        start_date,
        end_date,
        days,
        total_items,
        api_secret,
        title,
        summary,
        api_base,
        listing,
    )
