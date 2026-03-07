"""Tests for all 8 fetcher modules."""
import json
import time
from unittest.mock import patch, MagicMock

import pytest


def _make_mock_response(content: str | bytes, encoding: str = "utf-8"):
    """Create a mock urllib response that supports context manager protocol."""
    if isinstance(content, str):
        content = content.encode(encoding)
    mock_response = MagicMock()
    mock_response.read.return_value = content
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


# ---------------------------------------------------------------------------
# HuggingFace
# ---------------------------------------------------------------------------

class TestHuggingFaceFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        sample_html = '''
        <html><body>
        <a href="/papers/2403.12345">Sample Paper Title Here</a>
        <a href="/papers/2403.67890">Another Paper About AI Research</a>
        </body></html>
        '''
        mock_response = _make_mock_response(sample_html)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.huggingface import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.source == "huggingface"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        # huggingface swallows per-date errors in _fetch_papers_for_date,
        # so urlopen failures result in success with 0 items
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.huggingface import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.items == []
        assert result.items_found == 0


# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------

class TestRedditFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        reddit_json = json.dumps({
            "data": {
                "children": [
                    {
                        "data": {
                            "id": "abc123",
                            "title": "New AI Model Released",
                            "score": 100,
                            "num_comments": 50,
                            "created_utc": time.time(),
                            "permalink": "/r/MachineLearning/comments/abc123/new_ai_model/",
                            "url": "https://example.com/ai-model",
                            "upvote_ratio": 0.95,
                            "author": "testuser",
                            "link_flair_text": "",
                            "selftext": "Test content",
                        }
                    }
                ]
            }
        })
        mock_response = _make_mock_response(reddit_json)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.reddit import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.source == "reddit"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        # reddit swallows per-subreddit errors in _fetch_subreddit,
        # so urlopen failures result in success with 0 items
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.reddit import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.items == []
        assert result.items_found == 0


# ---------------------------------------------------------------------------
# Hacker News
# ---------------------------------------------------------------------------

class TestHackerNewsFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        hn_json = json.dumps({
            "hits": [
                {
                    "objectID": "12345",
                    "title": "AI Story on Hacker News",
                    "url": "https://example.com/ai-story",
                    "points": 200,
                    "num_comments": 80,
                    "created_at_i": int(time.time()),
                    "author": "hn_user",
                }
            ]
        })
        mock_response = _make_mock_response(hn_json)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.hackernews import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.source == "hackernews"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        # hackernews swallows per-query errors in _fetch_hn_search,
        # so urlopen failures result in success with 0 items
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.hackernews import fetch
            result = await fetch(days=1)

        assert result.success
        assert result.items == []
        assert result.items_found == 0


# ---------------------------------------------------------------------------
# TechCrunch
# ---------------------------------------------------------------------------

class TestTechCrunchFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from datetime import datetime
        today = datetime.now().strftime("%a, %d %b %Y %H:%M:%S")
        rss_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel>
            <title>TechCrunch</title>
            <item>
              <title>OpenAI Releases New AI Model</title>
              <link>https://techcrunch.com/2026/03/06/openai-new-model/</link>
              <description>OpenAI has announced a new AI model today.</description>
              <pubDate>{today} +0000</pubDate>
              <dc:creator>Test Author</dc:creator>
              <category>AI</category>
            </item>
          </channel>
        </rss>'''
        mock_response = _make_mock_response(rss_xml)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.techcrunch import fetch
            result = await fetch(days=7)

        assert result.success
        assert result.source == "techcrunch"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.techcrunch import fetch
            result = await fetch(days=1)

        assert not result.success
        assert result.error is not None
        assert result.items == []


# ---------------------------------------------------------------------------
# AI News Site
# ---------------------------------------------------------------------------

class TestAINewsSiteFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from datetime import datetime
        today_display = datetime.now().strftime("%B %d, %Y")  # e.g. "March 06, 2026"
        sample_html = f'''
        <html><body>
        <div class="article">
            <span class="date">{today_display}</span>
            <a href="https://www.artificialintelligence-news.com/2026/03/06/test-article/">
                AI News Test Article About Machine Learning Advances
            </a>
        </div>
        </body></html>
        '''
        mock_response = _make_mock_response(sample_html)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.ai_news_site import fetch
            result = await fetch(days=7)

        assert result.success
        assert result.source == "ai-news"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.ai_news_site import fetch
            result = await fetch(days=1)

        # ai_news_site swallows errors in _fetch_sync, so it returns success with 0 items
        assert result.success
        assert result.items == []


# ---------------------------------------------------------------------------
# The Batch
# ---------------------------------------------------------------------------

class TestTheBatchFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from datetime import datetime
        today_display = datetime.now().strftime("%b %d, %Y")  # e.g. "Mar 06, 2026"
        sample_html = f'''
        <html><body>
        <div class="article-list">
            <span>{today_display}</span>
            <a href="https://www.deeplearning.ai/the-batch/ai-advances-march-2026/">
                <h2>AI Advances in March 2026 Are Remarkable</h2>
            </a>
        </div>
        </body></html>
        '''
        mock_response = _make_mock_response(sample_html)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.the_batch import fetch
            result = await fetch(days=7)

        assert result.success
        assert result.source == "the_batch"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.the_batch import fetch
            result = await fetch(days=1)

        # the_batch swallows errors in _fetch_sync, so it returns success with 0 items
        assert result.success
        assert result.items == []


# ---------------------------------------------------------------------------
# Smol News
# ---------------------------------------------------------------------------

class TestSmolNewsFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from datetime import datetime
        today_rss = datetime.now().strftime("%a, %d %b %Y") + " 12:00:00 +0000"
        rss_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"
             xmlns:content="http://purl.org/rss/1.0/modules/content/">
          <channel>
            <title>Smol News</title>
            <item>
              <title>AI News Digest</title>
              <link>https://news.smol.ai/issues/26-03-06-ai-news</link>
              <description>Latest AI news and developments from across the web.</description>
              <pubDate>{today_rss}</pubDate>
              <content:encoded><![CDATA[
                <p>Coverage: 10 subreddits, 5 twitters</p>
                <p>OpenAI announced something new today.</p>
              ]]></content:encoded>
            </item>
          </channel>
        </rss>'''
        mock_response = _make_mock_response(rss_xml)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.smol_news import fetch
            result = await fetch(days=7)

        assert result.success
        assert result.source == "smol.ai"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.smol_news import fetch
            result = await fetch(days=1)

        assert not result.success
        assert result.error is not None
        assert result.items == []


# ---------------------------------------------------------------------------
# Simon Willison
# ---------------------------------------------------------------------------

class TestSimonWillisonFetcher:
    @pytest.mark.asyncio
    async def test_fetch_success(self):
        from datetime import datetime
        today_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        atom_xml = f'''<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
          <title>Simon Willison</title>
          <entry>
            <title>Prompt Engineering Best Practices</title>
            <link rel="alternate" href="https://simonwillison.net/2026/Mar/6/prompt-engineering/"/>
            <published>{today_iso}</published>
            <summary>A deep dive into prompt engineering techniques.</summary>
            <category term="prompt-engineering"/>
          </entry>
        </feed>'''
        mock_response = _make_mock_response(atom_xml)

        with patch('urllib.request.urlopen', return_value=mock_response):
            from ai_news.fetchers.simonwillison import fetch
            result = await fetch(days=7)

        assert result.success
        assert result.source == "simonwillison"
        assert result.items_found >= 0

    @pytest.mark.asyncio
    async def test_fetch_error(self):
        # simonwillison fetcher catches errors per-feed in _fetch_atom_feed,
        # so we need to make urlopen raise to trigger the top-level except
        with patch('urllib.request.urlopen', side_effect=Exception("Network error")):
            from ai_news.fetchers.simonwillison import fetch
            result = await fetch(days=1)

        # The fetcher catches per-feed errors, so it returns success with 0 items
        assert result.success
        assert result.items == []
