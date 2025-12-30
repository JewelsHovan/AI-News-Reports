#!/usr/bin/env python3
"""
Fetch trending AI papers from alphaXiv.
Captures papers with community engagement and discussions.
"""

import argparse
import json
import sys
import re
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import html


def clean_text(text: str) -> str:
    """Clean HTML entities and extra whitespace."""
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_papers_from_html(html_content: str) -> list:
    """Extract paper information from alphaXiv page."""
    papers = []

    # Pattern to find paper links with arxiv IDs
    # alphaXiv uses /abs/YYMM.NNNNN format
    paper_pattern = r'href="/abs/(\d{4}\.\d+)"[^>]*>([^<]+)</a>'

    # Also look for engagement metrics nearby
    votes_pattern = r'(\d+)\s*(?:votes?|likes?|upvotes?)'

    seen_ids = set()

    for match in re.finditer(paper_pattern, html_content, re.IGNORECASE):
        paper_id = match.group(1)
        title = clean_text(match.group(2))

        if paper_id in seen_ids or len(title) < 10:
            continue

        seen_ids.add(paper_id)

        # Try to find votes/engagement nearby
        start_pos = max(0, match.start() - 500)
        end_pos = min(len(html_content), match.end() + 500)
        context = html_content[start_pos:end_pos]

        votes = 0
        votes_match = re.search(votes_pattern, context, re.IGNORECASE)
        if votes_match:
            try:
                votes = int(votes_match.group(1))
            except ValueError:
                pass

        papers.append({
            "title": title,
            "url": f"https://alphaxiv.org/abs/{paper_id}",
            "arxiv_url": f"https://arxiv.org/abs/{paper_id}",
            "paper_id": paper_id,
            "source": "alphaxiv",
            "date": datetime.now().strftime("%Y-%m-%d"),  # Trending today
            "votes": votes,
            "tags": ["research", "trending", "community-picked"]
        })

    # Sort by votes if available
    papers.sort(key=lambda x: x['votes'], reverse=True)

    return papers


def fetch_alphaxiv(days: int = 7, limit: int = 30) -> list:
    """
    Fetch trending papers from alphaXiv.

    Args:
        days: Not directly used (alphaXiv shows trending)
        limit: Max number of papers to return

    Returns:
        List of trending paper items
    """
    url = "https://alphaxiv.org/"

    all_papers = []

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'text/html,application/xhtml+xml'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')

        papers = extract_papers_from_html(content)
        all_papers.extend(papers[:limit])

    except Exception as e:
        print(f"Error fetching alphaXiv: {e}", file=sys.stderr)

    return all_papers


def main():
    parser = argparse.ArgumentParser(description='Fetch trending papers from alphaXiv')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days (for consistency, shows trending)')
    parser.add_argument('--limit', type=int, default=30,
                        help='Maximum papers to fetch (default: 30)')

    args = parser.parse_args()

    items = fetch_alphaxiv(args.days, args.limit)

    output = {
        "source": "alphaxiv",
        "source_url": "https://alphaxiv.org/",
        "fetch_date": datetime.now().isoformat(),
        "note": "Trending papers with community engagement",
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
