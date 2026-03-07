"""Fetch AI discussions from Reddit AI communities."""

import asyncio
import json
import urllib.request
from datetime import datetime, timedelta

from ai_news.fetchers.base import FetchResult


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
    """Fetch posts from a subreddit using Reddit's JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "AI-News-Bot/1.0 (Educational Research)"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        return data.get("data", {}).get("children", [])

    except Exception:
        return []


def _process_post(post_data: dict, subreddit: str) -> dict:
    """Convert Reddit post to standard format."""
    data = post_data.get("data", {})

    created_utc = data.get("created_utc", 0)
    created_date = datetime.fromtimestamp(created_utc)

    flair = data.get("link_flair_text", "") or ""
    title = data.get("title", "")

    post_type = "discussion"
    if "[R]" in title or "research" in flair.lower():
        post_type = "research"
    elif "[P]" in title or "project" in flair.lower():
        post_type = "project"
    elif "[D]" in title or "discussion" in flair.lower():
        post_type = "discussion"
    elif "[N]" in title or "news" in flair.lower():
        post_type = "news"

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
        "post_type": post_type,
        "selftext_preview": (data.get("selftext", "") or "")[:300],
        "tags": ["community", "sentiment", subreddit],
    }


def analyze_sentiment(items: list[dict]) -> dict:
    """Analyze overall community sentiment from posts."""
    if not items:
        return {"overall": "neutral", "topics": []}

    # Count post types
    type_counts: dict[str, int] = {}
    for item in items:
        pt = item.get("post_type", "discussion")
        type_counts[pt] = type_counts.get(pt, 0) + 1

    # Extract common topics from titles
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

    avg_score = sum(i["score"] for i in items) / len(items)
    avg_comments = sum(i["comments"] for i in items) / len(items)

    return {
        "post_type_distribution": type_counts,
        "hot_topics": [t[0] for t in top_topics],
        "avg_score": round(avg_score, 1),
        "avg_comments": round(avg_comments, 1),
        "total_posts": len(items),
    }


def _fetch_sync(days: int) -> list[dict]:
    """Synchronous fetch logic."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    all_posts: dict[str, dict] = {}

    for subreddit, sort in SUBREDDITS:
        posts = _fetch_subreddit(subreddit, sort, limit=50)

        for post_data in posts:
            data = post_data.get("data", {})
            post_id = data.get("id")

            if not post_id or post_id in all_posts:
                continue

            created_utc = data.get("created_utc", 0)
            created_date = datetime.fromtimestamp(created_utc)

            if not (start_date <= created_date <= end_date):
                continue

            processed = _process_post(post_data, subreddit)
            all_posts[post_id] = processed

    # Sort by score descending
    return sorted(all_posts.values(), key=lambda x: x["score"], reverse=True)


async def fetch(days: int = 7) -> FetchResult:
    """Fetch AI discussions from Reddit for the past N days."""
    try:
        items = await asyncio.to_thread(_fetch_sync, days)
        sentiment = analyze_sentiment(items)
        return FetchResult(
            source="reddit",
            items=items,
            items_found=len(items),
            metadata={
                "subreddits": SUBREDDIT_NAMES,
                "community_sentiment": sentiment,
                "days_requested": days,
                "fetch_date": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        return FetchResult(
            source="reddit",
            items=[],
            error=str(e),
        )
