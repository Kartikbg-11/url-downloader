"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class DownloadCreateRequest(BaseModel):
    """Request schema for creating a new download."""

    url: str = Field(
        ...,
        description="Direct download URL for the file",
        examples=["https://example.com/files/application.zip"],
    )
    format_id: Optional[str] = Field(
        default=None,
        description="Media format identifier returned by /api/media-info",
    )
    media_type: Optional[str] = Field(
        default=None,
        pattern="^(video|audio)$",
        description="Selected media type",
    )

    model_config = {"extra": "forbid"}


class MediaInfoRequest(BaseModel):
    url: str


class MediaFormat(BaseModel):
    format_id: str
    media_type: str
    label: str
    extension: str
    filesize: Optional[int] = None


class MediaInfoResponse(BaseModel):
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    formats: list[MediaFormat]


class DownloadResponse(BaseModel):
    """Response schema for download information."""

    id: str = Field(..., description="Unique download identifier (UUID)")
    url: str = Field(..., description="Original URL requested")
    filename: str = Field(..., description="Sanitized filename")
    status: str = Field(..., description="Current download status")
    downloaded_bytes: int = Field(
        default=0,
        description="Number of bytes downloaded so far",
        ge=0,
    )
    total_bytes: Optional[int] = Field(
        default=None,
        description="Total file size in bytes, if known",
    )
    progress_percentage: float = Field(
        default=0.0,
        description="Download progress as percentage (0-100)",
        ge=0.0,
        le=100.0,
    )
    speed_bytes_per_second: float = Field(
        default=0.0,
        description="Current download speed in bytes per second",
        ge=0.0,
    )
    estimated_seconds_remaining: Optional[float] = Field(
        default=None,
        description="Estimated time remaining in seconds",
        ge=0.0,
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if download failed",
    )
    created_at: datetime = Field(..., description="Timestamp when download was created")
    updated_at: datetime = Field(..., description="Timestamp of last update")

    model_config = {"from_attributes": True}


class DownloadListResponse(BaseModel):
    """Response schema for listing downloads."""

    downloads: list[DownloadResponse] = Field(default_factory=list)
    total: int = Field(default=0, description="Total number of downloads")


class ProgressEvent(BaseModel):
    """Schema for SSE progress events."""

    id: str = Field(..., description="Download ID")
    status: str = Field(..., description="Current status")
    downloaded_bytes: int = Field(default=0)
    total_bytes: Optional[int] = Field(default=None)
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    speed_bytes_per_second: float = Field(default=0.0, ge=0.0)
    estimated_seconds_remaining: Optional[float] = Field(default=None)

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: dict = Field(
        ...,
        description="Error details with code and message",
        examples=[{"code": "INVALID_URL", "message": "The provided URL is invalid."}],
    )


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="healthy", description="Service health status")
