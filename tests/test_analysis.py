"""Tests for ai_news.analysis module."""
import pytest
from ai_news.analysis.prompts import (
    REPORT_TEMPLATE,
    COMMUNITY_EXPLORER_PROMPT,
    RESEARCH_EXPLORER_PROMPT,
    INDUSTRY_EXPLORER_PROMPT,
    EXPERT_EXPLORER_PROMPT,
    STORY_SYNTHESIZER_PROMPT,
    TREND_SYNTHESIZER_PROMPT,
    IMPLICATIONS_SYNTHESIZER_PROMPT,
    ORCHESTRATOR_PROMPT,
)
from ai_news.analysis.agents import _build_fetch_data_dict
from ai_news.fetchers.base import FetchResult


def test_all_prompts_are_non_empty():
    """Verify all prompt constants are defined and non-empty."""
    prompts = [
        REPORT_TEMPLATE,
        COMMUNITY_EXPLORER_PROMPT,
        RESEARCH_EXPLORER_PROMPT,
        INDUSTRY_EXPLORER_PROMPT,
        EXPERT_EXPLORER_PROMPT,
        STORY_SYNTHESIZER_PROMPT,
        TREND_SYNTHESIZER_PROMPT,
        IMPLICATIONS_SYNTHESIZER_PROMPT,
        ORCHESTRATOR_PROMPT,
    ]
    for prompt in prompts:
        assert isinstance(prompt, str)
        assert len(prompt) > 50


def test_report_template_has_placeholders():
    """Verify the report template has format placeholders."""
    assert "{start_date}" in REPORT_TEMPLATE
    assert "{end_date}" in REPORT_TEMPLATE
    assert "{total_items}" in REPORT_TEMPLATE
    assert "{sources}" in REPORT_TEMPLATE
    assert "{generated_at}" in REPORT_TEMPLATE


def test_report_template_can_be_formatted():
    """Verify the report template can be formatted without errors."""
    formatted = REPORT_TEMPLATE.format(
        start_date="2026-03-01",
        end_date="2026-03-06",
        total_items=42,
        sources="reddit, hackernews",
        generated_at="2026-03-06T12:00:00Z",
    )
    assert "2026-03-01" in formatted
    assert "42" in formatted


def test_build_fetch_data_dict_filters_failed():
    """Test _build_fetch_data_dict filters failed sources."""
    results = {
        "good": FetchResult(source="good", items=[{"title": "A"}], items_found=1),
        "bad": FetchResult(source="bad", items=[], error="failed"),
    }
    data = _build_fetch_data_dict(results)
    assert "good" in data
    assert "bad" not in data
    assert data["good"]["items_found"] == 1


def test_build_fetch_data_dict_empty():
    """Test _build_fetch_data_dict with empty input."""
    data = _build_fetch_data_dict({})
    assert data == {}


def test_build_fetch_data_dict_all_failed():
    """Test _build_fetch_data_dict when all sources failed."""
    results = {
        "a": FetchResult(source="a", items=[], error="err1"),
        "b": FetchResult(source="b", items=[], error="err2"),
    }
    data = _build_fetch_data_dict(results)
    assert data == {}


def test_build_fetch_data_dict_preserves_items():
    """Test that _build_fetch_data_dict preserves item data."""
    items = [{"title": "X", "url": "https://x.com"}]
    results = {
        "src": FetchResult(source="src", items=items, items_found=1),
    }
    data = _build_fetch_data_dict(results)
    assert data["src"]["items"] == items
    assert data["src"]["source"] == "src"
