"""Fetch AI news from TechCrunch RSS feed."""

import asyncio
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

from ai_news.fetchers.base import FetchResult


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_rss_date(date_str: str) -> Optional[str]:
    """Parse RSS pubDate format to ISO date."""
    try:
        dt = datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except (ValueError, IndexError):
        return None


def _is_ai_related(categories: list[str], title: str, description: str) -> bool:
    """Check if article is AI-related based on categories and content."""
    ai_keywords = [
        "ai", "artificial intelligence", "machine learning", "ml",
        "llm", "gpt", "chatgpt", "claude", "openai", "anthropic",
        "deep learning", "neural", "transformer", "generative",
        "deepmind", "gemini", "copilot", "midjourney", "stable diffusion",
    ]

    for cat in categories:
        if cat.lower() in ["ai", "artificial-intelligence", "machine-learning"]:
            return True

    text = f"{title} {description}".lower()
    return any(kw in text for kw in ai_keywords)


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    rss_url = "https://techcrunch.com/feed/"

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    items: list[dict] = []

    namespaces = {
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }

    req = urllib.request.Request(
        rss_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        content = response.read().decode("utf-8")

    root = ET.fromstring(content)

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        desc_elem = item.find("description")
        pub_date_elem = item.find("pubDate")
        creator_elem = item.find("dc:creator", namespaces)

        if title_elem is None or link_elem is None:
            continue

        title = title_elem.text or ""
        link = link_elem.text or ""
        description = (
            _clean_html(desc_elem.text)
            if desc_elem is not None and desc_elem.text
            else ""
        )
        author = creator_elem.text if creator_elem is not None else ""

        categories = [cat.text for cat in item.findall("category") if cat.text]

        item_date = None
        if pub_date_elem is not None and pub_date_elem.text:
            item_date = _parse_rss_date(pub_date_elem.text)

        if not item_date:
            continue

        try:
            parsed_date = datetime.strptime(item_date, "%Y-%m-%d").date()
            if not (start_date <= parsed_date <= end_date):
                continue
        except ValueError:
            continue

        if not _is_ai_related(categories, title, description):
            continue

        items.append({
            "title": title,
            "url": link,
            "source": "techcrunch",
            "date": item_date,
            "summary": description[:500] if description else "",
            "author": author,
            "categories": categories,
            "tags": ["industry", "startups", "funding"],
        })

    return items


async def fetch(days: int = 7) -> FetchResult:
    """Fetch AI news from TechCrunch for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="techcrunch",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://techcrunch.com/category/artificial-intelligence/",
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="techcrunch",
            items=[],
            error=str(e),
        )
