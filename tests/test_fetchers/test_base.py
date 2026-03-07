"""Tests for ai_news.fetchers.base module."""
from ai_news.fetchers.base import FetchResult


class TestFetchResultSuccess:
    def test_success_when_no_error(self, sample_fetch_result):
        assert sample_fetch_result.success is True

    def test_not_success_when_error_set(self, failed_fetch_result):
        assert failed_fetch_result.success is False

    def test_success_with_empty_items_but_no_error(self):
        result = FetchResult(source="test", items=[])
        assert result.success is True


class TestFetchResultToDict:
    def test_to_dict_returns_correct_keys(self, sample_fetch_result):
        d = sample_fetch_result.to_dict()
        assert set(d.keys()) == {"source", "items_found", "items", "metadata", "error"}

    def test_to_dict_values(self, sample_fetch_result):
        d = sample_fetch_result.to_dict()
        assert d["source"] == "test_source"
        assert d["items_found"] == 2
        assert len(d["items"]) == 2
        assert d["metadata"] == {"source_url": "https://example.com"}
        assert d["error"] is None

    def test_to_dict_with_error(self, failed_fetch_result):
        d = failed_fetch_result.to_dict()
        assert d["error"] == "Connection timeout"
        assert d["items"] == []


class TestFetchResultDefaults:
    def test_default_metadata_is_empty_dict(self):
        result = FetchResult(source="test", items=[])
        assert result.metadata == {}

    def test_default_error_is_none(self):
        result = FetchResult(source="test", items=[])
        assert result.error is None

    def test_default_items_found_is_zero(self):
        result = FetchResult(source="test", items=[])
        assert result.items_found == 0

    def test_default_metadata_not_shared_between_instances(self):
        r1 = FetchResult(source="a", items=[])
        r2 = FetchResult(source="b", items=[])
        r1.metadata["key"] = "value"
        assert "key" not in r2.metadata
