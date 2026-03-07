"""Tests for ai_news.utils.dates module."""
import pytest
from ai_news.utils.dates import (
    get_ordinal_suffix,
    format_date_human_filename,
    format_date_human_display,
    format_date_range_filename,
    format_date_range_display,
)


class TestGetOrdinalSuffix:
    def test_1st(self):
        assert get_ordinal_suffix(1) == "st"

    def test_2nd(self):
        assert get_ordinal_suffix(2) == "nd"

    def test_3rd(self):
        assert get_ordinal_suffix(3) == "rd"

    def test_4th(self):
        assert get_ordinal_suffix(4) == "th"

    def test_11th(self):
        assert get_ordinal_suffix(11) == "th"

    def test_12th(self):
        assert get_ordinal_suffix(12) == "th"

    def test_13th(self):
        assert get_ordinal_suffix(13) == "th"

    def test_21st(self):
        assert get_ordinal_suffix(21) == "st"

    def test_22nd(self):
        assert get_ordinal_suffix(22) == "nd"

    def test_23rd(self):
        assert get_ordinal_suffix(23) == "rd"


class TestFormatDateHumanFilename:
    def test_valid_date(self):
        assert format_date_human_filename("2026-03-06") == "mar_6th_2026"

    def test_valid_date_1st(self):
        assert format_date_human_filename("2026-03-01") == "mar_1st_2026"

    def test_valid_date_22nd(self):
        assert format_date_human_filename("2026-01-22") == "jan_22nd_2026"

    def test_invalid_date_returns_none(self):
        assert format_date_human_filename("not-a-date") is None

    def test_empty_string_returns_none(self):
        assert format_date_human_filename("") is None


class TestFormatDateHumanDisplay:
    def test_valid_date(self):
        assert format_date_human_display("2026-03-06") == "Mar 6th, 2026"

    def test_valid_date_1st(self):
        assert format_date_human_display("2026-03-01") == "Mar 1st, 2026"

    def test_valid_date_2nd(self):
        assert format_date_human_display("2026-03-02") == "Mar 2nd, 2026"

    def test_invalid_date_returns_none(self):
        assert format_date_human_display("invalid") is None

    def test_empty_string_returns_none(self):
        assert format_date_human_display("") is None


class TestFormatDateRangeFilename:
    def test_valid_range(self):
        result = format_date_range_filename("2026-03-04", "2026-03-06")
        assert result == "mar_4th_2026_to_mar_6th_2026"

    def test_invalid_start_returns_none(self):
        assert format_date_range_filename("bad", "2026-03-06") is None

    def test_invalid_end_returns_none(self):
        assert format_date_range_filename("2026-03-04", "bad") is None

    def test_both_invalid_returns_none(self):
        assert format_date_range_filename("bad", "bad") is None


class TestFormatDateRangeDisplay:
    def test_valid_range(self):
        result = format_date_range_display("2026-03-04", "2026-03-06")
        assert result == "Mar 4th, 2026 \u2192 Mar 6th, 2026"

    def test_contains_arrow_character(self):
        result = format_date_range_display("2026-03-01", "2026-03-06")
        assert "\u2192" in result

    def test_invalid_start_returns_none(self):
        assert format_date_range_display("bad", "2026-03-06") is None

    def test_invalid_end_returns_none(self):
        assert format_date_range_display("2026-03-04", "bad") is None
