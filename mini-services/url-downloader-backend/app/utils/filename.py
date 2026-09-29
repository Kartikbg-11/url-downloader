"""
Filename sanitization and handling utilities.

Provides safe filename extraction and sanitization to prevent
path traversal attacks and ensure cross-platform compatibility.
"""

import re
import unicodedata
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse

# Windows reserved names (case-insensitive)
WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}

# Characters invalid in filenames on various OS
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Maximum filename length
MAX_FILENAME_LENGTH = 255


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename for safe filesystem use.

    - Removes null bytes and control characters
    - Removes path separators
    - Handles Unicode normalization
    - Limits length
    - Avoids Windows reserved names
    - Prevents path traversal sequences
    """
    if not filename:
        return "download"

    # Decode URL-encoded characters
    try:
        filename = unquote(filename)
    except Exception:
        pass

    # Normalize Unicode (NFC form)
    filename = unicodedata.normalize("NFC", filename)

    # Remove null bytes and control characters
    filename = "".join(c for c in filename if ord(c) >= 32 and c != "\x00")

    # Remove path separators and other invalid characters FIRST
    # This prevents path traversal by removing / and \ before processing ..
    filename = INVALID_FILENAME_CHARS.sub("_", filename)

    # Remove path traversal sequences (..) after replacing separators
    # Replace .. with single underscore to prevent any traversal attempts
    filename = re.sub(r'\.{2,}', '_', filename)
    
    # Remove leading/trailing whitespace and dots
    filename = filename.strip(" .")

    # Replace consecutive spaces/underscores with single underscore
    filename = re.sub(r"[\s_]+", "_", filename)

    if not filename:
        return "download"

    # Check for Windows reserved names (with or without extension)
    name_part = Path(filename).stem.lower()
    if name_part in WINDOWS_RESERVED_NAMES:
        filename = f"_{filename}"

    # Truncate if too long (keep extension)
    if len(filename) > MAX_FILENAME_LENGTH:
        suffix = Path(filename).suffix
        max_name_length = MAX_FILENAME_LENGTH - len(suffix)
        filename = filename[:max_name_length] + suffix

    return filename


def extract_filename_from_content_disposition(
    header_value: Optional[str],
) -> Optional[str]:
    """
    Extract filename from Content-Disposition header.

    Supports both quoted and unquoted filenames,
    as well as UTF-8 encoded filenames (RFC 5987).
    """
    if not header_value:
        return None

    # Try RFC 5987 filename* first (UTF-8 encoded)
    match = re.search(
        r"filename\*\s*=\s*(?:UTF-8''|utf-8'')([^;\s]+)",
        header_value,
        re.IGNORECASE,
    )
    if match:
        try:
            encoded = match.group(1)
            # Decode percent-encoding
            filename = re.sub(
                r"%([0-9A-Fa-f]{2})",
                lambda m: chr(int(m.group(1), 16)),
                encoded,
            )
            return sanitize_filename(filename)
        except Exception:
            pass

    # Try regular filename (quoted)
    match = re.search(
        r'filename\s*=\s*"([^"]+)"',
        header_value,
        re.IGNORECASE,
    )
    if match:
        return sanitize_filename(match.group(1))

    # Try regular filename (unquoted)
    match = re.search(
        r"filename\s*=\s*([^;\s]+)",
        header_value,
        re.IGNORECASE,
    )
    if match:
        return sanitize_filename(match.group(1))

    return None


def extract_filename_from_url(url: str) -> str:
    """
    Extract filename from URL path.

    Returns sanitized filename or 'download' as fallback.
    """
    try:
        parsed = urlparse(url)
        path = unquote(parsed.path)

        # Get the last path component
        filename = Path(path).name

        if filename and filename != "/":
            return sanitize_filename(filename)
    except Exception:
        pass

    return "download"


def generate_fallback_filename(download_id: str, extension: Optional[str] = None) -> str:
    """Generate a safe filename using download ID."""
    base = f"download_{download_id[:8]}"
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    elif not extension:
        extension = ""
    return f"{base}{extension}"


def is_safe_path(base_dir: Path, file_path: Path) -> bool:
    """
    Verify that file_path resolves within base_dir.

    Prevents path traversal attacks.
    """
    try:
        resolved_base = base_dir.resolve()
        resolved_file = file_path.resolve()

        # Check that the file path starts with the base directory
        resolved_file.relative_to(resolved_base)
        return True
    except ValueError:
        return False


def get_unique_filepath(directory: Path, filename: str) -> Path:
    """
    Generate a unique filepath by appending counter if needed.
    """
    filepath = directory / filename

    if not filepath.exists():
        return filepath

    # Find unique name by appending counter
    stem = filepath.stem
    suffix = filepath.suffix
    counter = 1

    while True:
        new_filename = f"{stem}_{counter}{suffix}"
        new_filepath = directory / new_filename
        if not new_filepath.exists():
            return new_filepath
        counter += 1

        # Safety limit
        if counter > 1000:
            raise ValueError(f"Cannot generate unique filename for: {filename}")
