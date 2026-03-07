"""Fetch AI news from smol.ai newsletter RSS feed.

Extracts rich metadata including coverage metrics, tags, and linked resources.
"""

import asyncio
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional

from ai_news.fetchers.base import FetchResult


# XML namespace for content:encoded
CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}


def _parse_date_from_title(title: str, current_year: int) -> Optional[str]:
    """Extract date from title like 'AI News Dec 22' or similar patterns."""
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }

    pattern = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})"
    match = re.search(pattern, title.lower())
    if match:
        month = months[match.group(1)[:3]]
        day = match.group(2).zfill(2)
        return f"{current_year}-{month}-{day}"
    return None


def _parse_date_from_link(link: str) -> Optional[str]:
    """Extract date from URL pattern /issues/YY-MM-DD-slug."""
    pattern = r"/issues/(\d{2})-(\d{2})-(\d{2})"
    match = re.search(pattern, link)
    if match:
        year = f"20{match.group(1)}"
        month = match.group(2)
        day = match.group(3)
        return f"{year}-{month}-{day}"
    return None


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


def _extract_coverage_metrics(content: str) -> dict:
    """Extract coverage metrics from content."""
    metrics = {
        "subreddits": 0,
        "twitters": 0,
        "discords": 0,
        "channels": 0,
        "messages": 0,
    }

    for key in metrics:
        match = re.search(rf"(\d+)\s+{key}?", content, re.I)
        if match:
            metrics[key] = int(match.group(1))

    return metrics


def _extract_twitter_links(content: str) -> list[dict]:
    """Extract Twitter/X links with surrounding context."""
    links: list[dict] = []
    pattern = r"https?://(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)"

    for match in re.finditer(pattern, content):
        url = match.group(0)
        handle = match.group(1)
        if not any(link["url"] == url for link in links):
            links.append({
                "url": url,
                "handle": f"@{handle}" if not handle.startswith("@") else handle,
            })

    return links


def _extract_reddit_links(content: str) -> list[dict]:
    """Extract Reddit post links."""
    links: list[dict] = []
    pattern = r"https?://(?:www\.)?reddit\.com/r/([^/]+)/comments/([^/]+)"

    for match in re.finditer(pattern, content):
        url = match.group(0)
        subreddit = match.group(1)
        clean_url = re.match(
            r"(https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^/]+/[^/]*)", url
        )
        if clean_url:
            url = clean_url.group(1)
        if not any(link["url"] == url for link in links):
            links.append({"url": url, "subreddit": f"r/{subreddit}"})

    return links


def _extract_arxiv_links(content: str) -> list[dict]:
    """Extract arXiv paper links."""
    links: list[dict] = []
    pattern = r"https?://arxiv\.org/(?:abs|pdf)/(\d+\.\d+)"

    for match in re.finditer(pattern, content):
        paper_id = match.group(1)
        url = f"https://arxiv.org/abs/{paper_id}"
        if not any(link["url"] == url for link in links):
            links.append({"url": url, "paper_id": paper_id})

    return links


def _extract_github_links(content: str) -> list[dict]:
    """Extract GitHub repository links."""
    links: list[dict] = []
    pattern = r'https?://github\.com/([^/]+)/([^/\s<>"\']+)'

    skip_owners = {
        "settings", "notifications", "pulls", "issues", "marketplace",
    }

    for match in re.finditer(pattern, content):
        owner = match.group(1)
        repo = match.group(2).rstrip("/")
        if owner in skip_owners:
            continue
        url = f"https://github.com/{owner}/{repo}"
        if not any(link["url"] == url for link in links):
            links.append({"url": url, "owner": owner, "repo": repo})

    return links


def _extract_tags_from_content(content: str) -> dict:
    """Extract tags from newsletter content."""
    tags: dict[str, list] = {
        "companies": [],
        "people": [],
        "topics": [],
    }

    known_companies = [
        "openai", "anthropic", "google", "deepmind", "meta", "microsoft",
        "nvidia", "deepseek", "bytedance", "mistral", "cohere", "stability",
        "huggingface", "together", "replicate", "perplexity", "character.ai",
        "inflection", "xai", "groq", "cerebras", "anyscale", "modal",
        "fireworks", "databricks", "snowflake", "aws", "amazon",
    ]

    content_lower = content.lower()
    for company in known_companies:
        if re.search(rf"\b{re.escape(company)}\b", content_lower):
            tags["companies"].append(company)

    # Extract @handles
    handles = re.findall(r"@([a-zA-Z0-9_]{1,15})\b", content)
    seen: set[str] = set()
    for h in handles:
        h_lower = h.lower()
        if h_lower not in seen and len(tags["people"]) < 20:
            seen.add(h_lower)
            tags["people"].append(f"@{h}")

    # Extract topics from headers or emphasized text
    topic_patterns = [
        r"<(?:strong|b)>([^<]+)</(?:strong|b)>",
        r"<h[23][^>]*>([^<]+)</h[23]>",
    ]

    for pattern in topic_patterns:
        for match in re.finditer(pattern, content, re.I):
            topic = _clean_html(match.group(1)).strip()
            if 3 < len(topic) < 50 and topic not in tags["topics"]:
                tags["topics"].append(topic)
                if len(tags["topics"]) >= 15:
                    break

    return tags


def _parse_content_encoded(item_elem: ET.Element) -> Optional[str]:
    """Extract content:encoded from an RSS item element."""
    content_elem = item_elem.find("content:encoded", CONTENT_NS)
    if content_elem is not None and content_elem.text:
        return content_elem.text

    for child in item_elem:
        if "encoded" in child.tag.lower():
            if child.text:
                return child.text

    return None


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    rss_url = "https://news.smol.ai/rss.xml"

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    current_year = end_date.year

    items: list[dict] = []

    req = urllib.request.Request(
        rss_url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)",
            "Accept": "application/rss+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        rss_content = response.read().decode("utf-8")

    root = ET.fromstring(rss_content)

    for item in root.findall(".//item"):
        title_elem = item.find("title")
        link_elem = item.find("link")
        desc_elem = item.find("description")
        pub_date_elem = item.find("pubDate")

        if title_elem is None or link_elem is None:
            continue

        title = title_elem.text or ""
        link = link_elem.text or ""
        description = (
            _clean_html(desc_elem.text)
            if desc_elem is not None and desc_elem.text
            else ""
        )

        full_content = _parse_content_encoded(item) or ""

        # Try to extract date from link first, then title
        item_date = _parse_date_from_link(link) or _parse_date_from_title(
            title, current_year
        )

        # If we have a pubDate, parse it
        if pub_date_elem is not None and pub_date_elem.text:
            try:
                pub_date = datetime.strptime(
                    pub_date_elem.text[:16], "%a, %d %b %Y"
                ).date()
                item_date = pub_date.isoformat()
            except (ValueError, IndexError):
                pass

        if not item_date:
            continue

        try:
            parsed_date = datetime.strptime(item_date, "%Y-%m-%d").date()
            if not (start_date <= parsed_date <= end_date):
                continue
        except ValueError:
            continue

        content_to_parse = full_content or description

        news_item: dict = {
            "title": title,
            "url": link,
            "source": "smol.ai",
            "date": item_date,
            "summary": description[:500] if description else "",
            "tags": ["newsletter", "ai-digest"],
        }

        # Add coverage metrics
        metrics = _extract_coverage_metrics(content_to_parse)
        if any(v > 0 for v in metrics.values()):
            news_item["coverage_metrics"] = metrics

        # Add extracted tags
        extracted_tags = _extract_tags_from_content(content_to_parse)
        if extracted_tags["companies"]:
            news_item["companies"] = extracted_tags["companies"]
        if extracted_tags["people"]:
            news_item["people"] = extracted_tags["people"]
        if extracted_tags["topics"]:
            news_item["topics"] = extracted_tags["topics"]

        # Add linked resources
        linked_resources: dict = {}

        twitter_links = _extract_twitter_links(content_to_parse)
        if twitter_links:
            linked_resources["twitter"] = twitter_links

        reddit_links = _extract_reddit_links(content_to_parse)
        if reddit_links:
            linked_resources["reddit"] = reddit_links

        arxiv_links = _extract_arxiv_links(content_to_parse)
        if arxiv_links:
            linked_resources["arxiv"] = arxiv_links

        github_links = _extract_github_links(content_to_parse)
        if github_links:
            linked_resources["github"] = github_links

        if linked_resources:
            news_item["linked_resources"] = linked_resources

        items.append(news_item)

    return items


async def fetch(days: int = 7) -> FetchResult:
    """Fetch news from smol.ai newsletter for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="smol.ai",
            items=items,
            items_found=len(items),
            metadata={
                "source_url": "https://news.smol.ai/",
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="smol.ai",
            items=[],
            error=str(e),
        )
