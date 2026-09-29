"""
Download status enumeration.

Defines all possible states for a download operation.
"""

from enum import Enum


class DownloadStatus(str, Enum):
    """Status of a download operation."""

    QUEUED = "queued"
    VALIDATING = "validating"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state (no further transitions)."""
        return self in {
            DownloadStatus.COMPLETED,
            DownloadStatus.FAILED,
            DownloadStatus.CANCELLED,
        }

    @property
    def is_active(self) -> bool:
        """Check if this is an active/running state."""
        return self in {
            DownloadStatus.QUEUED,
            DownloadStatus.VALIDATING,
            DownloadStatus.DOWNLOADING,
        }
