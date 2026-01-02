#!/usr/bin/env python3
"""
Date formatting utilities for AI News reports.

Provides human-friendly date formatting for filenames and display text.
"""

from datetime import datetime


def get_ordinal_suffix(day: int) -> str:
    """
    Return ordinal suffix (st, nd, rd, th) for a day number.

    Args:
        day: Day of month (1-31)

    Returns:
        Ordinal suffix string

    Examples:
        >>> get_ordinal_suffix(1)
        'st'
        >>> get_ordinal_suffix(2)
        'nd'
        >>> get_ordinal_suffix(3)
        'rd'
        >>> get_ordinal_suffix(4)
        'th'
        >>> get_ordinal_suffix(11)
        'th'
        >>> get_ordinal_suffix(21)
        'st'
    """
    # 11, 12, 13 are special cases (always use 'th')
    if 11 <= day <= 13:
        return "th"

    # Check last digit for other cases
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
    """
    Convert YYYY-MM-DD to filename format like 'dec_2nd_2025'.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Lowercase filename-safe date string, or None if invalid date

    Examples:
        >>> format_date_human_filename('2025-12-02')
        'dec_2nd_2025'
        >>> format_date_human_filename('2025-01-01')
        'jan_1st_2025'
        >>> format_date_human_filename('2025-03-23')
        'mar_23rd_2025'
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    month_abbr = dt.strftime("%b").lower()  # e.g., 'dec'
    day = dt.day
    suffix = get_ordinal_suffix(day)
    year = dt.year

    return f"{month_abbr}_{day}{suffix}_{year}"


def format_date_human_display(date_str: str) -> str | None:
    """
    Convert YYYY-MM-DD to display format like 'Dec 2nd, 2025'.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        Human-readable display date string, or None if invalid date

    Examples:
        >>> format_date_human_display('2025-12-02')
        'Dec 2nd, 2025'
        >>> format_date_human_display('2025-01-01')
        'Jan 1st, 2025'
        >>> format_date_human_display('2025-03-23')
        'Mar 23rd, 2025'
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None
    month_abbr = dt.strftime("%b")  # e.g., 'Dec'
    day = dt.day
    suffix = get_ordinal_suffix(day)
    year = dt.year

    return f"{month_abbr} {day}{suffix}, {year}"


def format_date_range_filename(start_date: str, end_date: str) -> str | None:
    """
    Format date range for filename: 'dec_2nd_2025_to_dec_4th_2025'.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Filename-safe date range string, or None if either date is invalid

    Examples:
        >>> format_date_range_filename('2025-12-02', '2025-12-04')
        'dec_2nd_2025_to_dec_4th_2025'
    """
    start_formatted = format_date_human_filename(start_date)
    end_formatted = format_date_human_filename(end_date)
    if start_formatted is None or end_formatted is None:
        return None
    return f"{start_formatted}_to_{end_formatted}"


def format_date_range_display(start_date: str, end_date: str) -> str | None:
    """
    Format date range for display: 'Dec 2nd, 2025 -> Dec 4th, 2025'.

    Uses Unicode right arrow for visual clarity.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Human-readable date range string, or None if either date is invalid

    Examples:
        >>> format_date_range_display('2025-12-02', '2025-12-04')
        'Dec 2nd, 2025 -> Dec 4th, 2025'
    """
    start_formatted = format_date_human_display(start_date)
    end_formatted = format_date_human_display(end_date)
    if start_formatted is None or end_formatted is None:
        return None
    return f"{start_formatted} \u2192 {end_formatted}"
