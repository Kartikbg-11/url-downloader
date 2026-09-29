"""
Download API endpoints.

Provides CRUD operations for downloads and file retrieval.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import FileResponse, StreamingResponse

from app.core.config import get_settings
from app.core.exceptions import (
    DownloadError,
    DownloadNotFoundError,
    InvalidDownloadStateError,
)
from app.models.download import DownloadStatus
from app.schemas.download import (
    DownloadCreateRequest,
    DownloadListResponse,
    DownloadResponse,
    ErrorResponse,
    MediaInfoRequest,
    MediaInfoResponse,
)
from app.services.download_manager import get_download_manager
from app.services.file_service import get_file_service
from app.storage.download_repository import get_repository
from app.utils.network import redact_sensitive_params

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/downloads", tags=["Downloads"])


@router.post(
    "",
    response_model=DownloadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: {"description": "Download accepted and queued"},
        400: {"model": ErrorResponse, "description": "Invalid URL or request"},
        403: {"model": ErrorResponse, "description": "URL blocked for security"},
        429: {"model": ErrorResponse, "description": "Too many concurrent downloads"},
    },
    summary="Start Download",
    description="Submit a URL to start a new download. Returns immediately with download ID for progress tracking.",
)
async def create_download(request: DownloadCreateRequest) -> dict:
    """
    Create a new download task.

    Validates the URL and starts an async download process.
    Returns immediately with a download ID for tracking progress.
    """
    manager = get_download_manager()

    try:
        record = await manager.create_download(
            request.url,
            request.format_id,
            request.media_type,
        )
        logger.info(f"Download created: {record.id}")
        return record.to_response()

    except DownloadError as e:
        raise HTTPException(status_code=e.status_code, detail=e.to_dict())


@router.post(
    "/media-info",
    response_model=MediaInfoResponse,
    summary="Inspect public media formats",
)
async def media_info(request: MediaInfoRequest) -> dict:
    from app.services.media_service import get_media_service
    from app.services.url_validator import URLValidator

    valid, message = URLValidator().validate_format(request.url)
    if not valid:
        raise HTTPException(status_code=400, detail={
            "error": {"code": "INVALID_URL", "message": message}
        })
    try:
        result = await get_media_service().get_info(request.url)
        if not result["formats"]:
            raise ValueError("No downloadable audio or video formats were found.")
        return result
    except Exception as exc:
        logger.warning(f"Media inspection failed: {exc}")
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "MEDIA_INFO_FAILED",
                "message": f"Could not read media formats: {exc}",
            }
        })


@router.get(
    "",
    response_model=DownloadListResponse,
    summary="List Downloads",
    description="Get list of all downloads with optional filtering and pagination.",
)
async def list_downloads(
    status: Optional[str] = Query(
        None,
        description="Filter by status (queued, validating, downloading, completed, failed, cancelled)",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of results",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip",
    ),
) -> dict:
    """
    List all downloads.

    Supports filtering by status and pagination.
    """
    repository = get_repository()

    # Parse status filter if provided
    status_filter = None
    if status:
        try:
            status_filter = DownloadStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_STATUS",
                        "message": f"Invalid status '{status}'. Valid values: {[s.value for s in DownloadStatus]}",
                    }
                },
            )

    records, total = await repository.list(
        status=status_filter,
        limit=limit,
        offset=offset,
    )

    return {
        "downloads": [r.to_response() for r in records],
        "total": total,
    }


@router.get(
    "/{download_id}",
    response_model=DownloadResponse,
    responses={
        200: {"description": "Download found"},
        404: {"model": ErrorResponse, "description": "Download not found"},
    },
    summary="Get Download Status",
    description="Get detailed status of a specific download by its ID.",
)
async def get_download(download_id: str) -> dict:
    """
    Get download details by ID.

    Returns current status, progress, and metadata.
    """
    repository = get_repository()
    record = await repository.get(download_id)

    if not record:
        raise HTTPError(status_code=404, detail={
            "error": {
                "code": "DOWNLOAD_NOT_FOUND",
                "message": f"Download with ID '{download_id}' was not found.",
            }
        })

    return record.to_response()


@router.get(
    "/{download_id}/events",
    summary="Progress Events (SSE)",
    description="Server-Sent Events stream for real-time download progress updates.",
    responses={
        200: {
            "description": "SSE event stream",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "status": {"type": "string"},
                            "downloaded_bytes": {"type": "integer"},
                            "total_bytes": {"type": "integer", "nullable": True},
                            "progress_percentage": {"type": "number"},
                            "speed_bytes_per_second": {"type": "number"},
                            "estimated_seconds_remaining": {"type": "number", "nullable": True},
                        },
                    }
                },
            },
        },
        404: {"model": ErrorResponse, "description": "Download not found"},
    },
)
async def download_events(download_id: str):
    """
    Server-Sent Events endpoint for real-time progress.

    Sends progress updates as they happen, including:
    - Status changes
    - Progress percentage updates
    - Speed calculations
    - ETA estimates
    - Terminal events on completion/failure/cancellation

    Also sends heartbeat events every 15 seconds to prevent connection timeout.
    """
    import asyncio
    import json

    from app.storage.download_repository import get_repository

    repository = get_repository()
    manager = get_download_manager()

    # Verify download exists
    record = await repository.get(download_id)
    if not record:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "DOWNLOAD_NOT_FOUND",
                "message": f"Download with ID '{download_id}' was not found.",
            }
        })

    # Create event generator
    async def event_generator():
        queue = manager.subscribe_to_events(download_id)

        try:
            # Send initial state
            yield format_sse_event(record.to_response())

            # If already in terminal state, send one event and close
            if record.status.is_terminal:
                yield format_sse_event({
                    **record.to_response(),
                    "terminal": True,
                })
                return

            # Stream events
            heartbeat_interval = 15  # seconds
            while True:
                try:
                    # Wait for event with timeout for heartbeats
                    try:
                        event_data = await asyncio.wait_for(
                            queue.get(),
                            timeout=heartbeat_interval,
                        )
                        yield format_sse_event(event_data)

                        # Close connection on terminal event
                        if event_data.get("terminal"):
                            return

                    except asyncio.TimeoutError:
                        # Send heartbeat
                        yield format_sse_event({
                            "id": download_id,
                            "type": "heartbeat",
                        })

                except asyncio.CancelledError:
                    logger.debug(f"SSE client disconnected from {download_id}")
                    return

        finally:
            manager.unsubscribe_from_events(download_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{download_id}/file",
    responses={
        200: {
            "description": "File content",
            "content": {"application/octet-stream": {}},
        },
        404: {"model": ErrorResponse, "description": "Download not found"},
        409: {"model": ErrorResponse, "description": "Download not completed"},
    },
    summary="Download File",
    description="Retrieve the downloaded file. Only available after download completes successfully.",
)
async def get_file(download_id: str):
    """
    Get the downloaded file.

    Only works when download status is 'completed'.
    Uses Content-Disposition header for proper filename handling.
    """
    repository = get_repository()
    file_service = get_file_service()

    record = await repository.get(download_id)
    if not record:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "DOWNLOAD_NOT_FOUND",
                "message": f"Download with ID '{download_id}' was not found.",
            }
        })

    if record.status != DownloadStatus.COMPLETED:
        raise HTTPException(status_code=409, detail={
            "error": {
                "code": "DOWNLOAD_NOT_COMPLETED",
                "message": f"File is not available. Current status: {record.status.value}",
            }
        })

    if not record.file_path:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "FILE_NOT_FOUND",
                "message": "The downloaded file could not be found on disk.",
            }
        })

    from pathlib import Path
    filepath = Path(record.file_path)

    if not filepath.exists():
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "FILE_NOT_FOUND",
                "message": "The downloaded file could not be found on disk.",
            }
        })

    return FileResponse(
        path=str(filepath),
        filename=record.filename,
        media_type="application/octet-stream",
    )


@router.post(
    "/{download_id}/cancel",
    response_model=DownloadResponse,
    responses={
        200: {"description": "Cancellation requested"},
        404: {"model": ErrorResponse, "description": "Download not found"},
        409: {"model": ErrorResponse, "description": "Cannot cancel this download"},
    },
    summary="Cancel Download",
    description="Cancel an active download. Removes partial files.",
)
async def cancel_download(download_id: str) -> dict:
    """
    Cancel an active download.

    Stops the download process and cleans up partial files.
    """
    manager = get_download_manager()

    try:
        await manager.cancel_download(download_id)

        # Return updated record
        repository = get_repository()
        record = await repository.get(download_id)
        if record:
            return record.to_response()

        return {"id": download_id, "status": "cancelled"}

    except DownloadNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.to_dict())
    except InvalidDownloadStateError as e:
        raise HTTPException(status_code=409, detail=e.to_dict())


@router.delete(
    "/{download_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Download deleted successfully"},
        404: {"model": ErrorResponse, "description": "Download not found"},
        409: {"model": ErrorResponse, "description": "Cannot delete active download"},
    },
    summary="Delete Download",
    description="Delete a completed or failed download and remove its file.",
)
async def delete_download(download_id: str) -> Response:
    """
    Delete a download record and its file.

    Only works for terminal states (completed, failed, cancelled).
    """
    manager = get_download_manager()

    try:
        await manager.delete_download(download_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except DownloadNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.to_dict())
    except InvalidDownloadStateError as e:
        raise HTTPException(status_code=409, detail=e.to_dict())


# --- Helper functions ---

def format_sse_event(data: dict) -> str:
    """Format data as a Server-Sent Event."""
    import json
    return f"data: {json.dumps(data)}\n\n"


def HTTPException(*args, **kwargs):
    """Alias for FastAPI's HTTPException."""
    from fastapi import HTTPException as _HTTPException
    return _HTTPException(*args, **kwargs)


def HTTPError(*args, **kwargs):
    """Alias for HTTPException."""
    return HTTPException(*args, **kwargs)
