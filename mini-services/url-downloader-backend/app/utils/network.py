"""
Network utility functions.
"""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def extract_hostname(url: str) -> str:
    """
    Extract hostname from URL safely.

    Args:
        url: Full URL

    Returns:
        Hostname string or empty string on failure
    """
    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        logger.warning(f"Failed to extract hostname from URL")
        return ""


def redact_sensitive_params(url: str) -> str:
    """
    Redact sensitive query parameters from URL for logging.

    Removes tokens, keys, passwords, etc. while preserving
    non-sensitive parameters.

    Args:
        url: URL with potential sensitive parameters

    Returns:
        URL with sensitive values replaced by [REDACTED]
    """
    try:
        parsed = urlparse(url)

        if not parsed.query:
            return url

        # Parameters to redact
        sensitive_params = {
            "token", "key", "api_key", "apikey", "signature",
            "auth", "password", "pass", "access_token", "refresh_token",
            "secret", "credential", "session", "ticket",
        }

        query_parts = []
        for param in parsed.query.split("&"):
            if "=" in param:
                key, _ = param.split("=", 1)
                if key.lower() in sensitive_params:
                    query_parts.append(f"{key}=[REDACTED]")
                else:
                    query_parts.append(param)
            else:
                query_parts.append(param)

        redacted_query = "&".join(query_parts)

        # Reconstruct URL
        scheme = f"{parsed.scheme}://"
        netloc = parsed.netloc
        path = parsed.path or "/"
        query = f"?{redacted_query}" if redacted_query else ""
        fragment = f"#{parsed.fragment}" if parsed.fragment else ""

        return f"{scheme}{netloc}{path}{query}{fragment}"

    except Exception:
        logger.debug("Failed to redact URL parameters")
        # Return just scheme://hostname if parsing fails
        try:
            parsed = urlparse(url)
            return f"{parsed.scheme}://{parsed.hostname}"
        except Exception:
            return "[URL PARSE ERROR]"
