"""
File service for managing downloaded files on disk.

Handles file writing, renaming, and cleanup operations.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

import aiofiles

from app.core.config import get_settings
from app.utils.filename import get_unique_filepath, is_safe_path

logger = logging.getLogger(__name__)


class FileService:
    """Service for managing downloaded files."""

    def __init__(self):
        self.settings = get_settings()
        self.download_dir = self.settings.resolved_download_directory

    async def ensure_directory(self) -> Path:
        """
        Ensure the download directory exists.

        Returns:
            Path to the download directory
        """
        self.download_dir.mkdir(parents=True, exist_ok=True)
        return self.download_dir

    async def create_temp_file(self, filename: str) -> Path:
        """
        Create a temporary .part file for downloading.

        Args:
            filename: Desired filename

        Returns:
            Path to the temporary file
        """
        await self.ensure_directory()

        temp_filename = f"{filename}.part"
        filepath = get_unique_filepath(self.download_dir, temp_filename)

        # Verify path is safe
        if not is_safe_path(self.download_dir, filepath):
            raise ValueError(f"Path traversal detected: {filepath}")

        # Create empty file
        async with aiofiles.open(filepath, "wb") as f:
            pass

        logger.debug(f"Created temp file: {filepath}")
        return filepath

    async def write_chunk(
        self,
        filepath: Path,
        data: bytes,
    ) -> int:
        """
        Write a chunk of data to a file.

        Args:
            filepath: Path to write to
            data: Data to write

        Returns:
            Number of bytes written
        """
        async with aiofiles.open(filepath, "ab") as f:
            written = await f.write(data)
            # Flush to ensure data is written
            await f.flush()
        return written

    async def finalize_file(
        self,
        temp_filepath: Path,
        final_filename: str,
    ) -> Path:
        """
        Rename temporary file to final filename.

        Args:
            temp_filepath: Path to .part file
            final_filename: Final desired filename

        Returns:
            Path to final file
        """
        # Generate unique final path
        final_filepath = get_unique_filepath(self.download_dir, final_filename)

        # Safety check
        if not is_safe_path(self.download_dir, final_filepath):
            raise ValueError(f"Path traversal detected: {final_filepath}")

        # Rename the file
        temp_filepath.rename(final_filepath)

        logger.info(f"Finalized file: {final_filepath.name}")
        return final_filepath

    async def delete_file(self, filepath: Optional[str]) -> bool:
        """
        Delete a downloaded file.

        Args:
            filepath: Path string to delete (can be None)

        Returns:
            True if deleted or didn't exist, False on error
        """
        if not filepath:
            return True

        try:
            path = Path(filepath)

            # Security check - only allow deletion within download dir
            if not is_safe_path(self.download_dir, path):
                logger.warning(f"Attempted to delete file outside download dir: {filepath}")
                return False

            if path.exists():
                path.unlink()
                logger.debug(f"Deleted file: {filepath}")

            return True
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")
            return False

    async def cleanup_temp_files(self) -> int:
        """
        Clean up any leftover .part files from interrupted downloads.

        Returns:
            Number of files cleaned up
        """
        await self.ensure_directory()

        cleaned = 0
        for part_file in self.download_dir.glob("*.part"):
            try:
                part_file.unlink()
                cleaned += 1
                logger.debug(f"Cleaned up temp file: {part_file.name}")
            except Exception as e:
                logger.warning(f"Failed to clean up {part_file}: {e}")

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} temporary files")

        return cleaned

    def get_relative_path(self, filepath: Path) -> str:
        """
        Get relative path for API responses (hides server filesystem structure).

        Args:
            filepath: Absolute path

        Returns:
            Relative path string
        """
        try:
            return str(filepath.relative_to(self.download_dir))
        except ValueError:
            return filepath.name


# Global service instance
file_service = FileService()


def get_file_service() -> FileService:
    """Get the global file service instance."""
    return file_service
