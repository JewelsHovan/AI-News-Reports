"""Tests for ai_news.publishing.persist."""
import json
import pytest
from pathlib import Path
from ai_news.publishing.persist import (
    write_report,
    PersistResult,
    _strip_preamble,
)


def test_strip_preamble_removes_chat_leak():
    """A conversational preamble before the H1 heading is discarded."""
    leaked = (
        "I'll now generate the comprehensive AI News Report using all the "
        "gathered data.\n\n# AI News Report: 2026-03-16 to 2026-03-18\n\n"
        "## Executive Summary\nReal content."
    )
    out = _strip_preamble(leaked)
    assert out.startswith("# AI News Report: 2026-03-16 to 2026-03-18")
    assert "I'll now generate" not in out


def test_strip_preamble_leaves_clean_report_untouched():
    """A report that already starts with the heading is unchanged."""
    clean = "# AI News Report: 2026-03-16 to 2026-03-18\n\n## Executive Summary\nX."
    assert _strip_preamble(clean) == clean


def test_strip_preamble_preserves_report_without_marker():
    """Without the marker, content is returned as-is (no destructive trim)."""
    other = "# Some Other Heading\n\nbody"
    assert _strip_preamble(other) == other


@pytest.mark.asyncio
async def test_write_report_strips_preamble(tmp_path):
    """End-to-end: a leaked preamble is stripped before hitting disk."""
    content = (
        "Perfect! Here is your report.\n\n"
        "# AI News Report: 2026-03-14 to 2026-03-16\n\n## Executive Summary\nBody."
    )
    result = await write_report(
        content=content,
        start_date="2026-03-14",
        end_date="2026-03-16",
        days=2,
        sources_ok=["reddit"],
        sources_failed=[],
        total_items=10,
        base_dir=tmp_path,
    )
    written = result.filepath.read_text(encoding="utf-8")
    assert written.startswith("# AI News Report: 2026-03-14 to 2026-03-16")
    assert "Perfect!" not in written


@pytest.mark.asyncio
async def test_write_report_creates_files(tmp_path):
    """Test that write_report creates .md, latest.md, and manifest.jsonl."""
    content = "# Test Report\n\nSome content here."
    result = await write_report(
        content=content,
        start_date="2026-03-01",
        end_date="2026-03-06",
        days=5,
        sources_ok=["reddit", "hackernews"],
        sources_failed=["techcrunch"],
        total_items=42,
        base_dir=tmp_path,
    )

    assert isinstance(result, PersistResult)
    assert result.filepath.exists()
    assert result.bytes_written > 0
    assert result.manifest_updated

    # Check latest.md exists
    latest = tmp_path / "latest.md"
    assert latest.exists()
    assert latest.read_text() == content

    # Check manifest
    manifest = tmp_path / "manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text().strip().split("\n")
    entry = json.loads(lines[-1])
    assert entry["date_range_start"] == "2026-03-01"
    assert entry["date_range_end"] == "2026-03-06"
    assert entry["days"] == 5
    assert entry["total_items"] == 42


@pytest.mark.asyncio
async def test_write_report_replaces_existing(tmp_path):
    """Test that writing the same date range replaces the old entry."""
    await write_report("First", "2026-03-01", "2026-03-06", 5, ["a"], [], 10, tmp_path)
    await write_report("Second", "2026-03-01", "2026-03-06", 5, ["a", "b"], [], 20, tmp_path)

    manifest = tmp_path / "manifest.jsonl"
    lines = [l for l in manifest.read_text().strip().split("\n") if l]
    assert len(lines) == 1  # Should have replaced, not duplicated
    entry = json.loads(lines[0])
    assert entry["total_items"] == 20


@pytest.mark.asyncio
async def test_write_report_preserves_other_entries(tmp_path):
    """Test that writing a new date range preserves existing entries."""
    await write_report("First", "2026-03-01", "2026-03-03", 2, ["a"], [], 10, tmp_path)
    await write_report("Second", "2026-03-04", "2026-03-06", 2, ["b"], [], 20, tmp_path)

    manifest = tmp_path / "manifest.jsonl"
    lines = [l for l in manifest.read_text().strip().split("\n") if l]
    assert len(lines) == 2


@pytest.mark.asyncio
async def test_write_report_invalid_date(tmp_path):
    """Test that invalid date format raises ValueError."""
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        await write_report("Content", "not-a-date", "2026-03-06", 5, [], [], 0, tmp_path)


@pytest.mark.asyncio
async def test_write_report_filename_format(tmp_path):
    """Test that the report filename follows the expected pattern."""
    result = await write_report(
        "Content", "2026-03-01", "2026-03-06", 5, [], [], 0, tmp_path
    )
    assert result.filepath.name == "ai-news_2026-03-01_to_2026-03-06.md"


@pytest.mark.asyncio
async def test_write_report_generated_at_format(tmp_path):
    """Test that generated_at is in ISO 8601 UTC format."""
    result = await write_report(
        "Content", "2026-03-01", "2026-03-06", 5, [], [], 0, tmp_path
    )
    # Should match YYYY-MM-DDTHH:MM:SSZ
    assert result.generated_at.endswith("Z")
    assert "T" in result.generated_at
