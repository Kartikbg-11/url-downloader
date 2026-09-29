"""
URL validation service.

Validates URLs for format, security, and accessibility.
"""

import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

import httpx
from app.core.config import get_settings
from app.core.exceptions import (
    HTMLResponseError,
    InvalidURLError,
    RemoteFileNotFoundError,
    RemoteServerError,
    TooManyRedirectsError,
    UnsupportedFileTypeError,
)
from app.core.security import validate_url_for_ssrf

logger = logging.getLogger(__name__)

# Common HTML content types that indicate a webpage
HTML_CONTENT_TYPES = {
    "text/html",
    "text/html; charset=utf-8",
    "text/html; charset=iso-8859-1",
    "application/xhtml+xml",
}


class URLValidator:
    """Validates URLs before initiating downloads."""

    def __init__(self):
        self.settings = get_settings()

    def validate_format(self, url: str) -> Tuple[bool, str]:
        """
        Validate basic URL format.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not url or not url.strip():
            return False, "URL cannot be empty."

        url = url.strip()

        # Check for whitespace or control characters
        if any(c.isspace() or ord(c) < 32 for c in url):
            return False, "URL contains invalid characters."

        try:
            parsed = urlparse(url)
        except Exception:
            return False, "Could not parse URL format."

        # Must have scheme and netloc
        if not parsed.scheme:
            return False, "URL must include scheme (http:// or https://)."

        if not parsed.netloc:
            return False, "URL must include a hostname."

        # Only allow http/https
        if parsed.scheme.lower() not in ("http", "https"):
            return False, f"URL scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are supported."

        # Validate hostname exists and looks reasonable
        hostname = parsed.hostname
        if not hostname:
            return False, "URL does not contain a valid hostname."

        # Basic hostname length check
        if len(hostname) > 253:
            return False, "Hostname is too long."

        # Check for obviously invalid hostnames
        if hostname.startswith("-") or hostname.endswith("-"):
            return False, "Hostname is invalid."

        return True, ""

    async def validate_security(
        self,
        url: str,
        client: httpx.AsyncClient,
    ) -> Tuple[bool, str]:
        """
        Perform security validation including SSRF protection.

        Args:
            url: URL to validate
            client: HTTP client for DNS resolution

        Returns:
            Tuple of (is_safe, error_message)
        """
        is_safe, error_msg = await validate_url_for_ssrf(url, client)
        return is_safe, error_msg

    async def check_remote_file(
        self,
        url: str,
        client: httpx.AsyncClient,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """
        Check remote file metadata without downloading.

        Returns:
            Tuple of (metadata_dict, error_message)
        """
        try:
            # Use HEAD request to get metadata
            response = await client.head(
                url,
                follow_redirects=True,
                timeout=httpx.Timeout(
                    connect=self.settings.connect_timeout_seconds,
                    read=10.0,
                    write=10.0,
                    pool=self.settings.pool_timeout_seconds,
                ),
            )

            # Handle specific status codes
            if response.status_code == 404:
                raise RemoteFileNotFoundError()
            elif response.status_code == 403:
                raise app.core.exceptions.RemoteAccessDeniedError()
            elif response.status_code >= 500:
                raise RemoteServerError(
                    status_code=response.status_code,
                    message=f"Remote server returned {response.status_code}",
                )

            # Extract metadata
            content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            content_length_str = response.headers.get("content-length")
            content_disposition = response.headers.get("content-disposition")

            content_length = None
            if content_length_str:
                try:
                    content_length = int(content_length_str)
                    if content_length < 0:
                        content_length = None
                except ValueError:
                    pass

            # Check for HTML responses
            if content_type in HTML_CONTENT_TYPES:
                if not self.settings.allow_html_downloads:
                    raise HTMLResponseError()
                logger.warning(f"Allowing HTML download from {url}")

            # Check size limit
            if content_length and content_length > self.settings.max_download_size_bytes:
                max_size_mb = self.settings.max_download_size_bytes / (1024 * 1024)
                raise app.core.exceptions.FileTooLargeError(
                    message=f"File size ({content_length / (1024 * 1024):.1f} MB) exceeds maximum allowed ({max_size_mb:.1f} MB)."
                )

            metadata = {
                "content_type": content_type,
                "content_length": content_length,
                "content_disposition": content_disposition,
                "final_url": str(response.url),
                "status_code": response.status_code,
            }

            return metadata, None

        except httpx.TooManyRedirects:
            # HTTPX reports both redirect loops and overlong redirect chains
            # with TooManyRedirects. It has no RedirectLoop exception class.
            raise TooManyRedirectsError()
        except DownloadError:
            raise
        except httpx.TimeoutException:
            raise app.core.exceptions.DownloadTimeoutError(
                message="Timed out while checking remote file."
            )
        except Exception as e:
            logger.error(f"Unexpected error checking remote file: {e}")
            raise app.core.exceptions.DownloadFailedError(
                message=f"Failed to check remote file: {str(e)}"
            )

    def validate_extension(self, filename: str) -> Tuple[bool, str]:
        """
        Validate file extension against allowlist.

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Extract extension
        dot_index = filename.rfind(".")
        if dot_index == -1 or dot_index == len(filename) - 1:
            if self.settings.allow_unknown_mime_types:
                return True, ""
            return False, "File has no extension and unknown MIME types are not allowed."

        ext = filename[dot_index:].lower()

        if ext not in self.settings.allowed_extensions:
            allowed = ", ".join(self.settings.allowed_extensions)
            return False, f"File extension '{ext}' is not allowed. Allowed extensions: {allowed}"

        return True, ""

    def validate_content_type(self, content_type: str) -> Tuple[bool, str]:
        """
        Validate MIME type against allowlist.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not content_type:
            if self.settings.allow_unknown_mime_types:
                return True, ""
            return False, "Server did not provide Content-Type and unknown types are not allowed."

        content_type_lower = content_type.lower().split(";")[0].strip()

        if content_type_lower in HTML_CONTENT_TYPES:
            if self.settings.allow_html_downloads:
                return True, ""
            return False, "Server returned HTML content which is not allowed."

        if content_type_lower in self.settings.allowed_mime_types:
            return True, ""

        if self.settings.allow_unknown_mime_types:
            logger.info(f"Allowing unknown content type: {content_type}")
            return True, ""

        allowed = ", ".join(self.settings.allowed_mime_types[:5])
        if len(self.settings.allowed_mime_types) > 5:
            allowed += f"... (+{len(self.settings.allowed_mime_types) - 5} more)"
        return False, f"Content type '{content_type}' is not allowed. Allowed types include: {allowed}"


# Import needed for exception raising
import app.core.exceptions
from app.core.exceptions import DownloadError
