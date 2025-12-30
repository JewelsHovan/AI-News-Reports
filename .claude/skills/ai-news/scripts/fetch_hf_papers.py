#!/usr/bin/env python3
"""
Fetch trending AI papers from HuggingFace Daily Papers.
Uses date-based URLs to fetch papers from specific days.
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


def extract_papers_from_html(html_content: str, date_str: str) -> list:
    """
    Extract paper information from HuggingFace papers page HTML.

    Note: This is a best-effort extraction since the page is client-rendered.
    For production use, consider using a headless browser.
    """
    papers = []

    # Pattern to find paper links and titles
    # Format: /papers/YYMM.NNNNN with title nearby
    paper_pattern = r'href="/papers/(\d{4}\.\d+)"[^>]*>([^<]+)</a>'

    for match in re.finditer(paper_pattern, html_content):
        paper_id = match.group(1)
        title = clean_text(match.group(2))

        if title and len(title) > 5:  # Filter out short/empty matches
            papers.append({
                "title": title,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "arxiv_url": f"https://arxiv.org/abs/{paper_id}",
                "paper_id": paper_id,
                "source": "huggingface",
                "date": date_str,
                "tags": ["research", "papers"]
            })

    # Deduplicate by paper_id
    seen = set()
    unique_papers = []
    for paper in papers:
        if paper["paper_id"] not in seen:
            seen.add(paper["paper_id"])
            unique_papers.append(paper)

    return unique_papers


def fetch_papers_for_date(date: datetime) -> list:
    """Fetch papers for a specific date."""
    date_str = date.strftime("%Y-%m-%d")
    url = f"https://huggingface.co/papers?date={date_str}"

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

        return extract_papers_from_html(content, date_str)

    except Exception as e:
        print(f"Error fetching papers for {date_str}: {e}", file=sys.stderr)
        return []


def fetch_hf_papers(days: int = 7) -> list:
    """
    Fetch papers from HuggingFace for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of paper items
    """
    all_papers = []
    end_date = datetime.now()

    for i in range(days):
        current_date = end_date - timedelta(days=i)
        papers = fetch_papers_for_date(current_date)
        all_papers.extend(papers)

    return all_papers


def main():
    parser = argparse.ArgumentParser(description='Fetch AI papers from HuggingFace Daily Papers')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')

    args = parser.parse_args()

    items = fetch_hf_papers(args.days)

    output = {
        "source": "huggingface",
        "source_url": "https://huggingface.co/papers",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
