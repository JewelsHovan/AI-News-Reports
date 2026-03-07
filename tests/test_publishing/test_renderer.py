"""Tests for ai_news.publishing.renderer."""
import pytest
from pathlib import Path
from ai_news.publishing.renderer import render_html, RenderResult


@pytest.mark.asyncio
async def test_render_html_creates_file(tmp_path):
    """Test basic HTML rendering."""
    md_content = "# Test Report\n\nSome **bold** text and a [link](https://example.com)."
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text(md_content)

    result = await render_html(md_path)

    assert isinstance(result, RenderResult)
    assert result.html_path.exists()
    assert result.html_path.suffix == ".html"
    assert result.title == "Test Report"

    html = result.html_path.read_text()
    assert "<html" in html
    assert "Test Report" in html
    assert "bold" in html


@pytest.mark.asyncio
async def test_render_html_includes_inline_styles(tmp_path):
    """Test that HTML has inline styles for email compatibility."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("# Report\n\n## Section\n\nParagraph text.")

    result = await render_html(md_path)
    html = result.html_path.read_text()

    # Should have inline styles on elements
    assert 'style="' in html
    # Should have the email wrapper table
    assert 'role="presentation"' in html


@pytest.mark.asyncio
async def test_render_html_updates_latest(tmp_path):
    """Test that latest.html is updated."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("# Report\n\nContent.")

    await render_html(md_path)

    latest = tmp_path / "latest.html"
    assert latest.exists()


@pytest.mark.asyncio
async def test_render_html_web_mode(tmp_path):
    """Test web mode omits unsubscribe footer."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("# Report\n\nContent.")

    result = await render_html(md_path, mode="web")
    html = result.html_path.read_text()

    assert "UNSUBSCRIBE_LINK" not in html


@pytest.mark.asyncio
async def test_render_html_email_mode_has_unsubscribe(tmp_path):
    """Test email mode includes unsubscribe placeholder."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("# Report\n\nContent.")

    result = await render_html(md_path, mode="email")
    html = result.html_path.read_text()

    assert "UNSUBSCRIBE_LINK" in html


@pytest.mark.asyncio
async def test_render_html_missing_file(tmp_path):
    """Test that missing markdown file raises FileNotFoundError."""
    md_path = tmp_path / "nonexistent.md"
    with pytest.raises(FileNotFoundError):
        await render_html(md_path)


@pytest.mark.asyncio
async def test_render_html_extracts_date_range(tmp_path):
    """Test that date range is extracted from filename and shown in HTML."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("# Report\n\nContent.")

    result = await render_html(md_path)
    html = result.html_path.read_text()

    # The date range display should appear in the header
    # format_date_range_display produces "Mar 1st, 2026 -> Mar 6th, 2026"
    assert "Mar" in html
    assert "2026" in html


@pytest.mark.asyncio
async def test_render_html_default_title(tmp_path):
    """Test that a default title is used when no H1 is present."""
    md_path = tmp_path / "ai-news_2026-03-01_to_2026-03-06.md"
    md_path.write_text("Some content without a heading.")

    result = await render_html(md_path)
    assert result.title == "AI News Report"
