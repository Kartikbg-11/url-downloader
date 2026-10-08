"""
URL Application Downloader - Main Application Entry Point

FastAPI application for downloading files from authorized direct-download URLs
with real-time progress tracking via Server-Sent Events.
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.core.config import get_settings
from app.core.exceptions import DownloadError
from app.api import auth, health, downloads


# Configure logging
def setup_logging():
    """Configure application logging."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Reduce noise from third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    logger = logging.getLogger(__name__)

    logger.info(f"Starting {settings.app_name} v{app.version}")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Download directory: {settings.resolved_download_directory}")
    logger.info(f"Max download size: {settings.max_download_size_bytes / (1024*1024):.0f} MB")
    logger.info(f"Max concurrent downloads: {settings.max_concurrent_downloads}")

    # Ensure download directory exists
    download_dir = settings.resolved_download_directory
    download_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Ensured download directory exists: {download_dir}")

    # Cleanup any leftover temp files on startup
    try:
        from app.services.file_service import get_file_service
        file_service = get_file_service()
        cleaned = await file_service.cleanup_temp_files()
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} leftover temporary files")
    except Exception as e:
        logger.warning(f"Failed to cleanup temp files on startup: {e}")

    yield  # Application is running

    logger.info("Shutting down...")


# Create application
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Secure URL-based file downloader with real-time progress tracking. "
        "Supports direct-download URLs for various file types including APK, EXE, "
        "ZIP, PDF, and more. Features SSRF protection, streaming downloads, "
        "and Server-Sent Events for live progress updates."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Configure CORS
cors_origins = settings.parsed_cors_origins
logger.info(f"CORS origins: {cors_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
)


# Register exception handlers
@app.exception_handler(DownloadError)
async def download_error_handler(request: Request, exc: DownloadError):
    """Handle custom download errors."""
    logger.warning(f"Download error ({exc.code}): {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
            }
        },
    )


# Register routers
api_prefix = settings.api_prefix
app.include_router(health.router, prefix=api_prefix)
app.include_router(auth.router, prefix=api_prefix)
app.include_router(downloads.router, prefix=api_prefix)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": f"{api_prefix}/health",
        "downloads": f"{api_prefix}/downloads",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.app_env == "development",
    )
