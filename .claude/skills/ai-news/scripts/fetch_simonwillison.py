#!/usr/bin/env python3
"""
Fetch AI-related blog posts from Simon Willison's blog (simonwillison.net).

Simon Willison is a prominent voice in AI tooling, prompt engineering, and developer
experience. His blog covers topics like AI-assisted programming, coding agents,
context engineering, and the Model Context Protocol (MCP).

This script fetches from multiple tag-specific Atom feeds and deduplicates entries
since the same post may appear under multiple tags.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import xml.etree.ElementTree as ET
import html


# Atom namespace
ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom'}

# Tag feeds to fetch
TAG_FEEDS = [
    'prompt-engineering',
    'ai-assisted-programming',
    'coding-agents',
    'vibe-coding',
    'context-engineering',
    'model-context-protocol',
    'system-prompts',
]


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_atom_date(date_str: str) -> Optional[str]:
    """
    Parse Atom date formats to YYYY-MM-DD.

    Atom uses ISO 8601 format: 2025-01-02T15:30:00Z or 2025-01-02T15:30:00+00:00
    """
    if not date_str:
        return None

    # Try common Atom date formats
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    # Handle timezone offset format like +00:00
    cleaned = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback: try to extract just the date portion
    match = re.match(r'(\d{4}-\d{2}-\d{2})', date_str)
    if match:
        return match.group(1)

    return None


def fetch_atom_feed(tag: str, timeout: int = 30) -> Optional[str]:
    """
    Fetch Atom feed content for a specific tag.

    Args:
        tag: The tag name to fetch
        timeout: Request timeout in seconds

    Returns:
        Feed XML content or None if fetch failed
    """
    url = f"https://simonwillison.net/tags/{tag}.atom"

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'application/atom+xml, application/xml, text/xml'
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        print(f"HTTP error fetching tag '{tag}': {e.code} {e.reason}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"URL error fetching tag '{tag}': {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Error fetching tag '{tag}': {e}", file=sys.stderr)
        return None


def parse_atom_entries(content: str, tag: str) -> list:
    """
    Parse Atom feed content and extract entries.

    Args:
        content: XML content of the Atom feed
        tag: The tag this feed was fetched from (for metadata)

    Returns:
        List of entry dictionaries
    """
    entries = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        print(f"XML parse error for tag '{tag}': {e}", file=sys.stderr)
        return entries

    # Find all entry elements (handle both namespaced and non-namespaced)
    atom_entries = root.findall('atom:entry', ATOM_NS)
    if not atom_entries:
        # Try without namespace
        atom_entries = root.findall('.//entry')
    if not atom_entries:
        # Try with default namespace
        atom_entries = root.findall('.//{http://www.w3.org/2005/Atom}entry')

    for entry in atom_entries:
        # Extract title
        title_elem = entry.find('atom:title', ATOM_NS)
        if title_elem is None:
            title_elem = entry.find('title')
        if title_elem is None:
            title_elem = entry.find('{http://www.w3.org/2005/Atom}title')
        title = title_elem.text if title_elem is not None and title_elem.text else ""

        # Extract link (prefer alternate link)
        link = ""
        for link_elem in entry.findall('atom:link', ATOM_NS) + entry.findall('link') + entry.findall('{http://www.w3.org/2005/Atom}link'):
            rel = link_elem.get('rel', 'alternate')
            if rel == 'alternate':
                link = link_elem.get('href', '')
                break
            elif not link:  # Fallback to any link
                link = link_elem.get('href', '')

        # Extract published/updated date
        date_elem = entry.find('atom:published', ATOM_NS)
        if date_elem is None:
            date_elem = entry.find('published')
        if date_elem is None:
            date_elem = entry.find('{http://www.w3.org/2005/Atom}published')
        if date_elem is None:
            date_elem = entry.find('atom:updated', ATOM_NS)
        if date_elem is None:
            date_elem = entry.find('updated')
        if date_elem is None:
            date_elem = entry.find('{http://www.w3.org/2005/Atom}updated')

        date_str = date_elem.text if date_elem is not None else None
        item_date = parse_atom_date(date_str)

        # Extract summary/content
        summary_elem = entry.find('atom:summary', ATOM_NS)
        if summary_elem is None:
            summary_elem = entry.find('summary')
        if summary_elem is None:
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
        if summary_elem is None:
            summary_elem = entry.find('atom:content', ATOM_NS)
        if summary_elem is None:
            summary_elem = entry.find('content')
        if summary_elem is None:
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}content')

        summary = ""
        if summary_elem is not None and summary_elem.text:
            summary = clean_html(summary_elem.text)[:500]

        # Extract categories from the feed
        categories = []
        for cat_elem in entry.findall('atom:category', ATOM_NS) + entry.findall('category') + entry.findall('{http://www.w3.org/2005/Atom}category'):
            term = cat_elem.get('term', '')
            if term:
                categories.append(term)

        if title and link:
            entries.append({
                "title": title,
                "url": link,
                "date": item_date,
                "summary": summary,
                "categories": categories,
                "source_tag": tag,  # Track which tag feed this came from
            })

    return entries


def fetch_simonwillison(days: int = 7) -> dict:
    """
    Fetch blog posts from Simon Willison's blog for the past N days.

    Fetches from multiple tag-specific Atom feeds and deduplicates by URL.

    Args:
        days: Number of days to look back

    Returns:
        Dictionary with source metadata and list of items
    """
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # Track all entries by URL for deduplication
    entries_by_url = {}
    tags_fetched = []

    for tag in TAG_FEEDS:
        content = fetch_atom_feed(tag)
        if content is None:
            continue

        tags_fetched.append(tag)
        entries = parse_atom_entries(content, tag)

        for entry in entries:
            url = entry["url"]

            # Check date filter
            if entry["date"]:
                try:
                    parsed_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
                    if not (start_date <= parsed_date <= end_date):
                        continue
                except ValueError:
                    continue
            else:
                # Skip entries without parseable dates
                continue

            if url in entries_by_url:
                # Merge categories and track additional source tags
                existing = entries_by_url[url]
                existing_cats = set(existing.get("categories", []))
                new_cats = set(entry.get("categories", []))
                existing["categories"] = list(existing_cats | new_cats)

                # Track all source tags
                if "source_tags" not in existing:
                    existing["source_tags"] = [existing.pop("source_tag", tag)]
                if entry["source_tag"] not in existing["source_tags"]:
                    existing["source_tags"].append(entry["source_tag"])
            else:
                entries_by_url[url] = entry

    # Convert to final format
    items = []
    for url, entry in entries_by_url.items():
        # Build tags list
        tags = ["expert", "blog"]
        source_tags = entry.pop("source_tags", [entry.pop("source_tag", None)])
        source_tags = [t for t in source_tags if t]
        tags.extend(source_tags)

        items.append({
            "title": entry["title"],
            "url": entry["url"],
            "source": "simonwillison",
            "date": entry["date"],
            "summary": entry["summary"],
            "categories": entry.get("categories", []),
            "tags": tags,
        })

    # Sort by date (newest first)
    items.sort(key=lambda x: x["date"] or "", reverse=True)

    return {
        "source": "simonwillison",
        "source_url": "https://simonwillison.net/",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": days,
        "tags_fetched": tags_fetched,
        "items_found": len(items),
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch AI-related posts from Simon Willison's blog"
    )
    parser.add_argument(
        'days',
        type=int,
        nargs='?',
        default=7,
        help='Number of days to look back (default: 7)'
    )

    args = parser.parse_args()

    output = fetch_simonwillison(args.days)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
