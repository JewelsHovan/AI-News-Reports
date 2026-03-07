"""Fetch AI-related blog posts from Simon Willison's blog (simonwillison.net).

Simon Willison is a prominent voice in AI tooling, prompt engineering, and developer
experience. Fetches from multiple tag-specific Atom feeds and deduplicates entries.
"""

import asyncio
import html
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

from ai_news.fetchers.base import FetchResult


# Atom namespace
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Tag feeds to fetch
TAG_FEEDS = [
    "prompt-engineering",
    "ai-assisted-programming",
    "coding-agents",
    "vibe-coding",
    "context-engineering",
    "model-context-protocol",
    "system-prompts",
]


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_atom_date(date_str: str) -> Optional[str]:
    """Parse Atom date formats to YYYY-MM-DD."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]

    # Handle timezone offset format like +00:00
    cleaned = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", date_str)

    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback: extract just the date portion
    match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
    if match:
        return match.group(1)

    return None


def _fetch_atom_feed(tag: str, timeout: int = 30) -> Optional[str]:
    """Fetch Atom feed content for a specific tag."""
    url = f"https://simonwillison.net/tags/{tag}.atom"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
                "Accept": "application/atom+xml, application/xml, text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, Exception):
        return None


def _parse_atom_entries(content: str, tag: str) -> list[dict]:
    """Parse Atom feed content and extract entries."""
    entries = []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return entries

    # Find all entry elements (handle both namespaced and non-namespaced)
    atom_entries = root.findall("atom:entry", ATOM_NS)
    if not atom_entries:
        atom_entries = root.findall(".//entry")
    if not atom_entries:
        atom_entries = root.findall(".//{http://www.w3.org/2005/Atom}entry")

    for entry in atom_entries:
        # Extract title
        title_elem = (
            entry.find("atom:title", ATOM_NS)
            or entry.find("title")
            or entry.find("{http://www.w3.org/2005/Atom}title")
        )
        title = title_elem.text if title_elem is not None and title_elem.text else ""

        # Extract link (prefer alternate link)
        link = ""
        all_links = (
            entry.findall("atom:link", ATOM_NS)
            + entry.findall("link")
            + entry.findall("{http://www.w3.org/2005/Atom}link")
        )
        for link_elem in all_links:
            rel = link_elem.get("rel", "alternate")
            if rel == "alternate":
                link = link_elem.get("href", "")
                break
            elif not link:
                link = link_elem.get("href", "")

        # Extract published/updated date
        date_elem = None
        for date_tag in [
            ("atom:published", ATOM_NS),
            ("published", {}),
            ("{http://www.w3.org/2005/Atom}published", {}),
            ("atom:updated", ATOM_NS),
            ("updated", {}),
            ("{http://www.w3.org/2005/Atom}updated", {}),
        ]:
            if len(date_tag) == 2 and date_tag[1]:
                date_elem = entry.find(date_tag[0], date_tag[1])
            else:
                date_elem = entry.find(date_tag[0])
            if date_elem is not None:
                break

        date_str = date_elem.text if date_elem is not None else None
        item_date = _parse_atom_date(date_str) if date_str else None

        # Extract summary/content
        summary_elem = None
        for sum_tag in [
            ("atom:summary", ATOM_NS),
            ("summary", {}),
            ("{http://www.w3.org/2005/Atom}summary", {}),
            ("atom:content", ATOM_NS),
            ("content", {}),
            ("{http://www.w3.org/2005/Atom}content", {}),
        ]:
            if len(sum_tag) == 2 and sum_tag[1]:
                summary_elem = entry.find(sum_tag[0], sum_tag[1])
            else:
                summary_elem = entry.find(sum_tag[0])
            if summary_elem is not None:
                break

        summary = ""
        if summary_elem is not None and summary_elem.text:
            summary = _clean_html(summary_elem.text)[:500]

        # Extract categories
        categories = []
        all_cats = (
            entry.findall("atom:category", ATOM_NS)
            + entry.findall("category")
            + entry.findall("{http://www.w3.org/2005/Atom}category")
        )
        for cat_elem in all_cats:
            term = cat_elem.get("term", "")
            if term:
                categories.append(term)

        if title and link:
            entries.append({
                "title": title,
                "url": link,
                "date": item_date,
                "summary": summary,
                "categories": categories,
                "source_tag": tag,
            })

    return entries


def _fetch_sync(days: int) -> tuple[list[dict], list[str]]:
    """Synchronous fetch logic. Returns (items, tags_fetched)."""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    entries_by_url: dict[str, dict] = {}
    tags_fetched: list[str] = []

    for tag in TAG_FEEDS:
        content = _fetch_atom_feed(tag)
        if content is None:
            continue

        tags_fetched.append(tag)
        entries = _parse_atom_entries(content, tag)

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
                continue

            if url in entries_by_url:
                # Merge categories and track additional source tags
                existing = entries_by_url[url]
                existing_cats = set(existing.get("categories", []))
                new_cats = set(entry.get("categories", []))
                existing["categories"] = list(existing_cats | new_cats)

                if "source_tags" not in existing:
                    existing["source_tags"] = [existing.pop("source_tag", tag)]
                if entry["source_tag"] not in existing["source_tags"]:
                    existing["source_tags"].append(entry["source_tag"])
            else:
                entries_by_url[url] = entry

    # Convert to final format
    items = []
    for entry in entries_by_url.values():
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

    return items, tags_fetched


async def fetch(days: int = 7) -> FetchResult:
    """Fetch blog posts from Simon Willison's blog for the past N days."""
    try:
        items, tags_fetched = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="simonwillison",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://simonwillison.net/",
                "tags_fetched": tags_fetched,
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="simonwillison",
            items=[],
            error=str(e),
        )
