#!/usr/bin/env python3
"""
Upload a rendered HTML report to Cloudflare R2 + KV archive.

Usage:
    uv run python upload_to_cloudflare.py <html_path> \
        --start-date YYYY-MM-DD \
        --end-date YYYY-MM-DD \
        --days N \
        --total-items COUNT \
        [--title "Custom Title"] \
        [--summary "Brief summary"]

Environment:
    ADMIN_API_SECRET - Required. The admin API secret for the Worker.

Example:
    ADMIN_API_SECRET=secret uv run python upload_to_cloudflare.py \
        reports/ai-news_2026-01-02_to_2026-01-03_20260103T120000Z.html \
        --start-date 2026-01-02 \
        --end-date 2026-01-03 \
        --days 1 \
        --total-items 50
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_BASE = "https://ai-news-signup.julienh15.workers.dev"


def generate_report_id(end_date: str, generated_at: str) -> str:
    """Generate a unique report ID."""
    ts = generated_at.replace(":", "").replace("-", "")
    return f"{end_date}_{ts}"


def generate_default_title(start_date: str, end_date: str) -> str:
    """Generate a human-readable title."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    start_str = start.strftime("%b %d")
    end_str = end.strftime("%b %d, %Y")
    return f"AI News Digest: {start_str} - {end_str}"


def upload_report(
    html_path: Path,
    start_date: str,
    end_date: str,
    days: int,
    total_items: int,
    title: str | None,
    summary: str | None,
    api_secret: str,
) -> dict:
    """Upload report to Cloudflare and return result."""
    generated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    report_id = generate_report_id(end_date, generated_at)

    if not title:
        title = generate_default_title(start_date, end_date)

    if not summary:
        summary = f"AI news coverage with {total_items} items"

    html_content = html_path.read_text()

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
        "Content-Type": "text/html",
    }

    response = requests.post(
        f"{API_BASE}/archive",
        headers=headers,
        data=html_content.encode("utf-8"),
    )

    if response.ok:
        result = response.json()
        return {
            "success": True,
            "report_id": report_id,
            "url": f"{API_BASE}/archive/{report_id}",
            "response": result,
        }
    else:
        return {
            "success": False,
            "error": f"{response.status_code}: {response.text}",
        }


def main():
    parser = argparse.ArgumentParser(
        description="Upload HTML report to Cloudflare archive"
    )
    parser.add_argument("html_path", type=Path, help="Path to HTML file")
    parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--days", type=int, required=True, help="Number of days covered")
    parser.add_argument("--total-items", type=int, default=0, help="Total items in report")
    parser.add_argument("--title", help="Custom title (optional)")
    parser.add_argument("--summary", help="Brief summary (optional)")

    args = parser.parse_args()

    api_secret = os.environ.get("ADMIN_API_SECRET")
    if not api_secret:
        print(json.dumps({"success": False, "error": "ADMIN_API_SECRET environment variable required"}))
        sys.exit(1)

    if not args.html_path.exists():
        print(json.dumps({"success": False, "error": f"HTML file not found: {args.html_path}"}))
        sys.exit(1)

    result = upload_report(
        html_path=args.html_path,
        start_date=args.start_date,
        end_date=args.end_date,
        days=args.days,
        total_items=args.total_items,
        title=args.title,
        summary=args.summary,
        api_secret=api_secret,
    )

    print(json.dumps(result, indent=2))

    if not result["success"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
