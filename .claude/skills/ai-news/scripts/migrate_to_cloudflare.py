#!/usr/bin/env python3
"""
Migrate existing reports from docs/archive/ to Cloudflare R2 + KV.

Usage:
    API_SECRET=your_secret uv run python migrate_to_cloudflare.py

This script:
1. Reads manifest.jsonl and deduplicates by date range (keeps latest)
2. Finds corresponding HTML files in docs/archive/
3. Uploads each to the Cloudflare Worker API
"""

import json
import os
import sys
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Configuration
API_BASE = "https://ai-news-signup.julienh15.workers.dev"
MANIFEST_PATH = Path(__file__).parent.parent.parent.parent.parent / "reports" / "manifest.jsonl"
ARCHIVE_DIR = Path(__file__).parent.parent.parent.parent.parent / "docs" / "archive"

def ordinal(n: int) -> str:
    """Return ordinal suffix for a number."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

def format_date_for_filename(date_str: str) -> str:
    """Convert YYYY-MM-DD to human-readable format like 'dec_30th_2025'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    month = dt.strftime("%b").lower()
    day = ordinal(dt.day)
    year = dt.year
    return f"{month}_{day}_{year}"

def get_html_filename(start_date: str, end_date: str) -> str:
    """Generate the expected HTML filename from date range."""
    start_fmt = format_date_for_filename(start_date)
    end_fmt = format_date_for_filename(end_date)
    return f"{start_fmt}_to_{end_fmt}.html"

def load_manifest() -> list[dict]:
    """Load and deduplicate manifest entries."""
    entries = []
    with open(MANIFEST_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # Deduplicate by date range, keeping latest by generated_at
    by_range = {}
    for entry in entries:
        key = (entry["date_range_start"], entry["date_range_end"])
        if key not in by_range:
            by_range[key] = entry
        else:
            existing = by_range[key]
            if entry["generated_at"] > existing["generated_at"]:
                by_range[key] = entry

    return list(by_range.values())

def generate_report_id(entry: dict) -> str:
    """Generate a unique report ID from manifest entry."""
    # Use end date and timestamp for uniqueness
    ts = entry["generated_at"].replace(":", "").replace("-", "")
    return f"{entry['date_range_end']}_{ts}"

def generate_title(entry: dict) -> str:
    """Generate a human-readable title."""
    start = datetime.strptime(entry["date_range_start"], "%Y-%m-%d")
    end = datetime.strptime(entry["date_range_end"], "%Y-%m-%d")

    start_str = start.strftime("%b %d")
    end_str = end.strftime("%b %d, %Y")

    return f"AI News Digest: {start_str} - {end_str}"

def upload_report(entry: dict, html_content: str, api_secret: str) -> bool:
    """Upload a single report to Cloudflare."""
    report_id = generate_report_id(entry)

    headers = {
        "Authorization": f"Bearer {api_secret}",
        "X-Report-Id": report_id,
        "X-Date-Start": entry["date_range_start"],
        "X-Date-End": entry["date_range_end"],
        "X-Generated-At": entry["generated_at"],
        "X-Title": generate_title(entry),
        "X-Summary": f"Coverage of {entry.get('total_items', 'N/A')} AI news items from {len(entry.get('sources_ok', []))} sources",
        "X-Days": str(entry.get("days", 1)),
        "X-Total-Items": str(entry.get("total_items", 0)),
        "Content-Type": "text/html",
    }

    response = requests.post(
        f"{API_BASE}/archive",
        headers=headers,
        data=html_content.encode("utf-8"),
    )

    if response.ok:
        print(f"  Uploaded: {report_id}")
        return True
    else:
        print(f"  FAILED: {report_id} - {response.status_code}: {response.text}")
        return False

def main():
    api_secret = os.environ.get("ADMIN_API_SECRET")
    if not api_secret:
        print("Error: ADMIN_API_SECRET environment variable required")
        print("Set it in .env or run: ADMIN_API_SECRET=secret uv run python migrate_to_cloudflare.py")
        sys.exit(1)

    print(f"Loading manifest from {MANIFEST_PATH}")
    entries = load_manifest()
    print(f"Found {len(entries)} unique reports (after deduplication)")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for entry in entries:
        html_filename = get_html_filename(entry["date_range_start"], entry["date_range_end"])
        html_path = ARCHIVE_DIR / html_filename

        print(f"\nProcessing: {entry['date_range_start']} to {entry['date_range_end']}")
        print(f"  Looking for: {html_path}")

        if not html_path.exists():
            print(f"  SKIPPED: HTML file not found")
            skip_count += 1
            continue

        html_content = html_path.read_text()

        if upload_report(entry, html_content, api_secret):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n{'='*40}")
    print(f"Migration complete!")
    print(f"  Uploaded: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Skipped: {skip_count}")

if __name__ == "__main__":
    main()
