"""Fetch AI discussions from Reddit AI communities."""

import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from ai_news.fetchers.base import FetchResult

logger = logging.getLogger(__name__)
USER_AGENT = "AI-News-Bot/1.0 (Educational Research)"
ATOM = "{http://www.w3.org/2005/Atom}"

# Keep the RSS trial small: unauthenticated feeds are rate-limited and do not
# expose scores or comment counts. Authenticated API access is the long-term fix.
RSS_SUBREDDITS = ("LocalLLaMA", "MachineLearning", "ClaudeAI")

# Subreddits and sort methods to check
SUBREDDITS = [
    ("MachineLearning", "hot"),
    ("MachineLearning", "top"),
    ("LocalLLaMA", "hot"),
    ("artificial", "hot"),
    ("ClaudeAI", "hot"),
    ("ClaudeCode", "hot"),
    ("singularity", "hot"),
    ("Bard", "hot"),
    ("PromptEngineering", "hot"),
    ("PromptEngineering", "top"),
    ("ChatGPTPromptGenius", "hot"),
    ("aipromptprogramming", "hot"),
    ("PromptDesign", "hot"),
]

SUBREDDIT_NAMES = sorted(set(s for s, _ in SUBREDDITS))


def _fetch_subreddit(subreddit: str, sort: str = "hot", limit: int = 50) -> list:
    """Fetch posts from Reddit's public JSON listing; raise on access errors."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["data"]["children"]


def _post_type(title: str, flair: str = "") -> str:
    if "[R]" in title or "research" in flair.lower():
        return "research"
    if "[P]" in title or "project" in flair.lower():
        return "project"
    if "[N]" in title or "news" in flair.lower():
        return "news"
    return "discussion"


def _process_post(post_data: dict, subreddit: str) -> dict:
    """Convert Reddit JSON post to standard format."""
    data = post_data.get("data", {})
    created_date = datetime.fromtimestamp(data.get("created_utc", 0), timezone.utc)
    flair = data.get("link_flair_text", "") or ""
    title = data.get("title", "")
    return {
        "title": title,
        "url": f"https://reddit.com{data.get('permalink', '')}",
        "external_url": data.get("url", ""),
        "source": f"reddit_{subreddit}",
        "date": created_date.strftime("%Y-%m-%d"),
        "score": data.get("score", 0),
        "comments": data.get("num_comments", 0),
        "upvote_ratio": data.get("upvote_ratio", 0),
        "author": data.get("author", "[deleted]"),
        "flair": flair,
        "post_type": _post_type(title, flair),
        "selftext_preview": (data.get("selftext", "") or "")[:300],
        "tags": ["community", "sentiment", subreddit],
    }


def _fetch_rss(subreddit: str) -> list[dict]:
    """Read one public Atom feed. Feed data has no engagement metrics."""
    url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as response:
        root = ET.fromstring(response.read())
    entries = []
    for entry in root.findall(f"{ATOM}entry"):
        post_id = entry.findtext(f"{ATOM}id", "")
        title = entry.findtext(f"{ATOM}title", "")
        published = entry.findtext(f"{ATOM}published", "")
        link = entry.find(f"{ATOM}link")
        if not post_id.startswith("t3_") or not title or not published or link is None:
            continue
        created = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(timezone.utc)
        author = entry.findtext(f"{ATOM}author/{ATOM}name", "[deleted]")
        entries.append({
            "id": post_id[3:],
            "created": created,
            "item": {
                "title": title,
                "url": link.get("href", ""),
                "external_url": "",
                "source": f"reddit_{subreddit}",
                "date": created.strftime("%Y-%m-%d"),
                "score": None,
                "comments": None,
                "upvote_ratio": None,
                "author": author,
                "flair": "",
                "post_type": _post_type(title),
                "selftext_preview": "",
                "tags": ["community", "sentiment", subreddit, "rss"],
            },
        })
    return entries


def analyze_sentiment(items: list[dict]) -> dict:
    """Analyze overall community sentiment from posts without inventing metrics."""
    if not items:
        return {"overall": "neutral", "topics": []}

    type_counts: dict[str, int] = {}
    for item in items:
        pt = item.get("post_type", "discussion")
        type_counts[pt] = type_counts.get(pt, 0) + 1

    topic_keywords: dict[str, int] = {}
    keywords = [
        "gpt", "llama", "claude", "openai", "anthropic", "google",
        "fine-tuning", "rag", "agent", "benchmark", "open source",
        "local", "inference", "training", "reasoning", "gemini",
        "bard", "singularity", "agi", "claude code", "mcp",
        "prompt engineering", "context", "vibe coding", "cursor",
        "copilot", "aider", "system prompt", "chain of thought",
    ]
    for item in items:
        title_lower = item["title"].lower()
        for kw in keywords:
            if kw in title_lower:
                topic_keywords[kw] = topic_keywords.get(kw, 0) + 1
    top_topics = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:5]
    scores = [i["score"] for i in items if isinstance(i.get("score"), (int, float))]
    comments = [i["comments"] for i in items if isinstance(i.get("comments"), (int, float))]
    return {
        "post_type_distribution": type_counts,
        "hot_topics": [t[0] for t in top_topics],
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_comments": round(sum(comments) / len(comments), 1) if comments else None,
        "total_posts": len(items),
    }


def _fetch_sync(days: int) -> tuple[list[dict], dict]:
    """Return posts and provenance; report failures instead of hiding them."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)
    all_posts: dict[str, dict] = {}
    json_ok = 0
    errors: list[str] = []

    for subreddit, sort in SUBREDDITS:
        try:
            posts = _fetch_subreddit(subreddit, sort, limit=50)
            json_ok += 1
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            reason = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            logger.warning("Reddit JSON r/%s/%s failed: %s", subreddit, sort, reason)
            errors.append(f"r/{subreddit}/{sort}: {reason}")
            # A site-wide block or rate limit won't improve with 12 more calls.
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 429):
                break
            continue

        for post_data in posts:
            data = post_data.get("data", {})
            post_id = data.get("id")
            if not post_id or post_id in all_posts:
                continue
            created = datetime.fromtimestamp(data.get("created_utc", 0), timezone.utc)
            if start_date <= created <= end_date:
                all_posts[post_id] = _process_post(post_data, subreddit)

    if json_ok:
        return sorted(all_posts.values(), key=lambda x: x["score"], reverse=True), {
            "fetch_method": "json", "successful_listings": json_ok, "listing_errors": errors,
        }

    logger.warning("Reddit JSON unavailable; trying %d small public RSS feeds", len(RSS_SUBREDDITS))
    reachable_feeds: list[str] = []
    for index, subreddit in enumerate(RSS_SUBREDDITS):
        if index:
            time.sleep(2)  # space out feed requests; never retry a rate limit
        try:
            entries = _fetch_rss(subreddit)
            reachable_feeds.append(subreddit)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ET.ParseError, ValueError) as exc:
            reason = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            logger.warning("Reddit RSS r/%s failed: %s", subreddit, reason)
            errors.append(f"RSS r/{subreddit}: {reason}")
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (403, 429):
                break
            continue
        for entry in entries:
            if start_date <= entry["created"] <= end_date:
                all_posts.setdefault(entry["id"], entry["item"])

    if not reachable_feeds or not all_posts:
        raise RuntimeError("Reddit listings unavailable or no recent RSS posts; " + "; ".join(errors[:5]))
    logger.info("Reddit RSS fallback: %d recent posts from %d reachable feeds (engagement unavailable)", len(all_posts), len(reachable_feeds))
    return list(all_posts.values()), {
        "fetch_method": "rss", "successful_listings": len(reachable_feeds),
        "listing_errors": errors, "engagement_available": False,
        "subreddits": reachable_feeds,
    }


async def fetch(days: int = 7) -> FetchResult:
    """Fetch AI discussions from Reddit for the past N days."""
    try:
        items, provenance = await asyncio.to_thread(_fetch_sync, days)
        return FetchResult(
            source="reddit", items=items, items_found=len(items),
            metadata={
                "subreddits": provenance.get("subreddits", SUBREDDIT_NAMES),
                "community_sentiment": analyze_sentiment(items),
                "days_requested": days,
                "fetch_date": datetime.now(timezone.utc).isoformat(),
                **provenance,
            },
        )
    except Exception as exc:
        logger.error("Reddit fetch failed: %s", exc)
        return FetchResult(source="reddit", items=[], error=str(exc))
