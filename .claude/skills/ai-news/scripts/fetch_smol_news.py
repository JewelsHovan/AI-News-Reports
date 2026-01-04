#!/usr/bin/env python3
"""
Fetch AI news from smol.ai newsletter RSS feed.
Returns structured JSON of news items within the specified date range.

Extracts rich metadata including:
- Coverage metrics (subreddits, twitters, discords)
- Tags (companies, topics, people)
- Linked resources (Twitter, Reddit, arXiv, GitHub)
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request
import xml.etree.ElementTree as ET
import re
import html


# XML namespace for content:encoded
CONTENT_NS = {'content': 'http://purl.org/rss/1.0/modules/content/'}


def parse_date_from_title(title: str, current_year: int) -> Optional[str]:
    """Extract date from title like 'AI News Dec 22' or similar patterns."""
    months = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
        'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
        'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }

    # Try patterns like "Dec 22" or "December 22"
    pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})'
    match = re.search(pattern, title.lower())
    if match:
        month = months[match.group(1)[:3]]
        day = match.group(2).zfill(2)
        return f"{current_year}-{month}-{day}"
    return None


def parse_date_from_link(link: str) -> Optional[str]:
    """Extract date from URL pattern /issues/YY-MM-DD-slug."""
    pattern = r'/issues/(\d{2})-(\d{2})-(\d{2})'
    match = re.search(pattern, link)
    if match:
        year = f"20{match.group(1)}"
        month = match.group(2)
        day = match.group(3)
        return f"{year}-{month}-{day}"
    return None


def clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def extract_coverage_metrics(content: str) -> dict:
    """
    Extract coverage metrics from content like:
    '12 subreddits, 544 Twitters, 24 Discords (205 channels, 3051 messages)'
    """
    metrics = {
        "subreddits": 0,
        "twitters": 0,
        "discords": 0,
        "channels": 0,
        "messages": 0
    }

    # Pattern: "X subreddits"
    match = re.search(r'(\d+)\s+subreddits?', content, re.I)
    if match:
        metrics["subreddits"] = int(match.group(1))

    # Pattern: "X Twitters"
    match = re.search(r'(\d+)\s+twitters?', content, re.I)
    if match:
        metrics["twitters"] = int(match.group(1))

    # Pattern: "X Discords"
    match = re.search(r'(\d+)\s+discords?', content, re.I)
    if match:
        metrics["discords"] = int(match.group(1))

    # Pattern: "X channels"
    match = re.search(r'(\d+)\s+channels?', content, re.I)
    if match:
        metrics["channels"] = int(match.group(1))

    # Pattern: "X messages"
    match = re.search(r'(\d+)\s+messages?', content, re.I)
    if match:
        metrics["messages"] = int(match.group(1))

    return metrics


def extract_twitter_links(content: str) -> list:
    """Extract Twitter/X links with surrounding context."""
    links = []
    # Match twitter.com or x.com status URLs
    pattern = r'https?://(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)'

    for match in re.finditer(pattern, content):
        url = match.group(0)
        handle = match.group(1)
        # Avoid duplicates
        if not any(l["url"] == url for l in links):
            links.append({
                "url": url,
                "handle": f"@{handle}" if not handle.startswith('@') else handle
            })

    return links


def extract_reddit_links(content: str) -> list:
    """Extract Reddit post links."""
    links = []
    # Match reddit.com post URLs
    pattern = r'https?://(?:www\.)?reddit\.com/r/([^/]+)/comments/([^/]+)'

    for match in re.finditer(pattern, content):
        url = match.group(0)
        subreddit = match.group(1)
        # Clean URL (remove trailing parts after the post ID if needed)
        clean_url = re.match(r'(https?://(?:www\.)?reddit\.com/r/[^/]+/comments/[^/]+/[^/]*)', url)
        if clean_url:
            url = clean_url.group(1)
        # Avoid duplicates
        if not any(l["url"] == url for l in links):
            links.append({
                "url": url,
                "subreddit": f"r/{subreddit}"
            })

    return links


def extract_arxiv_links(content: str) -> list:
    """Extract arXiv paper links."""
    links = []
    # Match arxiv.org URLs (abs or pdf)
    pattern = r'https?://arxiv\.org/(?:abs|pdf)/(\d+\.\d+)'

    for match in re.finditer(pattern, content):
        paper_id = match.group(1)
        url = f"https://arxiv.org/abs/{paper_id}"
        # Avoid duplicates
        if not any(l["url"] == url for l in links):
            links.append({
                "url": url,
                "paper_id": paper_id
            })

    return links


def extract_github_links(content: str) -> list:
    """Extract GitHub repository links."""
    links = []
    # Match github.com repo URLs (exclude API/raw/etc paths)
    pattern = r'https?://github\.com/([^/]+)/([^/\s<>"\']+)'

    for match in re.finditer(pattern, content):
        owner = match.group(1)
        repo = match.group(2).rstrip('/')
        # Skip non-repo paths
        if owner in ('settings', 'notifications', 'pulls', 'issues', 'marketplace'):
            continue
        url = f"https://github.com/{owner}/{repo}"
        # Avoid duplicates
        if not any(l["url"] == url for l in links):
            links.append({
                "url": url,
                "owner": owner,
                "repo": repo
            })

    return links


def extract_tags_from_content(content: str) -> dict:
    """
    Extract tags from the newsletter content.
    Looks for patterns like company names, @handles, and topic keywords.
    """
    tags = {
        "companies": [],
        "people": [],
        "topics": []
    }

    # Known AI companies to look for
    known_companies = [
        'openai', 'anthropic', 'google', 'deepmind', 'meta', 'microsoft',
        'nvidia', 'deepseek', 'bytedance', 'mistral', 'cohere', 'stability',
        'huggingface', 'together', 'replicate', 'perplexity', 'character.ai',
        'inflection', 'xai', 'groq', 'cerebras', 'anyscale', 'modal',
        'fireworks', 'databricks', 'snowflake', 'aws', 'amazon'
    ]

    content_lower = content.lower()
    for company in known_companies:
        if re.search(rf'\b{re.escape(company)}\b', content_lower):
            tags["companies"].append(company)

    # Extract @handles (Twitter/X)
    handles = re.findall(r'@([a-zA-Z0-9_]{1,15})\b', content)
    # Deduplicate and limit
    seen = set()
    for h in handles:
        h_lower = h.lower()
        if h_lower not in seen and len(tags["people"]) < 20:
            seen.add(h_lower)
            tags["people"].append(f"@{h}")

    # Extract technical topics from headers or emphasized text
    # Look for text in strong/b tags or h2/h3 headers
    topic_patterns = [
        r'<(?:strong|b)>([^<]+)</(?:strong|b)>',
        r'<h[23][^>]*>([^<]+)</h[23]>'
    ]

    for pattern in topic_patterns:
        for match in re.finditer(pattern, content, re.I):
            topic = clean_html(match.group(1)).strip()
            if 3 < len(topic) < 50 and topic not in tags["topics"]:
                tags["topics"].append(topic)
                if len(tags["topics"]) >= 15:
                    break

    return tags


def parse_content_encoded(item_elem) -> Optional[str]:
    """Extract content:encoded from an RSS item element."""
    # Try with namespace
    content_elem = item_elem.find('content:encoded', CONTENT_NS)
    if content_elem is not None and content_elem.text:
        return content_elem.text

    # Try without namespace (some parsers)
    for child in item_elem:
        if 'encoded' in child.tag.lower():
            if child.text:
                return child.text

    return None


def fetch_smol_news(days: int = 7) -> list:
    """
    Fetch news from smol.ai RSS feed for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        List of news items with rich metadata including:
        - title, url, date, summary, source
        - coverage_metrics: counts of sources aggregated
        - tags: companies, people, topics mentioned
        - linked_resources: twitter, reddit, arxiv, github links
    """
    rss_url = "https://news.smol.ai/rss.xml"

    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    current_year = end_date.year

    items = []

    try:
        req = urllib.request.Request(
            rss_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; AI-News-Bot/1.0)',
                'Accept': 'application/rss+xml, application/xml, text/xml'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            rss_content = response.read().decode('utf-8')

        root = ET.fromstring(rss_content)

        # Find all items in the RSS feed
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            pub_date_elem = item.find('pubDate')

            if title_elem is None or link_elem is None:
                continue

            title = title_elem.text or ""
            link = link_elem.text or ""
            description = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""

            # Get the full content:encoded field
            full_content = parse_content_encoded(item) or ""

            # Try to extract date from link first, then title
            item_date = parse_date_from_link(link) or parse_date_from_title(title, current_year)

            # If we have a pubDate, parse it
            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    # RSS date format: "Mon, 23 Dec 2024 00:00:00 GMT"
                    pub_date = datetime.strptime(
                        pub_date_elem.text[:16], "%a, %d %b %Y"
                    ).date()
                    item_date = pub_date.isoformat()
                except (ValueError, IndexError):
                    pass

            if not item_date:
                continue

            # Check if within date range
            try:
                parsed_date = datetime.strptime(item_date, "%Y-%m-%d").date()
                if start_date <= parsed_date <= end_date:
                    # Extract rich metadata from full content
                    content_to_parse = full_content or description

                    # Build enhanced item
                    news_item = {
                        "title": title,
                        "url": link,
                        "source": "smol.ai",
                        "date": item_date,
                        "summary": description[:500] if description else "",
                        "tags": ["newsletter", "ai-digest"],
                    }

                    # Add coverage metrics
                    metrics = extract_coverage_metrics(content_to_parse)
                    if any(v > 0 for v in metrics.values()):
                        news_item["coverage_metrics"] = metrics

                    # Add extracted tags
                    extracted_tags = extract_tags_from_content(content_to_parse)
                    if extracted_tags["companies"]:
                        news_item["companies"] = extracted_tags["companies"]
                    if extracted_tags["people"]:
                        news_item["people"] = extracted_tags["people"]
                    if extracted_tags["topics"]:
                        news_item["topics"] = extracted_tags["topics"]

                    # Add linked resources
                    linked_resources = {}

                    twitter_links = extract_twitter_links(content_to_parse)
                    if twitter_links:
                        linked_resources["twitter"] = twitter_links

                    reddit_links = extract_reddit_links(content_to_parse)
                    if reddit_links:
                        linked_resources["reddit"] = reddit_links

                    arxiv_links = extract_arxiv_links(content_to_parse)
                    if arxiv_links:
                        linked_resources["arxiv"] = arxiv_links

                    github_links = extract_github_links(content_to_parse)
                    if github_links:
                        linked_resources["github"] = github_links

                    if linked_resources:
                        news_item["linked_resources"] = linked_resources

                    items.append(news_item)
            except ValueError:
                continue

    except Exception as e:
        print(f"Error fetching smol.ai news: {e}", file=sys.stderr)
        return []

    return items


def main():
    parser = argparse.ArgumentParser(description='Fetch AI news from smol.ai newsletter')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON (default)')

    args = parser.parse_args()

    items = fetch_smol_news(args.days)

    output = {
        "source": "smol.ai",
        "source_url": "https://news.smol.ai/",
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "items_found": len(items),
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
