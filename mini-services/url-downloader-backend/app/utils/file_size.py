"""
File size formatting utilities.
"""

from typing import Optional


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "15.2 MB")
    """
    if size_bytes < 0:
        return "Unknown"

    if size_bytes == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"

    return f"{size:.1f} {units[unit_index]}"


def format_speed(bytes_per_second: float) -> str:
    """
    Format download speed in human-readable format.

    Args:
        bytes_per_second: Speed in bytes per second

    Returns:
        Formatted string (e.g., "2.5 MB/s")
    """
    if bytes_per_second <= 0:
        return "0 B/s"

    size_str = format_file_size(int(bytes_per_second))
    return f"{size_str}/s"


def format_time_remaining(seconds: Optional[float]) -> str:
    """
    Format estimated time remaining.

    Args:
        seconds: Time in seconds (can be None if unknown)

    Returns:
        Formatted string (e.g., "2m 30s" or "Unknown")
    """
    if seconds is None or seconds < 0:
        return "Unknown"

    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
