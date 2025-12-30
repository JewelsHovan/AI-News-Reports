#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def _parse_date(date_str: str, label: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD (got {date_str})") from exc
    return date_str


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write AI news report to disk.")
    parser.add_argument("--start-date", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=0, help="Number of days covered")
    parser.add_argument(
        "--base-dir",
        default="./reports",
        help="Output directory (default: ./reports)",
    )
    parser.add_argument(
        "--sources-ok",
        default="",
        help="Comma-separated list of successful sources",
    )
    parser.add_argument(
        "--sources-failed",
        default="",
        help="Comma-separated list of failed sources",
    )
    parser.add_argument("--total-items", type=int, default=0, help="Total items in report")

    args = parser.parse_args()

    start_date = _parse_date(args.start_date, "start-date")
    end_date = _parse_date(args.end_date, "end-date")

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    filename = f"ai-news_{start_date}_to_{end_date}_{timestamp}.md"
    base_dir = Path(args.base_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    report_path = base_dir / filename
    manifest_path = base_dir / "manifest.jsonl"
    latest_path = base_dir / "latest.md"

    content = sys.stdin.read()
    content_bytes = content.encode("utf-8")

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
        "days": args.days,
        "sources_ok": _parse_csv(args.sources_ok),
        "sources_failed": _parse_csv(args.sources_failed),
        "total_items": args.total_items,
        "bytes_written": bytes_written,
    }

    with open(manifest_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(manifest_entry, ensure_ascii=True) + "\n")

    result = {
        "filepath": os.path.normpath(str(report_path)),
        "bytes_written": bytes_written,
        "generated_at": generated_at,
        "manifest_updated": True,
    }
    sys.stdout.write(json.dumps(result, ensure_ascii=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(1)
