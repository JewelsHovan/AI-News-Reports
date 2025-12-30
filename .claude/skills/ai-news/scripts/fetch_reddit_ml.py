#!/usr/bin/env python3
"""
Fetch AI discussions from Reddit r/MachineLearning and r/LocalLLaMA.
Captures community sentiment, hot discussions, and emerging trends.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Optional
import urllib.request


def fetch_subreddit(subreddit: str, sort: str = "hot", limit: int = 50) -> list:
    """
    Fetch posts from a subreddit using Reddit's JSON API.

    Args:
        subreddit: Name of the subreddit
        sort: Sort method (hot, new, top)
        limit: Number of posts to fetch

    Returns:
        List of post data
    """
    url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit={limit}"

    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'AI-News-Bot/1.0 (Educational Research)'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))

        return data.get('data', {}).get('children', [])

    except Exception as e:
        print(f"Error fetching r/{subreddit}: {e}", file=sys.stderr)
        return []


def process_post(post_data: dict, subreddit: str) -> dict:
    """Convert Reddit post to standard format."""
    data = post_data.get('data', {})

    created_utc = data.get('created_utc', 0)
    created_date = datetime.fromtimestamp(created_utc)

    # Determine post type based on flair or content
    flair = data.get('link_flair_text', '') or ''
    title = data.get('title', '')

    post_type = 'discussion'
    if '[R]' in title or 'research' in flair.lower():
        post_type = 'research'
    elif '[P]' in title or 'project' in flair.lower():
        post_type = 'project'
    elif '[D]' in title or 'discussion' in flair.lower():
        post_type = 'discussion'
    elif '[N]' in title or 'news' in flair.lower():
        post_type = 'news'

    return {
        "title": data.get('title', ''),
        "url": f"https://reddit.com{data.get('permalink', '')}",
        "external_url": data.get('url', ''),
        "source": f"reddit_{subreddit}",
        "date": created_date.strftime("%Y-%m-%d"),
        "score": data.get('score', 0),
        "comments": data.get('num_comments', 0),
        "upvote_ratio": data.get('upvote_ratio', 0),
        "author": data.get('author', '[deleted]'),
        "flair": flair,
        "post_type": post_type,
        "selftext_preview": (data.get('selftext', '') or '')[:300],
        "tags": ["community", "sentiment", subreddit]
    }


def fetch_reddit_ml(days: int = 7, min_score: int = 50) -> list:
    """
    Fetch AI discussions from Reddit for the past N days.

    Args:
        days: Number of days to look back
        min_score: Minimum score threshold for relevance

    Returns:
        List of discussion items
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    # Subreddits to check
    subreddits = [
        ('MachineLearning', 'hot'),
        ('MachineLearning', 'top'),
        ('LocalLLaMA', 'hot'),
        ('artificial', 'hot'),
    ]

    all_posts = {}

    for subreddit, sort in subreddits:
        posts = fetch_subreddit(subreddit, sort, limit=50)

        for post_data in posts:
            data = post_data.get('data', {})
            post_id = data.get('id')

            if not post_id or post_id in all_posts:
                continue

            # Check date range
            created_utc = data.get('created_utc', 0)
            created_date = datetime.fromtimestamp(created_utc)

            if not (start_date <= created_date <= end_date):
                continue

            # Check minimum score
            score = data.get('score', 0)
            if score < min_score:
                continue

            processed = process_post(post_data, subreddit)
            all_posts[post_id] = processed

    # Sort by score descending
    items = sorted(all_posts.values(), key=lambda x: x['score'], reverse=True)

    return items


def analyze_sentiment(items: list) -> dict:
    """Analyze overall community sentiment from posts."""
    if not items:
        return {"overall": "neutral", "topics": []}

    # Count post types
    type_counts = {}
    for item in items:
        pt = item.get('post_type', 'discussion')
        type_counts[pt] = type_counts.get(pt, 0) + 1

    # Extract common topics from titles
    topic_keywords = {}
    keywords = ['gpt', 'llama', 'claude', 'openai', 'anthropic', 'google',
                'fine-tuning', 'rag', 'agent', 'benchmark', 'open source',
                'local', 'inference', 'training', 'reasoning']

    for item in items:
        title_lower = item['title'].lower()
        for kw in keywords:
            if kw in title_lower:
                topic_keywords[kw] = topic_keywords.get(kw, 0) + 1

    top_topics = sorted(topic_keywords.items(), key=lambda x: x[1], reverse=True)[:5]

    # Calculate average engagement
    avg_score = sum(i['score'] for i in items) / len(items)
    avg_comments = sum(i['comments'] for i in items) / len(items)

    return {
        "post_type_distribution": type_counts,
        "hot_topics": [t[0] for t in top_topics],
        "avg_score": round(avg_score, 1),
        "avg_comments": round(avg_comments, 1),
        "total_posts": len(items)
    }


def main():
    parser = argparse.ArgumentParser(description='Fetch AI discussions from Reddit')
    parser.add_argument('days', type=int, nargs='?', default=7,
                        help='Number of days to look back (default: 7)')
    parser.add_argument('--min-score', type=int, default=50,
                        help='Minimum score threshold (default: 50)')

    args = parser.parse_args()

    items = fetch_reddit_ml(args.days, args.min_score)
    sentiment = analyze_sentiment(items)

    output = {
        "source": "reddit",
        "subreddits": ["MachineLearning", "LocalLLaMA", "artificial"],
        "fetch_date": datetime.now().isoformat(),
        "days_requested": args.days,
        "min_score_filter": args.min_score,
        "items_found": len(items),
        "community_sentiment": sentiment,
        "items": items
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
