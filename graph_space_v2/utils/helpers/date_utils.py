from datetime import datetime, timedelta
from typing import Optional, Union, Dict, Any, Tuple
import pytz
import re

DateType = Union[str, datetime]


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string into a datetime object.
    Supports ISO format and several common date formats.

    Args:
        date_str: Date string to parse

    Returns:
        Datetime object or None if parsing fails
    """
    if not date_str:
        return None

    try:
        # Try ISO format first (most common)
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    # Try common date formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%d %b %Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def format_date(date_obj: DateType, format_str: str = "%Y-%m-%d") -> str:
    """
    Format a date object or string to a specified format.

    Args:
        date_obj: Date object or string
        format_str: Format string

    Returns:
        Formatted date string
    """
    if isinstance(date_obj, str):
        date = parse_date(date_obj)
        if not date:
            return date_obj
    else:
        date = date_obj

    return date.strftime(format_str)


def to_iso_format(date_obj: DateType) -> str:
    """
    Convert a date object or string to ISO format.

    Args:
        date_obj: Date object or string

    Returns:
        ISO formatted date string
    """
    if isinstance(date_obj, str):
        date = parse_date(date_obj)
        if not date:
            return date_obj
    else:
        date = date_obj

    return date.isoformat()


def calculate_next_occurrence(start_date: DateType, frequency: str,
                              last_run: Optional[DateType] = None) -> datetime:
    """
    Calculate the next occurrence based on frequency.

    Args:
        start_date: Start date for recurrence
        frequency: Frequency (daily, weekly, monthly)
        last_run: Last run date, if any

    Returns:
        Next occurrence datetime
    """
    if isinstance(start_date, str):
        start = parse_date(start_date) or datetime.now()
    else:
        start = start_date

    if last_run:
        if isinstance(last_run, str):
            base_date = parse_date(last_run) or start
        else:
            base_date = last_run
    else:
        base_date = start

    now = datetime.now()
    if base_date < now:
        base_date = now

    if frequency == "daily":
        next_date = base_date + timedelta(days=1)
    elif frequency == "weekly":
        next_date = base_date + timedelta(weeks=1)
    elif frequency == "monthly":
        # Add a month (approximately)
        year = base_date.year + ((base_date.month + 1) // 12)
        month = ((base_date.month + 1) % 12) or 12
        day = min(base_date.day, [31, 29 if is_leap_year(
            year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
        next_date = base_date.replace(year=year, month=month, day=day)
    else:
        next_date = base_date + timedelta(days=1)  # Default to daily

    return next_date


def is_leap_year(year: int) -> bool:
    """
    Check if a year is a leap year.

    Args:
        year: Year to check

    Returns:
        True if leap year, False otherwise
    """
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def time_ago(date: DateType) -> str:
    """
    Get a human-readable string of how long ago a date was.

    Args:
        date: Date to check

    Returns:
        Human-readable string
    """
    if isinstance(date, str):
        parsed_date = parse_date(date)
        if not parsed_date:
            return "Unknown time"
        date = parsed_date

    now = datetime.now()
    diff = now - date

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif seconds < 2592000:  # 30 days
        days = int(seconds // 86400)
        return f"{days} day{'s' if days > 1 else ''} ago"
    elif seconds < 31536000:  # 365 days
        months = int(seconds // 2592000)
        return f"{months} month{'s' if months > 1 else ''} ago"
    else:
        years = int(seconds // 31536000)
        return f"{years} year{'s' if years > 1 else ''} ago"
