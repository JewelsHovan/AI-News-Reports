"""Fetch AI news from The Batch newsletter by Andrew Ng (DeepLearning.AI)."""

import asyncio
import html
import re
import urllib.request
from datetime import datetime, timedelta

from ai_news.fetchers.base import FetchResult


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()



def _extract_articles_from_html(
    html_content: str, start_date: datetime, end_date: datetime
) -> list[dict]:
    """Extract article information from The Batch page."""
    articles = []

    article_pattern = r'<a[^>]+href="(https://www\.deeplearning\.ai/the-batch/[^"]+)"[^>]*>\s*<[^>]+>([^<]+)</[^>]+>'
    date_pattern = r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4})"

    seen_urls: set[str] = set()

    # Extract from article links
    for match in re.finditer(article_pattern, html_content, re.IGNORECASE):
        url = match.group(1)
        title = _clean_html(match.group(2))

        if url in seen_urls or len(title) < 10:
            continue

        if "/tag/" in url or "/page/" in url:
            continue

        seen_urls.add(url)

        # Try to find date near this match
        start_pos = max(0, match.start() - 1000)
        end_pos = min(len(html_content), match.end() + 1000)
        context = html_content[start_pos:end_pos]

        date_match = re.search(date_pattern, context)
        item_date = None

        if date_match:
            try:
                date_str = date_match.group(1).replace(",", "")
                dt = datetime.strptime(date_str, "%b %d %Y")
                item_date = dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        if item_date:
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d")
                if start_date <= parsed_date <= end_date:
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": "the_batch",
                        "date": item_date,
                        "author": "Andrew Ng / DeepLearning.AI",
                        "tags": ["expert", "analysis", "newsletter"],
                    })
            except ValueError:
                continue

    # Also try a simpler pattern for issue titles
    issue_pattern = r'/the-batch/([^/]+)/["\']'
    title_nearby_pattern = r">([^<]{20,100})</(?:h[1-3]|a|span)"

    for match in re.finditer(issue_pattern, html_content):
        slug = match.group(1)
        url = f"https://www.deeplearning.ai/the-batch/{slug}/"

        if url in seen_urls:
            continue

        start_pos = max(0, match.start() - 500)
        end_pos = min(len(html_content), match.end() + 500)
        context = html_content[start_pos:end_pos]

        title_match = re.search(title_nearby_pattern, context)
        if title_match:
            title = _clean_html(title_match.group(1))
            if len(title) > 15:
                seen_urls.add(url)
                articles.append({
                    "title": title,
                    "url": url,
                    "source": "the_batch",
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "author": "Andrew Ng / DeepLearning.AI",
                    "tags": ["expert", "analysis", "newsletter"],
                })

    return articles


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    base_url = "https://www.deeplearning.ai/the-batch/"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    all_articles: list[dict] = []

    pages_to_check = [
        base_url,
        f"{base_url}page/2/",
    ]

    for page_url in pages_to_check:
        try:
            req = urllib.request.Request(
                page_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read().decode("utf-8")

            articles = _extract_articles_from_html(content, start_date, end_date)

            seen_urls = {a["url"] for a in all_articles}
            for article in articles:
                if article["url"] not in seen_urls:
                    all_articles.append(article)
                    seen_urls.add(article["url"])

        except Exception:
            continue

    return all_articles


async def fetch(days: int = 7) -> FetchResult:
    """Fetch articles from The Batch newsletter for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="the_batch",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://www.deeplearning.ai/the-batch/",
                "expert": "Andrew Ng",
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="the_batch",
            items=[],
            error=str(e),
        )
