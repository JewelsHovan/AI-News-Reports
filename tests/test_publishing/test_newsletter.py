"""Tests for ai_news.publishing.newsletter (basic unit tests)."""
import pytest
from ai_news.publishing.newsletter import NewsletterResult


def test_newsletter_result_dataclass():
    """Test NewsletterResult construction."""
    result = NewsletterResult(sent_count=5, skipped_count=2, errors=["one error"])
    assert result.sent_count == 5
    assert result.skipped_count == 2
    assert len(result.errors) == 1


def test_newsletter_result_empty_errors():
    """Test NewsletterResult with no errors."""
    result = NewsletterResult(sent_count=3, skipped_count=0, errors=[])
    assert result.sent_count == 3
    assert result.skipped_count == 0
    assert len(result.errors) == 0


def test_issue_subject_with_and_without_number():
    from ai_news.publishing.newsletter import _issue_subject

    assert _issue_subject("Le Chonk and a $40B chip bet", 69) == "Julien's AI Brief #69: Le Chonk and a $40B chip bet"
    assert _issue_subject("Le Chonk", None) == "Julien's AI Brief: Le Chonk"
