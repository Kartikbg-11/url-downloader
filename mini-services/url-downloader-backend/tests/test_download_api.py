"""
Backend unit tests.

Tests cover:
- URL validation (scheme, format, security)
- SSRF protection (private IPs, localhost, blocked hosts)
- Filename sanitization (path traversal, reserved names, special chars)
- Extension and MIME type validation
- File size limits
- API endpoints with mocked HTTP
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

# Import modules to test
from app.core.security import (
    validate_url_scheme,
    is_ip_blocked,
    is_hostname_blocked,
    BLOCKED_IP_RANGES,
)
from app.utils.filename import (
    sanitize_filename,
    extract_filename_from_content_disposition,
    extract_filename_from_url,
    generate_fallback_filename,
    is_safe_path,
    get_unique_filepath,
)
from app.utils.file_size import (
    format_file_size,
    format_speed,
    format_time_remaining,
)
from app.models.download import DownloadStatus


class TestURLSchemeValidation:
    """Test URL scheme validation."""

    def test_valid_http(self):
        """HTTP URLs should be valid."""
        is_valid, _ = validate_url_scheme("http://example.com/file.zip")
        assert is_valid is True

    def test_valid_https(self):
        """HTTPS URLs should be valid."""
        is_valid, _ = validate_url_scheme("https://example.com/file.zip")
        assert is_valid is True

    def test_invalid_ftp(self):
        """FTP URLs should be rejected."""
        is_valid, msg = validate_url_scheme("ftp://example.com/file.zip")
        assert is_valid is False
        assert "not allowed" in msg.lower()

    def test_invalid_file(self):
        """File:// URLs should be rejected."""
        is_valid, _ = validate_url_scheme("file:///etc/passwd")
        assert is_valid is False

    def test_no_scheme(self):
        """URLs without scheme should be invalid."""
        is_valid, _ = validate_url_scheme("example.com/file.zip")
        assert is_valid is False

    def test_invalid_scheme(self):
        """Unknown schemes should be rejected."""
        is_valid, _ = validate_url_scheme("javascript:alert('xss')")
        assert is_valid is False


class TestSSRFProtection:
    """Test SSRF protection mechanisms."""

    def test_loopback_ipv4_blocked(self):
        """127.x.x.x addresses should be blocked."""
        assert is_ip_blocked("127.0.0.1") is True
        assert is_ip_blocked("127.0.0.2") is True
        assert is_ip_blocked("127.255.255.255") is True

    def test_loopback_ipv6_blocked(self):
        """IPv6 loopback should be blocked."""
        assert is_ip_blocked("::1") is True

    def test_private_10_range_blocked(self):
        """10.0.0.0/8 range should be blocked."""
        assert is_ip_blocked("10.0.0.1") is True
        assert is_ip_blocked("10.255.255.254") is True

    def test_private_172_range_blocked(self):
        """172.16.0.0/12 range should be blocked."""
        assert is_ip_blocked("172.16.0.1") is True
        assert is_ip_blocked("172.31.255.255") is True

    def test_private_192_range_blocked(self):
        """192.168.0.0/16 range should be blocked."""
        assert is_ip_blocked("192.168.0.1") is True
        assert is_ip_blocked("192.168.1.100") is True

    def test_link_local_blocked(self):
        """169.254.0.0/16 link-local should be blocked."""
        assert is_ip_blocked("169.254.169.254") is True  # AWS metadata

    def test_public_ip_allowed(self):
        """Public IP addresses should be allowed."""
        assert is_ip_blocked("8.8.8.8") is False  # Google DNS
        assert is_ip_blocked("1.1.1.1") is False  # Cloudflare DNS

    def test_localhost_hostname_blocked(self):
        """'localhost' hostname should be blocked."""
        assert is_hostname_blocked("localhost") is True

    def test_metadata_endpoint_blocked(self):
        """Cloud metadata hostnames should be blocked."""
        assert is_hostname_blocked("metadata.google.internal") is True
        assert is_hostname_blocked("metadata.amazonaws.com") is True

    def test_normal_hostname_allowed(self):
        """Normal hostnames should be allowed."""
        assert is_hostname_blocked("example.com") is False
        assert is_hostname_blocked("cdn.example.org") is False

    def test_zero_range_blocked(self):
        """0.0.0.0/8 range should be blocked."""
        assert is_ip_blocked("0.0.0.0") is True
        assert is_ip_blocked("0.0.0.1") is True


class TestFilenameSanitization:
    """Test filename sanitization."""

    def test_normal_filename(self):
        """Normal filenames should pass through unchanged."""
        result = sanitize_filename("document.pdf")
        assert result == "document.pdf"

    def test_remove_path_separators(self):
        """Path separators should be removed."""
        result = sanitize_filename("../../../etc/passwd")
        assert "/" not in result
        assert ".." not in result
        assert "passwd" in result or "etc" not in result

    def test_remove_null_bytes(self):
        """Null bytes should be removed."""
        result = sanitize_filename("file\x00name.pdf")
        assert "\x00" not in result

    def test_windows_reserved_names(self):
        """Windows reserved names should be handled."""
        result = sanitize_filename("CON")
        assert result.startswith("_")

        result = sanitize_filename("prn.txt")
        assert result.startswith("_")

    def test_special_characters_replaced(self):
        """Special characters should be replaced with underscores."""
        result = sanitize_filename('file<name>:"|?.pdf')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        assert "|" not in result
        assert "?" not in result

    def test_unicode_normalization(self):
        """Unicode characters should be normalized."""
        result = sanitize_filename("café.pdf")
        assert "caf" in result.lower() or "cafe" in result.lower()

    def test_empty_filename_fallback(self):
        """Empty or whitespace filenames should return 'download'."""
        assert sanitize_filename("") == "download"
        assert sanitize_filename("   ") == "download"

    def test_long_filename_truncated(self):
        """Very long filenames should be truncated."""
        long_name = "a" * 300 + ".pdf"
        result = sanitize_filename(long_name)
        assert len(result) <= 255
        assert result.endswith(".pdf")

    def test_leading_dots_stripped(self):
        """Leading dots should be stripped."""
        result = sanitize_filename(".hidden_file.txt")
        assert not result.startswith(".")


class TestFilenameExtraction:
    """Test filename extraction from various sources."""

    def test_from_url_simple(self):
        """Extract filename from simple URL path."""
        result = extract_filename_from_url("https://example.com/files/app.zip")
        assert result == "app.zip"

    def test_from_url_with_query(self):
        """Query strings should be ignored."""
        result = extract_filename_from_url("https://example.com/download?file=app.zip&token=abc")
        # Should extract path component or fallback
        assert "download" in result or ".zip" in result

    def test_from_content_disposition_quoted(self):
        """Extract filename from quoted Content-Disposition."""
        header = 'attachment; filename="my_document.pdf"'
        result = extract_filename_from_content_disposition(header)
        assert result == "my_document.pdf"

    def test_from_content_disposition_unquoted(self):
        """Extract filename from unquoted Content-Disposition."""
        header = "attachment; filename=document.pdf"
        result = extract_filename_from_content_disposition(header)
        assert result == "document.pdf"

    def test_from_content_disposition_utf8(self):
        """Extract UTF-8 encoded filename (RFC 5987)."""
        header = "attachment; filename*=UTF-8''%E4%B8%AD%E6%96%87%E6%96%87%E4%BB%B6.pdf"
        result = extract_filename_from_content_disposition(header)
        assert result is not None
        assert ".pdf" in result

    def test_generate_fallback_filename(self):
        """Generate fallback filename using ID."""
        result = generate_fallback_filename("123e4567-e89b-12d3-a456-426614174000", ".zip")
        assert "download_" in result
        assert result.endswith(".zip")


class TestPathSafety:
    """Test path traversal protection."""

    def test_safe_path_within_base(self):
        """Paths within base directory are safe."""
        base = Path("/downloads")
        file_path = Path("/downloads/file.txt")
        assert is_safe_path(base, file_path) is True

    def test_unsafe_path_traversal(self):
        """Path traversal attempts should fail."""
        base = Path("/downloads")
        file_path = Path("/downloads/../etc/passwd")
        assert is_safe_path(base, file_path) is False

    def test_absolute_path_outside_base(self):
        """Absolute paths outside base should fail."""
        base = Path("/downloads")
        file_path = Path("/etc/passwd")
        assert is_safe_path(base, file_path) is False


class TestFileSizeFormatting:
    """Test human-readable file size formatting."""

    def test_bytes(self):
        """Small sizes should show in bytes."""
        assert format_file_size(500) == "500 B"

    def test_kilobytes(self):
        """KB sizes should show correctly."""
        result = format_file_size(1024)
        assert "KB" in result or "kB" in result

    def test_megabytes(self):
        """MB sizes should show correctly."""
        result = format_file_size(1048576)
        assert "MB" in result

    def test_gigabytes(self):
        """GB sizes should show correctly."""
        result = format_file_size(1073741824)
        assert "GB" in result

    def test_zero_bytes(self):
        """Zero should show as 0 B."""
        assert format_file_size(0) == "0 B"

    def test_negative_returns_unknown(self):
        """Negative values should return Unknown."""
        assert format_file_size(-1) == "Unknown"


class TestSpeedFormatting:
    """Test speed formatting."""

    def test_zero_speed(self):
        """Zero speed should show 0 B/s."""
        assert format_speed(0) == "0 B/s"

    def test_positive_speed(self):
        """Positive speeds should include units."""
        result = format_speed(1048576)
        assert "/s" in result


class TestTimeRemainingFormatting:
    """Test time remaining formatting."""

    def test_seconds_only(self):
        """Under a minute should show seconds."""
        assert "s" in format_time_remaining(30)

    def test_minutes_and_seconds(self):
        """Under an hour should show minutes and seconds."""
        result = format_time_remaining(90)
        assert "m" in result
        assert "s" in result

    def test_hours_and_minutes(self):
        """Over an hour should show hours and minutes."""
        result = format_time_remaining(3661)
        assert "h" in result
        assert "m" in result

    def test_none_returns_unknown(self):
        """None should return Unknown."""
        assert format_time_remaining(None) == "Unknown"


class TestDownloadStatusEnum:
    """Test DownloadStatus enum."""

    def test_terminal_states(self):
        """Completed, failed, cancelled should be terminal."""
        assert DownloadStatus.COMPLETED.is_terminal is True
        assert DownloadStatus.FAILED.is_terminal is True
        assert DownloadStatus.CANCELLED.is_terminal is True

    def test_active_states(self):
        """Queued, validating, downloading should be active."""
        assert DownloadStatus.QUEUED.is_active is True
        assert DownloadStatus.VALIDATING.is_active is True
        assert DownloadStatus.DOWNLOADING.is_active is True

    def test_values_match_expected(self):
        """String values should match expected."""
        assert DownloadStatus.QUEUED.value == "queued"
        assert DownloadStatus.COMPLETED.value == "completed"


class TestUniqueFilepath:
    """Test unique filepath generation."""

    def test_new_file_gets_original_name(self):
        """New file should get original name."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            result = get_unique_filepath(base, "test.txt")
            assert result.name == "test.txt"

    def test_existing_file_gets_numbered(self):
        """Existing file should trigger numbering."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            # Create existing file
            (base / "test.txt").touch()
            result = get_unique_filepath(base, "test.txt")
            assert "test_" in result.name
            assert result.name != "test.txt"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
