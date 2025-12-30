#!/usr/bin/env python3
"""
Fetch news from artificialintelligence-news.com website.
Parses the WordPress-based site for recent AI news articles.
"""

import argparse
import json
import sys
import re
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import html


# Month name to number mapping
MONTHS = {
    'january': '01', 'february': '02', 'march': '03', 'april': '04',
    'may': '05', 'june': '06', 'july': '07', 'august': '08',
    'september': '09', 'october': '10', 'november': '11', 'december': '12'
}


def clean_text(text: str) -> str:
    """Clean HTML entities and extra whitespace."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_date(date_str: str) -> Optional[str]:
    """
    Parse date from format "Month Day, Year" (e.g., "December 23, 2025").
    Returns ISO format YYYY-MM-DD.
    """
    pattern = r'([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})'
    match = re.search(pattern, date_str)

    if match:
        month_name = match.group(1).lower()
        day = match.group(2).zfill(2)
        year = match.group(3)

        month = MONTHS.get(month_name)
        if month:
            return f"{year}-{month}-{day}"

    return None


def extract_articles_from_html(html_content: str, start_date: datetime, end_date: datetime) -> list:
    """
    Extract article information from the AI News website HTML.
    """
    articles = []

    # Pattern to find article blocks with title, link, and date
    # Looking for h2/h3 titles with links and nearby date text

    # Find article links (usually in h2 or h3 tags)
    article_pattern = r'<a[^>]+href="(https://www\.artificialintelligence-news\.com/[^"]+)"[^>]*>\s*([^<]+)\s*</a>'

    # Also try to find date patterns in the content
    date_pattern = r'([A-Z][a-z]+\s+\d{1,2},?\s+\d{4})'

    # Find all potential articles
    seen_urls = set()

    for match in re.finditer(article_pattern, html_content):
        url = match.group(1)
        title = clean_text(match.group(2))

        # Skip if we've seen this URL or if title is too short
        if url in seen_urls or len(title) < 10:
            continue

        # Skip non-article URLs
        if '/category/' in url or '/tag/' in url or '/page/' in url:
            continue

        seen_urls.add(url)

        # Try to find a date near this article
        # Look for dates in a window around the match
        start_pos = max(0, match.start() - 500)
        end_pos = min(len(html_content), match.end() + 500)
        context = html_content[start_pos:end_pos]

        date_match = re.search(date_pattern, context)
        item_date = None

        if date_match:
            item_date = parse_date(date_match.group(1))

        if item_date:
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d")
                if start_date <= parsed_date <= end_date:
                    articles.append({
                        "title": title,
                        "url": url,
                        "source": "ai-news",
                        "date": item_date,
                        "tags": ["industry", "news"]
                    })
            except ValueError:
                continue

    return articles


def fetch_ai_news(days: int = 7) -> list:
    """
    Fetch news from artificialintelligence-news.com for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of article items
    """
    base_url = "https://www.artificialintelligence-news.com/"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    all_articles = []

    try:
        req = urllib.request.Request(
            base_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'text/html,application/xhtml+xml'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')

        articles = extract_articles_from_html(content, start_date, end_date)
        all_articles.extend(articles)

    except Exception as e:
        print(f"Error fetching AI News: {e}", file=sys.stderr)

    # Also try the news category page
    try:
        news_url = "https://www.artificialintelligence-news.com/categories/ai-news/"
        req = urllib.request.Request(
            news_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'text/html,application/xhtml+xml'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8')

        articles = extract_articles_from_html(content, start_date, end_date)

        # Deduplicate
        seen_urls = {a["url"] for a in all_articles}
        for article in articles:
            if article["url"] not in seen_urls:
                all_articles.append(article)
                seen_urls.add(article["url"])

    except Exception as e:
        print(f"Error fetching AI News category page: {e}", file=sys.stderr)

    return all_articles


def main():
    parser = argparse.ArgumentParser(description='Fetch news from artificialintelligence-news.com')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')

    args = parser.parse_args()

    items = fetch_ai_news(args.days)

    output = {
        "source": "ai-news",
        "source_url": "https://www.artificialintelligence-news.com/",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
