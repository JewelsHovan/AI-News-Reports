"""Shared test fixtures for AI News tests."""
import pytest
from ai_news.fetchers.base import FetchResult


@pytest.fixture
def sample_fetch_result():
    return FetchResult(
        source="test_source",
        items=[
            {"title": "Test Article 1", "url": "https://example.com/1", "date": "2026-03-01"},
            {"title": "Test Article 2", "url": "https://example.com/2", "date": "2026-03-02"},
        ],
        items_found=2,
        metadata={"source_url": "https://example.com"},
    )


@pytest.fixture
def failed_fetch_result():
    return FetchResult(
        source="failed_source",
        items=[],
        error="Connection timeout",
    )


@pytest.fixture
def sample_report_markdown():
    return """# AI News Report: 2026-03-01 to 2026-03-06

## Executive Summary
This is a test report with sample content.

---

## Top Stories This Period
### 1. Test Story
**Sources:** Reddit, HN
**Why It Matters:** Testing purposes

---

## Report Metadata
- **Date Range:** 2026-03-01 to 2026-03-06
- **Total Items Analyzed:** 42
- **Sources Consulted:** test_source
- **Generated:** 2026-03-06T12:00:00Z
"""
