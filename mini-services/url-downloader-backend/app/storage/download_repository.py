"""
In-memory download repository with async locking.

Provides CRUD operations for download metadata.
Designed to be replaceable with persistent storage (SQLite, PostgreSQL, Redis).

Note: In-memory storage is lost on backend restart.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional

from app.models.download import DownloadStatus
from app.schemas.download import DownloadResponse

logger = logging.getLogger(__name__)


class DownloadRecord:
    """Internal record for storing download data."""

    def __init__(
        self,
        id: str,
        url: str,
        filename: str,
        status: DownloadStatus = DownloadStatus.QUEUED,
        downloaded_bytes: int = 0,
        total_bytes: Optional[int] = None,
        progress_percentage: float = 0.0,
        speed_bytes_per_second: float = 0.0,
        estimated_seconds_remaining: Optional[float] = None,
        error: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        self.id = id
        self.url = url
        self.filename = filename
        self.status = status
        self.downloaded_bytes = downloaded_bytes
        self.total_bytes = total_bytes
        self.progress_percentage = progress_percentage
        self.speed_bytes_per_second = speed_bytes_per_second
        self.estimated_seconds_remaining = estimated_seconds_remaining
        self.error = error
        self.file_path = file_path
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def to_response(self) -> dict:
        """Convert to API response dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "filename": self.filename,
            "status": self.status.value,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "progress_percentage": self.progress_percentage,
            "speed_bytes_per_second": self.speed_bytes_per_second,
            "estimated_seconds_remaining": self.estimated_seconds_remaining,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DownloadRepository:
    """
    In-memory repository for download records.

    Thread-safe implementation using asyncio locks.
    """

    def __init__(self):
        self._downloads: dict[str, DownloadRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, record: DownloadRecord) -> DownloadRecord:
        """
        Create a new download record.

        Args:
            record: The download record to store

        Returns:
            The created record
        """
        async with self._lock:
            if record.id in self._downloads:
                raise ValueError(f"Download with ID {record.id} already exists")
            self._downloads[record.id] = record
            logger.debug(f"Created download record: {record.id}")
            return record

    async def get(self, download_id: str) -> Optional[DownloadRecord]:
        """
        Get a download record by ID.

        Args:
            download_id: UUID of the download

        Returns:
            The download record or None if not found
        """
        async with self._lock:
            return self._downloads.get(download_id)

    async def list(
        self,
        status: Optional[DownloadStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[DownloadRecord], int]:
        """
        List download records with optional filtering.

        Args:
            status: Filter by status (optional)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (list of records, total count)
        """
        async with self._lock:
            records = list(self._downloads.values())

            # Filter by status if specified
            if status:
                records = [r for r in records if r.status == status]

            # Sort by created_at descending (newest first)
            records.sort(key=lambda r: r.created_at, reverse=True)

            total = len(records)

            # Apply pagination
            paginated_records = records[offset:offset + limit]

            return paginated_records, total

    async def update(self, download_id: str, **kwargs) -> Optional[DownloadRecord]:
        """
        Update a download record's fields.

        Args:
            download_id: UUID of the download
            **kwargs: Fields to update

        Returns:
            Updated record or None if not found
        """
        async with self._lock:
            record = self._downloads.get(download_id)
            if not record:
                return None

            # Update allowed fields
            updatable_fields = {
                "filename", "status", "downloaded_bytes", "total_bytes",
                "progress_percentage", "speed_bytes_per_second",
                "estimated_seconds_remaining", "error", "file_path",
            }

            for key, value in kwargs.items():
                if key in updatable_fields:
                    setattr(record, key, value)

            # Always update timestamp
            record.updated_at = datetime.now(timezone.utc)

            logger.debug(f"Updated download record: {download_id}")
            return record

    async def delete(self, download_id: str) -> bool:
        """
        Delete a download record.

        Args:
            download_id: UUID of the download

        Returns:
            True if deleted, False if not found
        """
        async with self._lock:
            if download_id not in self._downloads:
                return False

            del self._downloads[download_id]
            logger.debug(f"Deleted download record: {download_id}")
            return True

    async def get_active_count(self) -> int:
        """
        Count active (non-terminal) downloads.

        Returns:
            Number of active downloads
        """
        async with self._lock:
            return sum(
                1 for r in self._downloads.values()
                if r.status.is_active
            )


# Global repository instance
repository = DownloadRepository()


def get_repository() -> DownloadRepository:
    """Get the global repository instance."""
    return repository
