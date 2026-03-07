"""Fetch AI-related stories from Hacker News using the Algolia Search API."""

import asyncio
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from ai_news.fetchers.base import FetchResult


# Search queries covering different AI topic areas
SEARCH_QUERIES = [
    "AI artificial intelligence",
    "LLM GPT ChatGPT Claude",
    "machine learning deep learning",
    "OpenAI Anthropic DeepMind",
    "neural network transformer",
]


def _fetch_hn_search(
    query: str, start_timestamp: int, end_timestamp: int, page: int = 0
) -> dict:
    """Search Hacker News via Algolia API."""
    base_url = "https://hn.algolia.com/api/v1/search"

    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{start_timestamp},created_at_i<{end_timestamp}",
        "hitsPerPage": 50,
        "page": page,
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI-News-Bot/1.0"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {"hits": []}


def _process_hit(hit: dict) -> dict:
    """Convert a Hacker News API hit to standard format."""
    created_at = datetime.fromtimestamp(hit.get("created_at_i", 0))

    return {
        "title": hit.get("title", ""),
        "url": hit.get("url")
        or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
        "source": "hackernews",
        "date": created_at.strftime("%Y-%m-%d"),
        "score": hit.get("points", 0),
        "comments": hit.get("num_comments", 0),
        "discussion_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
        "author": hit.get("author", ""),
        "tags": ["community", "discussion"],
        "hn_id": hit.get("objectID"),
    }


def _fetch_sync(days: int, min_points: int = 10) -> list[dict]:
    """Synchronous fetch logic."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    all_items: dict[str, dict] = {}

    for query in SEARCH_QUERIES:
        result = _fetch_hn_search(query, start_timestamp, end_timestamp)

        for hit in result.get("hits", []):
            hn_id = hit.get("objectID")
            if hn_id and hn_id not in all_items:
                item = _process_hit(hit)
                if item["score"] >= min_points:
                    all_items[hn_id] = item

    # Sort by score descending
    return sorted(all_items.values(), key=lambda x: x["score"], reverse=True)


async def fetch(days: int = 7) -> FetchResult:
    """Fetch AI-related stories from Hacker News for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="hackernews",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://news.ycombinator.com/",
                "search_api": "https://hn.algolia.com/api/v1/search",
                "min_points_filter": 10,
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="hackernews",
            items=[],
            error=str(e),
        )
