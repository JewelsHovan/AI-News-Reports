"""Date formatting utilities for AI News reports."""

from datetime import datetime


def get_ordinal_suffix(day: int) -> str:
    """Return the ordinal suffix (st, nd, rd, th) for a given day number."""
    if 11 <= day <= 13:
        return "th"
    last_digit = day % 10
    if last_digit == 1:
        return "st"
    elif last_digit == 2:
        return "nd"
    elif last_digit == 3:
        return "rd"
    else:
        return "th"


def format_date_human_filename(date_str: str) -> str | None:
    """Format a YYYY-MM-DD date string for use in filenames (e.g. 'mar_6th_2026')."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    month_abbr = dt.strftime("%b").lower()
    day = dt.day
    suffix = get_ordinal_suffix(day)
    year = dt.year
    return f"{month_abbr}_{day}{suffix}_{year}"


def format_date_human_display(date_str: str) -> str | None:
    """Format a YYYY-MM-DD date string for display (e.g. 'Mar 6th, 2026')."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    month_abbr = dt.strftime("%b")
    day = dt.day
    suffix = get_ordinal_suffix(day)
    year = dt.year
    return f"{month_abbr} {day}{suffix}, {year}"


def format_date_range_filename(start_date: str, end_date: str) -> str | None:
    """Format a date range for filenames (e.g. 'mar_4th_2026_to_mar_6th_2026')."""
    start_formatted = format_date_human_filename(start_date)
    end_formatted = format_date_human_filename(end_date)
    if start_formatted is None or end_formatted is None:
        return None
    return f"{start_formatted}_to_{end_formatted}"


def format_date_range_display(start_date: str, end_date: str) -> str | None:
    """Format a date range for display (e.g. 'Mar 4th, 2026 → Mar 6th, 2026')."""
    start_formatted = format_date_human_display(start_date)
    end_formatted = format_date_human_display(end_date)
    if start_formatted is None or end_formatted is None:
        return None
    return f"{start_formatted} \u2192 {end_formatted}"
