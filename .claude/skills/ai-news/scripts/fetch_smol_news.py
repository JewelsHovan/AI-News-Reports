#!/usr/bin/env python3
"""
Fetch AI news from smol.ai newsletter RSS feed.
Returns structured JSON of news items within the specified date range.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import xml.etree.ElementTree as ET
import re
import html


def parse_date_from_title(title: str, current_year: int) -> Optional[str]:
    """Extract date from title like 'AI News Dec 22' or similar patterns."""
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    # Try patterns like "Dec 22" or "December 22"
    pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})'
    match = re.search(pattern, title.lower())
    if match:
        month = months[match.group(1)[:3]]
        day = match.group(2).zfill(2)
        return f"{current_year}-{month}-{day}"
    return None


def parse_date_from_link(link: str) -> Optional[str]:
    """Extract date from URL pattern /issues/YY-MM-DD-slug."""
    pattern = r'/issues/(\d{2})-(\d{2})-(\d{2})'
    match = re.search(pattern, link)
    if match:
        year = f"20{match.group(1)}"
        month = match.group(2)
        day = match.group(3)
        return f"{year}-{month}-{day}"
    return None


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def fetch_smol_news(days: int = 7) -> list:
    """
    Fetch news from smol.ai RSS feed for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of news items with title, url, date, summary, source
    """
    rss_url = "https://news.smol.ai/rss.xml"

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    current_year = end_date.year

    items = []

    try:
        req = urllib.request.Request(
            rss_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'application/rss+xml, application/xml, text/xml'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')

        root = ET.fromstring(content)

        # Find all items in the RSS feed
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            pub_date_elem = item.find('pubDate')

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            description = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""

            # Try to extract date from link first, then title
            item_date = parse_date_from_link(link) or parse_date_from_title(title, current_year)

            # If we have a pubDate, parse it
            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    # RSS date format: "Mon, 23 Dec 2024 00:00:00 GMT"
                    pub_date = datetime.strptime(
                        pub_date_elem.text[:16], "%a, %d %b %Y"
                    ).date()
                    item_date = pub_date.isoformat()
                except (ValueError, IndexError):
                    pass

            if not item_date:
                continue

            # Check if within date range
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d").date()
                if start_date <= parsed_date <= end_date:
                    items.append({
                        "title": title,
                        "url": link,
                        "source": "smol.ai",
                        "date": item_date,
                        "summary": description[:500] if description else "",
                        "tags": ["newsletter", "ai-digest"]
                    })
            except ValueError:
                continue

    except Exception as e:
        print(f"Error fetching smol.ai news: {e}", file=sys.stderr)
        return []

    return items


def main():
    parser = argparse.ArgumentParser(description='Fetch AI news from smol.ai newsletter')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON (default)')

    args = parser.parse_args()

    items = fetch_smol_news(args.days)

    output = {
        "source": "smol.ai",
        "source_url": "https://news.smol.ai/",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
