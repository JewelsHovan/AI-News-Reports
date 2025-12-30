#!/usr/bin/env python3
"""
Fetch AI news from TechCrunch RSS feed.
Filters for AI-related articles within the specified date range.
"""

import argparse
import json
import sys
import re
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import xml.etree.ElementTree as ET
import html


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_rss_date(date_str: str) -> Optional[str]:
    """Parse RSS pubDate format to ISO date."""
    # Format: "Mon, 23 Dec 2025 21:48:46 +0000"
    try:
        dt = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        return None


def is_ai_related(categories: list, title: str, description: str) -> bool:
    """Check if article is AI-related based on categories and content."""
    ai_keywords = [
        'ai', 'artificial intelligence', 'machine learning', 'ml',
        'llm', 'gpt', 'chatgpt', 'claude', 'openai', 'anthropic',
        'deep learning', 'neural', 'transformer', 'generative',
        'deepmind', 'gemini', 'copilot', 'midjourney', 'stable diffusion'
    ]

    # Check categories first
    for cat in categories:
        if cat.lower() in ['ai', 'artificial-intelligence', 'machine-learning']:
            return True

    # Check title and description
    text = f"{title} {description}".lower()
    return any(kw in text for kw in ai_keywords)


def fetch_techcrunch(days: int = 7) -> list:
    """
    Fetch AI news from TechCrunch RSS feed for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of news items
    """
    rss_url = "https://techcrunch.com/feed/"

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

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

        # Parse namespaces
        namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'content': 'http://purl.org/rss/1.0/modules/content/'
        }

        root = ET.fromstring(content)

        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            pub_date_elem = item.find('pubDate')
            creator_elem = item.find('dc:creator', namespaces)

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            description = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""
            author = creator_elem.text if creator_elem is not None else ""

            # Get categories
            categories = [cat.text for cat in item.findall('category') if cat.text]

            # Parse date
            item_date = None
            if pub_date_elem is not None and pub_date_elem.text:
                item_date = parse_rss_date(pub_date_elem.text)

            if not item_date:
                continue

            # Check date range
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d").date()
                if not (start_date <= parsed_date <= end_date):
                    continue
            except ValueError:
                continue

            # Filter for AI-related content
            if not is_ai_related(categories, title, description):
                continue

            items.append({
                "title": title,
                "url": link,
                "source": "techcrunch",
                "date": item_date,
                "summary": description[:500] if description else "",
                "author": author,
                "categories": categories,
                "tags": ["industry", "startups", "funding"]
            })

    except Exception as e:
        print(f"Error fetching TechCrunch: {e}", file=sys.stderr)
        return []

    return items


def main():
    parser = argparse.ArgumentParser(description='Fetch AI news from TechCrunch')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')

    args = parser.parse_args()

    items = fetch_techcrunch(args.days)

    output = {
        "source": "techcrunch",
        "source_url": "https://techcrunch.com/category/artificial-intelligence/",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
