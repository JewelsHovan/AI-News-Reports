"""Integration tests for ai_news.pipeline."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
from ai_news.pipeline import (
    fetch_all_sources,
    PipelineResult,
    ALL_FETCHERS,
)
from ai_news.fetchers.base import FetchResult


def test_pipeline_result_dataclass():
    """Test PipelineResult construction."""
    result = PipelineResult(
        success=True,
        sources_ok=["reddit", "hackernews"],
        sources_failed=["techcrunch"],
        total_items=42,
    )
    assert result.success
    assert len(result.sources_ok) == 2
    assert result.report_path is None
    assert result.newsletter_sent == 0


def test_pipeline_result_defaults():
    """Test PipelineResult default values."""
    result = PipelineResult(success=False)
    assert not result.success
    assert result.report_path is None
    assert result.html_path is None
    assert result.upload_url is None
    assert result.newsletter_sent == 0
    assert result.sources_ok == []
    assert result.sources_failed == []
    assert result.total_items == 0
    assert result.errors == []


def test_all_fetchers_dict():
    """Test that ALL_FETCHERS contains expected sources."""
    expected_sources = {
        "huggingface", "reddit", "hackernews", "techcrunch",
        "ai-news", "the_batch", "smol.ai", "simonwillison",
    }
    assert set(ALL_FETCHERS.keys()) == expected_sources


def test_all_fetchers_are_callable():
    """Test that all fetcher values are callable."""
    for name, fetcher in ALL_FETCHERS.items():
        assert callable(fetcher), f"Fetcher {name} is not callable"


@pytest.mark.asyncio
async def test_fetch_all_sources_runs_all_fetchers():
    """Test that fetch_all_sources calls all fetchers and returns results."""
    mock_result = FetchResult(
        source="mock", items=[{"title": "Test"}], items_found=1
    )

    # Create async mock fetchers
    mock_fetchers = {}
    for name in ALL_FETCHERS:
        mock_fn = AsyncMock(return_value=FetchResult(
            source=name, items=[{"title": "Test"}], items_found=1
        ))
        mock_fetchers[name] = mock_fn

    with patch.dict(
        "ai_news.pipeline.ALL_FETCHERS",
        mock_fetchers,
    ):
        results = await fetch_all_sources(days=2)

    assert len(results) == len(mock_fetchers)
    for name, result in results.items():
        assert result.success


@pytest.mark.asyncio
async def test_fetch_all_sources_handles_failures():
    """Test that one failing fetcher doesn't crash others."""
    good_result = FetchResult(source="good", items=[{"title": "Test"}], items_found=1)

    async def failing_fetch(days):
        raise RuntimeError("Network error")

    async def good_fetch(days):
        return good_result

    with patch.dict(
        "ai_news.pipeline.ALL_FETCHERS",
        {"good": good_fetch, "bad": failing_fetch},
        clear=True,
    ):
        results = await fetch_all_sources(days=2)

    # The good one should succeed, bad one should be missing (exception caught)
    assert "good" in results
    assert results["good"].success
    # The bad one raised an exception, so it's excluded from results
    assert "bad" not in results
