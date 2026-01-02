#!/usr/bin/env python3
"""
Generate archive index page and render individual report HTML files.

This script reads the manifest.jsonl file containing metadata about generated
reports and creates:
1. An index.html page listing all reports in reverse chronological order
2. Individual HTML files for each report using render_html.py
"""
import argparse
import html
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# =============================================================================
# Date Formatting Utilities
# =============================================================================


def _ordinal_suffix(day: int) -> str:
    """Return ordinal suffix for a day number (st, nd, rd, th)."""
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def format_date_display(date_str: str) -> str:
    """
    Format a date string for display.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Human-readable date like "Dec 2nd, 2025"
    """
    date = datetime.strptime(date_str, "%Y-%m-%d")
    day = date.day
    suffix = _ordinal_suffix(day)
    return date.strftime(f"%b {day}{suffix}, %Y")


def format_date_range_display(start_date: str, end_date: str) -> str:
    """
    Format a date range for display.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Human-readable range like "Dec 2nd, 2025 -> Dec 4th, 2025"
    """
    return f"{format_date_display(start_date)} \u2192 {format_date_display(end_date)}"


def format_date_range_filename(start_date: str, end_date: str) -> str:
    """
    Format a date range for use in filenames.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Filename-safe string like "dec_2nd_2025_to_dec_4th_2025"
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    start_day = start.day
    end_day = end.day

    start_suffix = _ordinal_suffix(start_day)
    end_suffix = _ordinal_suffix(end_day)

    start_str = start.strftime(f"%b_{start_day}{start_suffix}_%Y").lower()
    end_str = end.strftime(f"%b_{end_day}{end_suffix}_%Y").lower()

    return f"{start_str}_to_{end_str}"


# =============================================================================
# Manifest Loading and Processing
# =============================================================================


def load_manifest(manifest_path: Path) -> list[dict]:
    """
    Load and parse the manifest.jsonl file.

    Args:
        manifest_path: Path to manifest.jsonl

    Returns:
        List of report metadata dictionaries
    """
    if not manifest_path.exists():
        return []

    reports = []
    with manifest_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    reports.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"Warning: Skipping invalid JSON line: {e}", file=sys.stderr)
    return reports


def _parse_timestamp(ts: str) -> datetime | None:
    """Parse ISO timestamp string to datetime, or None if invalid."""
    if not ts:
        return None
    try:
        # Handle both formats: with and without timezone
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def deduplicate_reports(reports: list[dict]) -> list[dict]:
    """
    Deduplicate reports with the same date range, keeping the latest by generated_at.

    Args:
        reports: List of report metadata dictionaries

    Returns:
        Deduplicated list with only the latest report per date range
    """
    # Group by date range
    by_range: dict[tuple[str, str], dict] = {}

    for report in reports:
        # Skip entries missing required date keys
        start = report.get("date_range_start")
        end = report.get("date_range_end")
        if not start or not end:
            print(f"Warning: Skipping report missing date keys: {report.get('filepath', 'unknown')}", file=sys.stderr)
            continue

        key = (start, end)
        existing = by_range.get(key)

        if existing is None:
            by_range[key] = report
        else:
            # Keep the one with later generated_at timestamp (parse to datetime for proper comparison)
            report_ts = _parse_timestamp(report.get("generated_at", ""))
            existing_ts = _parse_timestamp(existing.get("generated_at", ""))

            # If we can't parse timestamps, keep the existing one
            if report_ts and existing_ts and report_ts > existing_ts:
                by_range[key] = report
            elif report_ts and not existing_ts:
                by_range[key] = report

    return list(by_range.values())


def sort_reports_by_date(reports: list[dict], reverse: bool = True) -> list[dict]:
    """
    Sort reports by date range (start date, then end date).

    Args:
        reports: List of report metadata dictionaries
        reverse: If True, sort newest first (default)

    Returns:
        Sorted list of reports
    """
    return sorted(
        reports,
        key=lambda r: (r.get("date_range_start", ""), r.get("date_range_end", "")),
        reverse=reverse,
    )


# =============================================================================
# HTML Generation
# =============================================================================


def generate_archive_index_html(reports: list[dict], rendered_files: set[str] | None = None) -> str:
    """
    Generate the archive index HTML page.

    Args:
        reports: List of report metadata (should be sorted and deduplicated)
        rendered_files: Optional set of successfully rendered filenames (to avoid broken links)

    Returns:
        Complete HTML document as string
    """
    # Build report list items
    list_items = []
    for report in reports:
        start = report.get("date_range_start", "")
        end = report.get("date_range_end", "")
        total_items = report.get("total_items", 0)

        if not start or not end:
            continue

        display_range = format_date_range_display(start, end)
        filename = format_date_range_filename(start, end)

        # Skip entries where date formatting failed or rendering failed
        if not display_range or not filename:
            continue

        filename = filename + ".html"

        # Only include entries that were successfully rendered
        if rendered_files is not None and filename not in rendered_files:
            continue

        # HTML escape all interpolated values for XSS safety
        safe_filename = html.escape(filename)
        safe_display = html.escape(display_range)
        safe_items = int(total_items) if isinstance(total_items, (int, float)) else 0

        list_items.append(f"""            <li class="archive-item">
                <a href="{safe_filename}" class="archive-link">{safe_display}</a>
                <span class="archive-meta">{safe_items} items</span>
            </li>""")

    list_html = "\n".join(list_items) if list_items else "            <li class=\"archive-item\">No reports available yet.</li>"

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI News Archive</title>
    <link rel="stylesheet" href="../styles.css?v=2">
    <style>
        /* Archive-specific styles */
        .container {{
            max-width: 600px;
        }}

        .archive-description {{
            color: var(--color-text-muted);
            margin-bottom: 2rem;
            font-size: 0.95rem;
        }}

        .archive-list {{
            list-style: none;
            padding: 0;
            margin: 0 0 2rem 0;
        }}

        .archive-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            border-bottom: 1px solid var(--color-border);
            transition: background-color 0.15s;
        }}

        .archive-item:last-child {{
            border-bottom: none;
        }}

        .archive-item:hover {{
            background-color: rgba(37, 99, 235, 0.05);
        }}

        @media (prefers-color-scheme: dark) {{
            .archive-item:hover {{
                background-color: rgba(59, 130, 246, 0.1);
            }}
        }}

        .archive-link {{
            color: var(--color-accent);
            text-decoration: none;
            font-weight: 500;
            font-size: 0.95rem;
        }}

        .archive-link:hover {{
            text-decoration: underline;
        }}

        .archive-meta {{
            color: var(--color-text-muted);
            font-size: 0.85rem;
            white-space: nowrap;
            margin-left: 1rem;
        }}

        @media (max-width: 480px) {{
            .archive-item {{
                flex-direction: column;
                align-items: flex-start;
                gap: 0.5rem;
            }}

            .archive-meta {{
                margin-left: 0;
            }}
        }}
    </style>
</head>
<body>
    <main class="container">
        <h1>AI News Archive</h1>
        <p class="archive-description">Browse past AI news reports</p>

        <ul class="archive-list">
{list_html}
        </ul>

        <a href="../" class="back-link">&larr; Subscribe to Newsletter</a>
    </main>
</body>
</html>
'''


# =============================================================================
# Report HTML Generation
# =============================================================================


def render_report_html(
    report: dict,
    reports_dir: Path,
    output_dir: Path,
    scripts_dir: Path,
) -> Path | None:
    """
    Render a single report's markdown to web-safe HTML.

    Args:
        report: Report metadata dictionary
        reports_dir: Directory containing markdown reports
        output_dir: Directory to write HTML output
        scripts_dir: Directory containing render_html.py

    Returns:
        Path to generated HTML file, or None if failed
    """
    filepath = report.get("filepath", "")
    if not filepath:
        return None

    # Resolve the markdown file path
    # filepath in manifest could be:
    # - absolute path
    # - relative path like "reports/ai-news_...md"
    # - just filename like "ai-news_...md"
    md_path = Path(filepath)
    if not md_path.is_absolute():
        candidates = [
            Path.cwd() / filepath,                    # relative to cwd
            reports_dir / filepath,                   # relative to reports_dir
            reports_dir / md_path.name,               # just filename in reports_dir
            reports_dir.parent / filepath,            # relative to reports_dir parent
        ]
        md_path = None
        for candidate in candidates:
            if candidate.exists():
                md_path = candidate
                break

        if md_path is None:
            print(f"  Warning: Markdown file not found: {filepath}", file=sys.stderr)
            return None
    elif not md_path.exists():
        print(f"  Warning: Markdown file not found: {filepath}", file=sys.stderr)
        return None

    # Generate output filename from date range
    start = report.get("date_range_start", "")
    end = report.get("date_range_end", "")
    if not start or not end:
        return None

    output_filename = format_date_range_filename(start, end) + ".html"
    output_path = output_dir / output_filename

    # Call render_html.py to generate the HTML
    render_script = scripts_dir / "render_html.py"
    if not render_script.exists():
        print(f"  Error: render_html.py not found at {render_script}", file=sys.stderr)
        return None

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(render_script),
                str(md_path),
                "--output",
                str(output_path),
                "--mode",
                "web",  # Use web mode to remove unsubscribe footer
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"  Error rendering {filepath}: {result.stderr}", file=sys.stderr)
            return None

        return output_path

    except subprocess.TimeoutExpired:
        print(f"  Error: Timeout rendering {filepath}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Error rendering {filepath}: {e}", file=sys.stderr)
        return None


# =============================================================================
# Main Entry Point
# =============================================================================


def main() -> int:
    """
    Main entry point for archive generation.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Generate archive index and render report HTML files."
    )
    parser.add_argument(
        "--manifest",
        default="reports/manifest.jsonl",
        help="Path to manifest file (default: reports/manifest.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default="docs/archive",
        help="Output directory for archive (default: docs/archive)",
    )
    parser.add_argument(
        "--reports-dir",
        default="reports",
        help="Directory containing report markdown files (default: reports)",
    )
    args = parser.parse_args()

    # Resolve paths
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = Path.cwd() / manifest_path

    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir

    reports_dir = Path(args.reports_dir)
    if not reports_dir.is_absolute():
        reports_dir = Path.cwd() / reports_dir

    # Get the scripts directory (where this script lives)
    scripts_dir = Path(__file__).parent.resolve()

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load manifest
    print(f"Loading manifest from {manifest_path}...")
    if not manifest_path.exists():
        print(f"Warning: Manifest file not found: {manifest_path}")
        print("Creating empty archive index...")
        reports = []
    else:
        reports = load_manifest(manifest_path)
        print(f"  Found {len(reports)} report entries")

    # Deduplicate and sort
    reports = deduplicate_reports(reports)
    print(f"  {len(reports)} unique date ranges after deduplication")

    reports = sort_reports_by_date(reports, reverse=True)

    # Generate individual report HTML files
    print("\nRendering report HTML files...")
    rendered_count = 0
    rendered_files: set[str] = set()
    for report in reports:
        start = report.get("date_range_start", "")
        end = report.get("date_range_end", "")
        display = format_date_range_display(start, end) if start and end else None
        if not display:
            display = "unknown (invalid dates)"
        print(f"  Processing: {display}")

        result = render_report_html(report, reports_dir, output_dir, scripts_dir)
        if result:
            print(f"    -> {result.name}")
            rendered_count += 1
            rendered_files.add(result.name)

    print(f"\nRendered {rendered_count}/{len(reports)} reports")

    # Generate archive index (only include successfully rendered reports)
    print("\nGenerating archive index...")
    index_html = generate_archive_index_html(reports, rendered_files=rendered_files)
    index_path = output_dir / "index.html"
    index_path.write_text(index_html, encoding="utf-8")
    print(f"  -> {index_path}")

    print("\nArchive generation complete!")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
