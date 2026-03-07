"""Fetch news from artificialintelligence-news.com website."""

import asyncio
import html
import re
import urllib.request
from datetime import datetime, timedelta
from typing import Optional

from ai_news.fetchers.base import FetchResult


# Month name to number mapping
MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _clean_text(text: str) -> str:
    """Clean HTML entities and extra whitespace."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_date(date_str: str) -> Optional[str]:
    """Parse date from format 'Month Day, Year' to YYYY-MM-DD."""
    pattern = r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})"
    match = re.search(pattern, date_str)

    if match:
        month_name = match.group(1).lower()
        day = match.group(2).zfill(2)
        year = match.group(3)

        month = MONTHS.get(month_name)
        if month:
            return f"{year}-{month}-{day}"

    return None


def _extract_articles_from_html(
    html_content: str, start_date: datetime, end_date: datetime
) -> list[dict]:
    """Extract article information from the AI News website HTML."""
    articles = []

    article_pattern = r'<a[^>]+href="(https://www\.artificialintelligence-news\.com/[^"]+)"[^>]*>\s*([^<]+)\s*</a>'
    date_pattern = r"([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})"

    seen_urls: set[str] = set()

    for match in re.finditer(article_pattern, html_content):
        url = match.group(1)
        title = _clean_text(match.group(2))

        if url in seen_urls or len(title) < 10:
            continue

        if "/category/" in url or "/tag/" in url or "/page/" in url:
            continue

        seen_urls.add(url)

        # Try to find a date near this article
        start_pos = max(0, match.start() - 500)
        end_pos = min(len(html_content), match.end() + 500)
        context = html_content[start_pos:end_pos]

        date_match = re.search(date_pattern, context)
        item_date = None

        if date_match:
            item_date = _parse_date(date_match.group(1))

        if item_date:
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d")
                if start_date <= parsed_date <= end_date:
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": "ai-news",
                        "date": item_date,
                        "tags": ["industry", "news"],
                    })
            except ValueError:
                continue

    return articles


def _fetch_page(url: str) -> str:
    """Fetch a page and return its HTML content."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8")


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    # Fetch main page
    try:
        content = _fetch_page("https://www.artificialintelligence-news.com/")
        articles = _extract_articles_from_html(content, start_date, end_date)
        for article in articles:
            if article["url"] not in seen_urls:
                all_articles.append(article)
                seen_urls.add(article["url"])
    except Exception:
        pass

    # Also try the news category page
    try:
        content = _fetch_page(
            "https://www.artificialintelligence-news.com/categories/ai-news/"
        )
        articles = _extract_articles_from_html(content, start_date, end_date)
        for article in articles:
            if article["url"] not in seen_urls:
                all_articles.append(article)
                seen_urls.add(article["url"])
    except Exception:
        pass

    return all_articles


async def fetch(days: int = 7) -> FetchResult:
    """Fetch news from artificialintelligence-news.com for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="ai-news",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://www.artificialintelligence-news.com/",
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="ai-news",
            items=[],
            error=str(e),
        )
