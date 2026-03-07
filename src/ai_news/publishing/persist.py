"""Write AI news report to disk and update manifest."""

import asyncio
import json
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class PersistResult:
    filepath: Path
    bytes_written: int
    generated_at: str
    manifest_updated: bool


def _parse_date(date_str: str, label: str) -> str:
    """Validate that a date string is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD (got {date_str})") from exc
    return date_str


def _write_report_sync(
    content: str,
    start_date: str,
    end_date: str,
    days: int,
    sources_ok: list[str],
    sources_failed: list[str],
    total_items: int,
    base_dir: Path,
) -> PersistResult:
    """Synchronous implementation of report writing logic."""
    start_date = _parse_date(start_date, "start_date")
    end_date = _parse_date(end_date, "end_date")

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    filename = f"ai-news_{start_date}_to_{end_date}.md"
    base_dir.mkdir(parents=True, exist_ok=True)

    report_path = base_dir / filename
    manifest_path = base_dir / "manifest.jsonl"
    latest_path = base_dir / "latest.md"

    content_bytes = content.encode("utf-8")

    # Remove existing report files if they exist (to replace, not duplicate)
    if report_path.exists():
        report_path.unlink()
    html_path = report_path.with_suffix(".html")
    if html_path.exists():
        html_path.unlink()

    with open(report_path, "wb") as handle:
        bytes_written = handle.write(content_bytes)
    if bytes_written == 0:
        sys.stderr.write("warning: report is empty (0 bytes written)\n")

    shutil.copyfile(report_path, latest_path)

    manifest_entry = {
        "filepath": os.path.normpath(str(report_path)),
        "date_range_start": start_date,
        "date_range_end": end_date,
        "generated_at": generated_at,
        "days": days,
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "total_items": total_items,
        "bytes_written": bytes_written,
    }

    # Update manifest: filter out existing entries for same date range, then append new
    existing_entries: list[dict | str] = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Keep entries that don't match this date range
                    if not (
                        entry.get("date_range_start") == start_date
                        and entry.get("date_range_end") == end_date
                    ):
                        existing_entries.append(entry)
                except json.JSONDecodeError:
                    # Keep malformed lines as raw strings to preserve data
                    existing_entries.append(line)

    with open(manifest_path, "w", encoding="utf-8") as handle:
        for entry in existing_entries:
            if isinstance(entry, dict):
                handle.write(json.dumps(entry, ensure_ascii=True) + "\n")
            else:
                handle.write(entry + "\n")
        handle.write(json.dumps(manifest_entry, ensure_ascii=True) + "\n")

    return PersistResult(
        filepath=report_path,
        bytes_written=bytes_written,
        generated_at=generated_at,
        manifest_updated=True,
    )


async def write_report(
    content: str,
    start_date: str,
    end_date: str,
    days: int,
    sources_ok: list[str],
    sources_failed: list[str],
    total_items: int,
    base_dir: Path = Path("./reports"),
) -> PersistResult:
    """Write AI news report to disk and update manifest.

    Args:
        content: The markdown report content.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        days: Number of days covered by the report.
        sources_ok: List of sources that were successfully fetched.
        sources_failed: List of sources that failed.
        total_items: Total number of news items in the report.
        base_dir: Base directory for report output.

    Returns:
        PersistResult with filepath, bytes written, timestamp, and manifest status.

    Raises:
        ValueError: If date strings are not in YYYY-MM-DD format.
    """
    return await asyncio.to_thread(
        _write_report_sync,
        content,
        start_date,
        end_date,
        days,
        sources_ok,
        sources_failed,
        total_items,
        base_dir,
    )
