"""Fetch trending AI papers from HuggingFace Daily Papers."""

import asyncio
import re
import html
import urllib.request
from datetime import datetime, timedelta

from ai_news.fetchers.base import FetchResult


def _clean_text(text: str) -> str:
    """Clean HTML entities and extra whitespace."""
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _extract_papers_from_html(html_content: str, date_str: str) -> list[dict]:
    """
    Extract paper information from HuggingFace papers page HTML.

    Note: This is a best-effort extraction since the page is client-rendered.
    """
    papers = []

    # Pattern to find paper links and titles
    paper_pattern = r'href="/papers/(\d{4}\.\d+)"[^>]*>([^<]+)</a>'

    for match in re.finditer(paper_pattern, html_content):
        paper_id = match.group(1)
        title = _clean_text(match.group(2))

        if title and len(title) > 5:
            papers.append({
                "title": title,
                "url": f"https://huggingface.co/papers/{paper_id}",
                "arxiv_url": f"https://arxiv.org/abs/{paper_id}",
                "paper_id": paper_id,
                "source": "huggingface",
                "date": date_str,
                "tags": ["research", "papers"],
            })

    # Deduplicate by paper_id
    seen: set[str] = set()
    unique_papers = []
    for paper in papers:
        if paper["paper_id"] not in seen:
            seen.add(paper["paper_id"])
            unique_papers.append(paper)

    return unique_papers


def _fetch_papers_for_date(date: datetime) -> list[dict]:
    """Fetch papers for a specific date."""
    date_str = date.strftime("%Y-%m-%d")
    url = f"https://huggingface.co/papers?date={date_str}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode("utf-8")

        return _extract_papers_from_html(content, date_str)

    except Exception:
        return []


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    all_papers: list[dict] = []
    end_date = datetime.now()

    for i in range(days):
        current_date = end_date - timedelta(days=i)
        papers = _fetch_papers_for_date(current_date)
        all_papers.extend(papers)

    return all_papers


async def fetch(days: int = 7) -> FetchResult:
    """Fetch papers from HuggingFace Daily Papers for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="huggingface",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://huggingface.co/papers",
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="huggingface",
            items=[],
            error=str(e),
        )
