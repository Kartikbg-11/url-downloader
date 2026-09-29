"""
Application configuration module.

All settings are loaded from environment variables with sensible defaults.
Configuration is validated at startup to fail fast on invalid settings.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = Field(default="URL Application Downloader", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # Download settings
    download_directory: str = Field(default="downloads", alias="DOWNLOAD_DIRECTORY")
    max_download_size_bytes: int = Field(
        default=1073741824,  # 1 GB
        alias="MAX_DOWNLOAD_SIZE_BYTES",
        ge=1024,  # Minimum 1 KB
    )
    download_chunk_size_bytes: int = Field(
        default=1048576,  # 1 MB
        alias="DOWNLOAD_CHUNK_SIZE_BYTES",
        ge=1024,
    )
    max_concurrent_downloads: int = Field(
        default=3,
        alias="MAX_CONCURRENT_DOWNLOADS",
        ge=1,
        le=10,
    )
    max_redirects: int = Field(
        default=5,
        alias="MAX_REDIRECTS",
        ge=0,
        le=20,
    )

    # Timeout settings (in seconds)
    connect_timeout_seconds: float = Field(
        default=10.0,
        alias="CONNECT_TIMEOUT_SECONDS",
        ge=1.0,
        le=120.0,
    )
    read_timeout_seconds: float = Field(
        default=60.0,
        alias="READ_TIMEOUT_SECONDS",
        ge=5.0,
        le=600.0,
    )
    write_timeout_seconds: float = Field(
        default=30.0,
        alias="WRITE_TIMEOUT_SECONDS",
        ge=5.0,
        le=300.0,
    )
    pool_timeout_seconds: float = Field(
        default=10.0,
        alias="POOL_TIMEOUT_SECONDS",
        ge=1.0,
        le=120.0,
    )

    # File type validation (comma-separated)
    allowed_extensions: str = Field(
        default=".apk,.exe,.msi,.zip,.rar,.7z,.dmg,.pkg,.deb,.rpm,.tar,.gz,.pdf,.docx,.xlsx",
        alias="ALLOWED_EXTENSIONS",
    )
    allowed_mime_types: str = Field(
        default=(
            "application/octet-stream,application/zip,"
            "application/x-7z-compressed,application/vnd.android.package-archive,"
            "application/pdf"
        ),
        alias="ALLOWED_MIME_TYPES",
    )
    allow_unknown_mime_types: bool = Field(
        default=False,
        alias="ALLOW_UNKNOWN_MIME_TYPES",
    )
    allow_html_downloads: bool = Field(
        default=False,
        alias="ALLOW_HTML_DOWNLOADS",
    )

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @field_validator("allowed_extensions")
    @classmethod
    def parse_extensions(cls, v: str) -> List[str]:
        """Parse comma-separated extensions into a list."""
        exts = [ext.strip().lower() for ext in v.split(",") if ext.strip()]
        if not exts:
            raise ValueError("At least one extension must be allowed")
        return exts

    @field_validator("allowed_mime_types")
    @classmethod
    def parse_mime_types(cls, v: str) -> List[str]:
        """Parse comma-separated MIME types into a list."""
        mimes = [mime.strip().lower() for mime in v.split(",") if mime.strip()]
        return mimes

    @property
    def parsed_cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_download_directory(self) -> Path:
        """Resolve the download directory to an absolute path."""
        base_dir = Path(__file__).resolve().parents[2]
        download_dir = Path(self.download_directory)
        if download_dir.is_absolute():
            return download_dir.resolve()
        return (base_dir / download_dir).resolve()

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
