"""
Custom exception classes for the URL Downloader application.

Each exception has a machine-readable code and user-friendly message.
"""


class DownloadError(Exception):
    """Base exception for all download-related errors."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)

    def to_dict(self) -> dict:
        """Convert to API error response format."""
        return {"error": {"code": self.code, "message": self.message}}


class InvalidURLError(DownloadError):
    """Raised when the URL format is invalid."""

    def __init__(self, message: str = "The provided URL is invalid."):
        super().__init__("INVALID_URL", message)


class UnsafeURLError(DownloadError):
    """Raised when the URL targets unsafe resources (SSRF protection)."""

    def __init__(self, message: str = "The provided URL is not allowed for security reasons."):
        super().__init__("UNSAFE_URL", message, status_code=403)


class PrivateNetworkBlockedError(DownloadError):
    """Raised when URL resolves to private network address."""

    def __init__(self, message: str = "The URL resolves to a private or local network address which is blocked."):
        super().__init__("PRIVATE_NETWORK_BLOCKED", message, status_code=403)


class RemoteFileNotFoundError(DownloadError):
    """Raised when the remote file returns 404."""

    def __init__(self, message: str = "The remote file was not found (HTTP 404)."):
        super().__init__("REMOTE_FILE_NOT_FOUND", message, status_code=404)


class RemoteAccessDeniedError(DownloadError):
    """Raised when access to remote file is denied."""

    def __init__(self, message: str = "Access to the remote file was denied (HTTP 403)."):
        super().__init__("REMOTE_ACCESS_DENIED", message, status_code=403)


class TooManyRedirectsError(DownloadError):
    """Raised when redirect limit is exceeded."""

    def __init__(self, message: str = "Too many redirects. The URL may be part of a redirect loop."):
        super().__init__("TOO_MANY_REDIRECTS", message)


class FileTooLargeError(DownloadError):
    """Raised when file exceeds maximum size limit."""

    def __init__(self, message: str = None):
        msg = message or "The remote file exceeds the configured maximum download size."
        super().__init__("FILE_TOO_LARGE", msg)


class UnsupportedFileTypeError(DownloadError):
    """Raised when file type is not in the allowlist."""

    def __init__(self, message: str = "The file type is not supported. Only direct-download URLs with allowed extensions are accepted."):
        super().__init__("UNSUPPORTED_FILE_TYPE", message)


class HTMLResponseError(DownloadError):
    """Raised when server returns HTML instead of downloadable content."""

    def __init__(self, message: str = "The supplied URL appears to be a webpage rather than a direct downloadable file. Please provide the authorized direct download link."):
        super().__init__("HTML_RESPONSE", message)


class RemoteServerError(DownloadError):
    """Raised when remote server returns 5xx error."""

    def __init__(self, status_code: int = 500, message: str = "The remote server encountered an error."):
        super().__init__("REMOTE_SERVER_ERROR", message, status_code=status_code)


class DownloadTimeoutError(DownloadError):
    """Raised when download times out."""

    def __init__(self, message: str = "The download timed out. The server may be slow or unreachable."):
        super().__init__("DOWNLOAD_TIMEOUT", message, status_code=504)


class DownloadCancelledError(DownloadError):
    """Raised when download is cancelled by user."""

    def __init__(self, message: str = "The download was cancelled."):
        super().__init__("DOWNLOAD_CANCELLED", message)


class DownloadFailedError(DownloadError):
    """Raised when download fails for unknown reason."""

    def __init__(self, message: str = "The download failed due to an unexpected error."):
        super().__init__("DOWNLOAD_FAILED", message, status_code=500)


class DownloadNotFoundError(DownloadError):
    """Raised when download ID is not found."""

    def __init__(self, message: str = "The specified download was not found."):
        super().__init__("DOWNLOAD_NOT_FOUND", message, status_code=404)


class InvalidDownloadStateError(DownloadError):
    """Raised when operation is invalid for current state."""

    def __init__(self, message: str = "The operation is not valid for the current download state."):
        super().__init__("INVALID_DOWNLOAD_STATE", message, status_code=409)
