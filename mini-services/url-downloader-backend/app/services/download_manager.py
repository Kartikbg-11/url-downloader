"""
Download manager service.

Handles the complete download lifecycle:
- Validation
- Streaming download with progress tracking
- Cancellation support
- SSE event broadcasting
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.core.exceptions import (
    DownloadCancelledError,
    DownloadError,
    DownloadFailedError,
    InvalidDownloadStateError,
)
from app.models.download import DownloadStatus
from app.schemas.download import ProgressEvent
from app.services.file_service import FileService, get_file_service
from app.services.url_validator import URLValidator
from app.storage.download_repository import (
    DownloadRecord,
    DownloadRepository,
    get_repository,
)
from app.utils.filename import (
    extract_filename_from_content_disposition,
    extract_filename_from_url,
    generate_fallback_filename,
    sanitize_filename,
)
from app.utils.file_size import format_file_size
from app.utils.network import redact_sensitive_params

logger = logging.getLogger(__name__)


class DownloadManager:
    """
    Manages download operations with progress tracking.

    Coordinates between repository, file service, and HTTP client.
    """

    def __init__(self):
        self.settings = get_settings()
        self.repository: DownloadRepository = get_repository()
        self.file_service: FileService = get_file_service()
        self.validator = URLValidator()

        # Track active downloads for cancellation
        self._active_downloads: dict[str, asyncio.Task] = {}
        self._cancellation_flags: dict[str, asyncio.Event] = {}

        # SSE event subscribers: {download_id: [queues]}
        self._event_subscribers: dict[str, list[asyncio.Queue]] = {}
        self._media_options: dict[str, tuple[str, str]] = {}

    async def create_download(
        self,
        url: str,
        format_id: Optional[str] = None,
        media_type: Optional[str] = None,
    ) -> DownloadRecord:
        """
        Create a new download task.

        Validates URL, creates record, starts async download.

        Args:
            url: Direct download URL

        Returns:
            Created download record (in queued state)

        Raises:
            DownloadError: If validation fails or limits exceeded
        """
        # Check concurrent download limit
        active_count = await self.repository.get_active_count()
        if active_count >= self.settings.max_concurrent_downloads:
            raise DownloadError(
                "MAX_CONCURRENT_REACHED",
                f"Maximum concurrent downloads ({self.settings.max_concurrent_downloads}) reached. Please wait for a download to complete.",
                status_code=429,
            )

        # Generate ID
        download_id = str(uuid4())

        # Initial filename from URL (will be updated after validation)
        initial_filename = sanitize_filename(extract_filename_from_url(url))

        # Create record in queued state
        record = DownloadRecord(
            id=download_id,
            url=url,
            filename=initial_filename,
            status=DownloadStatus.QUEUED,
        )
        await self.repository.create(record)
        if format_id and media_type:
            self._media_options[download_id] = (format_id, media_type)

        # Log safe URL (redacted)
        safe_url = redact_sensitive_params(url)
        logger.info(f"Created download {download_id} for {safe_url}")

        # Start background download task
        task = asyncio.create_task(
            self._execute_download(download_id),
            name=f"download-{download_id}",
        )
        self._active_downloads[download_id] = task

        return record

    async def _execute_download(self, download_id: str) -> None:
        """
        Execute the full download process asynchronously.

        This runs as a background task.
        """
        # Create cancellation flag for this download
        cancel_event = asyncio.Event()
        self._cancellation_flags[download_id] = cancel_event

        temp_filepath = None

        try:
            record = await self.repository.get(download_id)
            if not record:
                raise DownloadNotFoundError(f"Download {download_id} not found")

            # Update to validating state
            await self._update_status(download_id, DownloadStatus.VALIDATING)

            media_option = self._media_options.get(download_id)
            if media_option:
                await self._execute_media_download(
                    download_id,
                    record.url,
                    media_option[0],
                    media_option[1],
                )
                return

            # Set up HTTP client with timeout settings
            timeout = httpx.Timeout(
                connect=self.settings.connect_timeout_seconds,
                read=self.settings.read_timeout_seconds,
                write=self.settings.write_timeout_seconds,
                pool=self.settings.pool_timeout_seconds,
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                max_redirects=self.settings.max_redirects,
            ) as client:
                # Step 1: Validate URL security
                is_safe, error_msg = await self.validator.validate_security(
                    record.url, client
                )
                if not is_safe:
                    raise app.core.exceptions.UnsafeURLError(error_msg)

                # Step 2: Check remote file metadata
                metadata, error_msg = await self.validator.check_remote_file(
                    record.url, client
                )
                if error_msg:
                    raise DownloadFailedError(error_msg)

                # Check for cancellation before proceeding
                if cancel_event.is_set():
                    raise DownloadCancelledError()

                content_type = metadata.get("content_type", "")
                content_length = metadata.get("content_length")
                content_disposition = metadata.get("content_disposition")
                final_url = metadata.get("final_url", record.url)

                # Step 3: Determine filename
                filename = None

                # Try Content-Disposition first
                if content_disposition:
                    filename = extract_filename_from_content_disposition(content_disposition)

                # Fall back to final URL path
                if not filename:
                    filename = extract_filename_from_url(final_url)

                # Generate fallback if still no filename
                if not filename or filename == "download":
                    extension = self._guess_extension(content_type)
                    filename = generate_fallback_filename(download_id, extension)

                # Step 4: Validate extension
                ext_valid, ext_error = self.validator.validate_extension(filename)
                if not ext_valid:
                    raise app.core.exceptions.UnsupportedFileTypeError(ext_error)

                # Step 5: Validate content type
                mime_valid, mime_error = self.validator.validate_content_type(content_type)
                if not mime_valid:
                    raise app.core.exceptions.UnsupportedFileTypeError(mime_error)

                # Update record with validated info
                await self.repository.update(
                    download_id,
                    filename=filename,
                    total_bytes=content_length,
                )

                # Check for cancellation again
                if cancel_event.is_set():
                    raise DownloadCancelledError()

                # Step 6: Start downloading
                await self._update_status(download_id, DownloadStatus.DOWNLOADING)

                # Create temporary file
                temp_filepath = await self.file_service.create_temp_file(filename)

                # Stream download
                downloaded_bytes = await self._stream_download(
                    download_id=download_id,
                    url=record.url,
                    temp_filepath=temp_filepath,
                    total_bytes=content_length,
                    cancel_event=cancel_event,
                    client=client,
                )

                # Step 7: Finalize file
                final_filepath = await self.file_service.finalize_file(
                    temp_filepath, filename
                )
                temp_filepath = None  # Prevent cleanup of finalized file

                # Update to completed
                await self.repository.update(
                    download_id,
                    status=DownloadStatus.COMPLETED,
                    downloaded_bytes=downloaded_bytes,
                    progress_percentage=100.0,
                    speed_bytes_per_second=0.0,
                    estimated_seconds_remaining=0.0,
                    file_path=str(final_filepath),
                )

                # Send completion event
                await self._send_progress_event(download_id, {
                    "status": DownloadStatus.COMPLETED.value,
                    "downloaded_bytes": downloaded_bytes,
                    "progress_percentage": 100.0,
                    "speed_bytes_per_second": 0.0,
                    "estimated_seconds_remaining": 0.0,
                })

                safe_url = redact_sensitive_params(record.url)
                logger.info(
                    f"Download completed: {download_id} - {filename} "
                    f"({format_file_size(downloaded_bytes)}) from {safe_url}"
                )

        except DownloadCancelledError:
            logger.info(f"Download cancelled: {download_id}")
            await self._handle_cancellation(download_id, temp_filepath)

        except DownloadError as e:
            logger.error(f"Download failed ({e.code}): {download_id} - {e.message}")
            await self._handle_failure(download_id, e.code, e.message, temp_filepath)

        except asyncio.CancelledError:
            logger.info(f"Download task cancelled: {download_id}")
            await self._handle_cancellation(download_id, temp_filepath)

        except Exception as e:
            logger.exception(f"Unexpected error in download {download_id}: {e}")
            message = str(e).strip()
            if not message:
                message = "An unexpected error occurred during download."
            await self._handle_failure(
                download_id,
                "DOWNLOAD_FAILED",
                message,
                temp_filepath,
            )

        finally:
            # Cleanup
            self._active_downloads.pop(download_id, None)
            self._cancellation_flags.pop(download_id, None)
            self._media_options.pop(download_id, None)

            # Send terminal event to close subscriber connections
            await self._send_terminal_event(download_id)

    async def _execute_media_download(
        self,
        download_id: str,
        url: str,
        format_id: str,
        media_type: str,
    ) -> None:
        """Download one of the formats selected from the media-info endpoint."""
        from app.services.media_service import get_media_service

        await self._update_status(download_id, DownloadStatus.DOWNLOADING)
        loop = asyncio.get_running_loop()

        def report_progress(data: dict) -> None:
            if data.get("status") != "downloading":
                return
            downloaded = int(data.get("downloaded_bytes") or 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            speed = float(data.get("speed") or 0)
            eta = data.get("eta")
            percentage = min(100.0, downloaded / total * 100) if total else 0.0

            async def update():
                await self.repository.update(
                    download_id,
                    downloaded_bytes=downloaded,
                    total_bytes=total,
                    progress_percentage=percentage,
                    speed_bytes_per_second=speed,
                    estimated_seconds_remaining=eta,
                )
                await self._send_progress_event(download_id, {
                    "status": DownloadStatus.DOWNLOADING.value,
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "progress_percentage": percentage,
                    "speed_bytes_per_second": speed,
                    "estimated_seconds_remaining": eta,
                })

            loop.call_soon_threadsafe(asyncio.create_task, update())

        filepath, size = await get_media_service().download(
            download_id,
            url,
            format_id,
            media_type,
            report_progress,
        )
        await self.repository.update(
            download_id,
            filename=filepath.name.removeprefix(f"{download_id}_"),
            status=DownloadStatus.COMPLETED,
            downloaded_bytes=size,
            total_bytes=size,
            progress_percentage=100.0,
            speed_bytes_per_second=0.0,
            estimated_seconds_remaining=0.0,
            file_path=str(filepath),
        )
        await self._send_progress_event(download_id, {
            "status": DownloadStatus.COMPLETED.value,
            "downloaded_bytes": size,
            "total_bytes": size,
            "progress_percentage": 100.0,
            "speed_bytes_per_second": 0.0,
            "estimated_seconds_remaining": 0.0,
        })

    async def _stream_download(
        self,
        download_id: str,
        url: str,
        temp_filepath: object,
        total_bytes: Optional[int],
        cancel_event: asyncio.Event,
        client: httpx.AsyncClient,
    ) -> int:
        """
        Stream download with progress tracking.

        Downloads in chunks, updates progress, and checks for cancellation.

        Returns:
            Total bytes downloaded
        """
        chunk_size = self.settings.download_chunk_size_bytes
        downloaded_bytes = 0
        start_time = time.monotonic()
        last_update_time = start_time
        last_update_bytes = 0

        async with client.stream("GET", url) as response:
            response.raise_for_status()

            async for chunk in aiter_chunks(response, chunk_size):
                # Check cancellation
                if cancel_event.is_set():
                    raise DownloadCancelledError()

                # Write chunk to file
                written = await self.file_service.write_chunk(temp_filepath, chunk)
                downloaded_bytes += written

                # Calculate progress metrics
                current_time = time.monotonic()
                elapsed_since_update = current_time - last_update_time

                # Update progress every 500ms or on significant change
                if elapsed_since_update >= 0.5:
                    # Calculate speed
                    bytes_since_update = downloaded_bytes - last_update_bytes
                    speed = bytes_since_update / elapsed_since_update

                    # Calculate percentage
                    if total_bytes:
                        progress = min(100.0, (downloaded_bytes / total_bytes) * 100)
                        remaining_bytes = total_bytes - downloaded_bytes
                        eta = remaining_bytes / speed if speed > 0 else None
                    else:
                        progress = 0.0
                        eta = None

                    # Update record
                    await self.repository.update(
                        download_id,
                        downloaded_bytes=downloaded_bytes,
                        progress_percentage=progress,
                        speed_bytes_per_second=speed,
                        estimated_seconds_remaining=eta,
                    )

                    # Send SSE event
                    await self._send_progress_event(download_id, {
                        "status": DownloadStatus.DOWNLOADING.value,
                        "downloaded_bytes": downloaded_bytes,
                        "total_bytes": total_bytes,
                        "progress_percentage": progress,
                        "speed_bytes_per_second": speed,
                        "estimated_seconds_remaining": eta,
                    })

                    last_update_time = current_time
                    last_update_bytes = downloaded_bytes

                # Check size limit
                if total_bytes and downloaded_bytes > self.settings.max_download_size_bytes:
                    raise app.core.exceptions.FileTooLargeError(
                        message="Download exceeded maximum size limit."
                    )

        return downloaded_bytes

    async def cancel_download(self, download_id: str) -> bool:
        """
        Cancel an active download.

        Args:
            download_id: ID of download to cancel

        Returns:
            True if cancellation was requested

        Raises:
            DownloadNotFoundError: If download doesn't exist
            InvalidDownloadStateError: If download can't be cancelled
        """
        record = await self.repository.get(download_id)
        if not record:
            raise DownloadNotFoundError()

        if not record.status.is_active:
            raise InvalidDownloadStateError(
                f"Cannot cancel download in '{record.status.value}' state."
            )

        # Signal cancellation
        cancel_event = self._cancellation_flags.get(download_id)
        if cancel_event:
            cancel_event.set()
            logger.info(f"Cancellation signal sent for download: {download_id}")
            return True

        # Cancel the asyncio task if exists
        task = self._active_downloads.get(download_id)
        if task and not task.done():
            task.cancel()
            return True

        return False

    async def delete_download(self, download_id: str) -> bool:
        """
        Delete a download and its file.

        Args:
            download_id: ID of download to delete

        Returns:
            True if deleted

        Raises:
            DownloadNotFoundError: If download doesn't exist
            InvalidDownloadStateError: If download is still active
        """
        record = await self.repository.get(download_id)
        if not record:
            raise DownloadNotFoundError()

        if record.status.is_active:
            raise InvalidDownloadStateError(
                "Cannot delete an active download. Cancel it first."
            )

        # Delete the file
        await self.file_service.delete_file(record.file_path)

        # Remove from repository
        await self.repository.delete(download_id)

        logger.info(f"Deleted download: {download_id}")
        return True

    async def retry_download(self, download_id: str) -> DownloadRecord:
        """
        Retry a failed download.

        Args:
            download_id: ID of failed download to retry

        Returns:
            New download record

        Raises:
            DownloadNotFoundError: If download doesn't exist
            InvalidDownloadStateError: If download isn't in failed state
        """
        record = await self.repository.get(download_id)
        if not record:
            raise DownloadNotFoundError()

        if record.status != DownloadStatus.FAILED:
            raise InvalidDownloadStateError(
                "Only failed downloads can be retried."
            )

        # Clean up old record
        await self.repository.delete(download_id)

        # Create new download with same URL
        return await self.create_download(record.url)

    # --- Event subscription methods ---

    def subscribe_to_events(self, download_id: str) -> asyncio.Queue:
        """
        Subscribe to progress events for a download.

        Returns:
            Queue that will receive progress events
        """
        queue: asyncio.Queue = asyncio.Queue()

        if download_id not in self._event_subscribers:
            self._event_subscribers[download_id] = []

        self._event_subscribers[download_id].append(queue)
        logger.debug(f"New subscriber for download {download_id}")

        return queue

    def unsubscribe_from_events(self, download_id: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from progress events."""
        if download_id in self._event_subscribers:
            try:
                self._event_subscribers[download_id].remove(queue)
            except ValueError:
                pass

    async def _send_progress_event(
        self,
        download_id: str,
        data: dict,
    ) -> None:
        """Send progress event to all subscribers."""
        if download_id not in self._event_subscribers:
            return

        record = await self.repository.get(download_id)
        if not record:
            return

        event_data = {
            "id": download_id,
            **data,
        }

        dead_queues = []
        for queue in self._event_subscribers[download_id]:
            try:
                queue.put_nowait(event_data)
            except asyncio.QueueFull:
                dead_queues.append(queue)

        # Clean up dead queues
        for q in dead_queues:
            self._event_subscribers[download_id].remove(q)

    async def _send_terminal_event(self, download_id: str) -> None:
        """Send terminal event to close subscriber connections."""
        await self._send_progress_event(download_id, {"terminal": True})

    # --- Helper methods ---

    async def _update_status(
        self,
        download_id: str,
        status: DownloadStatus,
    ) -> None:
        """Update download status and send event."""
        await self.repository.update(download_id, status=status)
        await self._send_progress_event(download_id, {
            "status": status.value,
        })

    async def _handle_cancellation(
        self,
        download_id: str,
        temp_filepath: Optional[object],
    ) -> None:
        """Handle download cancellation cleanup."""
        # Cleanup temp file
        if temp_filepath:
            try:
                Path(temp_filepath).unlink(missing_ok=True)
            except Exception:
                pass

        # Update status
        await self.repository.update(
            download_id,
            status=DownloadStatus.CANCELLED,
            error="Download was cancelled by user.",
        )

        await self._send_progress_event(download_id, {
            "status": DownloadStatus.CANCELLED.value,
            "error": "Download was cancelled by user.",
        })

    async def _handle_failure(
        self,
        download_id: str,
        code: str,
        message: str,
        temp_filepath: Optional[object],
    ) -> None:
        """Handle download failure cleanup."""
        # Cleanup temp file
        if temp_filepath:
            try:
                Path(temp_filepath).unlink(missing_ok=True)
            except Exception:
                pass

        # Update status
        await self.repository.update(
            download_id,
            status=DownloadStatus.FAILED,
            error=message,
        )

        await self._send_progress_event(download_id, {
            "status": DownloadStatus.FAILED.value,
            "error": message,
        })

    @staticmethod
    def _guess_extension(content_type: str) -> Optional[str]:
        """Guess file extension from MIME type."""
        mime_ext_map = {
            "application/zip": ".zip",
            "application/x-zip-compressed": ".zip",
            "application/x-7z-compressed": ".7z",
            "application/x-rar-compressed": ".rar",
            "application/vnd.android.package-archive": ".apk",
            "application/x-msdownload": ".exe",
            "application/x-msi": ".msi",
            "application/pdf": ".pdf",
            "application/x-apple-diskimage": ".dmg",
            "application/x-debian-package": ".deb",
            "application/x-redhat-package-manager": ".rpm",
            "application/gzip": ".gz",
            "application/x-tar": ".tar",
            "application/octet-stream": ".bin",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        }

        ct_lower = content_type.lower().split(";")[0].strip() if content_type else ""
        return mime_ext_map.get(ct_lower)


# Import needed for exception handling
import app.core.exceptions
from app.core.exceptions import DownloadNotFoundError


async def aiter_chunks(response, chunk_size):
    """Async iterator over response chunks."""
    async for chunk in response.aiter_bytes(chunk_size):
        yield chunk


# Global manager instance
download_manager = DownloadManager()


def get_download_manager() -> DownloadManager:
    """Get the global download manager instance."""
    return download_manager
