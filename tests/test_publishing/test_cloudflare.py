"""Tests for ai_news.publishing.cloudflare."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ai_news.publishing.cloudflare import upload_report, UploadResult


@pytest.mark.asyncio
async def test_upload_success(tmp_path):
    """Test successful upload."""
    html_path = tmp_path / "report.html"
    html_path.write_text("<html><body>Test</body></html>")

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.json.return_value = {"success": True}

    with patch("ai_news.publishing.cloudflare.requests.post", return_value=mock_response):
        result = await upload_report(
            html_path=html_path,
            start_date="2026-03-01",
            end_date="2026-03-06",
            days=5,
            total_items=42,
            api_secret="test-secret",
        )

    assert isinstance(result, UploadResult)
    assert result.success
    assert result.report_id is not None
    assert result.url is not None


@pytest.mark.asyncio
async def test_upload_failure(tmp_path):
    """Test failed upload returns error result."""
    html_path = tmp_path / "report.html"
    html_path.write_text("<html><body>Test</body></html>")

    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("ai_news.publishing.cloudflare.requests.post", return_value=mock_response):
        result = await upload_report(
            html_path=html_path,
            start_date="2026-03-01",
            end_date="2026-03-06",
            days=5,
            total_items=42,
            api_secret="test-secret",
        )

    assert not result.success
    assert result.error is not None


@pytest.mark.asyncio
async def test_upload_missing_file(tmp_path):
    """Test upload with missing HTML file returns error."""
    html_path = tmp_path / "nonexistent.html"

    # No need to mock requests since the file check happens first
    result = await upload_report(
        html_path=html_path,
        start_date="2026-03-01",
        end_date="2026-03-06",
        days=5,
        total_items=42,
        api_secret="test-secret",
    )

    assert not result.success
    assert "not found" in result.error


@pytest.mark.asyncio
async def test_upload_result_url_format(tmp_path):
    """Test that the returned URL contains the report ID."""
    html_path = tmp_path / "report.html"
    html_path.write_text("<html><body>Test</body></html>")

    mock_response = MagicMock()
    mock_response.ok = True

    with patch("ai_news.publishing.cloudflare.requests.post", return_value=mock_response):
        result = await upload_report(
            html_path=html_path,
            start_date="2026-03-01",
            end_date="2026-03-06",
            days=5,
            total_items=42,
            api_secret="test-secret",
            api_base="https://test.workers.dev",
        )

    assert result.success
    assert result.url.startswith("https://test.workers.dev/archive/")
    assert result.report_id in result.url


@pytest.mark.asyncio
async def test_upload_request_exception(tmp_path):
    """Test that a requests exception is caught and returned as error."""
    import requests as req_lib

    html_path = tmp_path / "report.html"
    html_path.write_text("<html><body>Test</body></html>")

    with patch(
        "ai_news.publishing.cloudflare.requests.post",
        side_effect=req_lib.ConnectionError("Connection refused"),
    ):
        result = await upload_report(
            html_path=html_path,
            start_date="2026-03-01",
            end_date="2026-03-06",
            days=5,
            total_items=42,
            api_secret="test-secret",
        )

    assert not result.success
    assert "Request failed" in result.error
