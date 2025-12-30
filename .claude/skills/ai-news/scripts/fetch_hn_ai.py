#!/usr/bin/env python3
"""
Fetch AI-related stories from Hacker News using the Algolia Search API.
Filters for AI/ML keywords and returns stories within the date range.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import urllib.parse


# AI-related search terms to filter stories
AI_KEYWORDS = [
    "AI", "artificial intelligence", "machine learning", "ML",
    "GPT", "LLM", "large language model", "ChatGPT", "Claude",
    "neural network", "deep learning", "transformer",
    "OpenAI", "Anthropic", "Google AI", "DeepMind",
    "generative AI", "foundation model", "diffusion",
    "computer vision", "NLP", "natural language",
    "AGI", "AI safety", "alignment"
]


def fetch_hn_search(query: str, start_timestamp: int, end_timestamp: int, page: int = 0) -> dict:
    """
    Search Hacker News via Algolia API.

    Args:
        query: Search query
        start_timestamp: Unix timestamp for start date
        end_timestamp: Unix timestamp for end date
        page: Page number for pagination

    Returns:
        API response dict
    """
    base_url = "https://hn.algolia.com/api/v1/search"

    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{start_timestamp},created_at_i<{end_timestamp}",
        "hitsPerPage": 50,
        "page": page
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'AI-News-Bot/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error searching HN for '{query}': {e}", file=sys.stderr)
        return {"hits": []}


def process_hit(hit: dict) -> dict:
    """Convert a Hacker News API hit to our standard format."""
    created_at = datetime.fromtimestamp(hit.get("created_at_i", 0))

    return {
        "title": hit.get("title", ""),
        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
        "source": "hackernews",
        "date": created_at.strftime("%Y-%m-%d"),
        "score": hit.get("points", 0),
        "comments": hit.get("num_comments", 0),
        "discussion_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
        "author": hit.get("author", ""),
        "tags": ["community", "discussion"],
        "hn_id": hit.get("objectID")
    }


def fetch_hn_ai(days: int = 7, min_points: int = 10) -> list:
    """
    Fetch AI-related stories from Hacker News for the past N days.

    Args:
        days: Number of days to look back
        min_points: Minimum points threshold for relevance

    Returns:
        List of story items
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    start_timestamp = int(start_date.timestamp())
    end_timestamp = int(end_date.timestamp())

    all_items = {}

    # Search for each keyword group
    search_queries = [
        "AI artificial intelligence",
        "LLM GPT ChatGPT Claude",
        "machine learning deep learning",
        "OpenAI Anthropic DeepMind",
        "neural network transformer"
    ]

    for query in search_queries:
        result = fetch_hn_search(query, start_timestamp, end_timestamp)

        for hit in result.get("hits", []):
            hn_id = hit.get("objectID")
            if hn_id and hn_id not in all_items:
                item = process_hit(hit)
                if item["score"] >= min_points:  # Filter by minimum points
                    all_items[hn_id] = item

    # Sort by score descending
    items = sorted(all_items.values(), key=lambda x: x["score"], reverse=True)

    return items


def main():
    parser = argparse.ArgumentParser(description='Fetch AI-related stories from Hacker News')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--min-points', type=int, default=10,
                        help='Minimum points threshold (default: 10)')

    args = parser.parse_args()

    items = fetch_hn_ai(args.days, args.min_points)

    output = {
        "source": "hackernews",
        "source_url": "https://news.ycombinator.com/",
        "search_api": "https://hn.algolia.com/api/v1/search",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "min_points_filter": args.min_points,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
