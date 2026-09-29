"""
Security utilities for SSRF protection and URL validation.

Implements comprehensive protection against Server-Side Request Forgery attacks
by validating URL schemes, resolving hostnames, and checking against blocked IP ranges.
"""

import ipaddress
import logging
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Blocked IP ranges for SSRF protection
BLOCKED_IP_RANGES: List[ipaddress._BaseNetwork] = [
    # Loopback addresses
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    # All zeros
    ipaddress.ip_network("0.0.0.0/8"),
    # RFC 1918 Private networks
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local addresses
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    # IPv6 unique local
    ipaddress.ip_network("fc00::/7"),
    # IPv6 multicast
    ipaddress.ip_network("ff00::/8"),
]

# Cloud metadata endpoints that should be blocked
BLOCKED_HOSTNAMES = {
    "metadata.google.internal",
    "metadata.amazonaws.com",
}

# Local network hostnames patterns
LOCAL_HOSTNAME_PATTERNS = {"localhost", "local", "internal", "intranet"}

# Allowed schemes
ALLOWED_SCHEMES = {"http", "https"}


def validate_url_scheme(url: str) -> Tuple[bool, str]:
    """
    Validate that the URL uses an allowed scheme.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in ALLOWED_SCHEMES:
            return False, f"URL scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are supported."
        return True, ""
    except Exception as e:
        logger.warning(f"Failed to parse URL scheme: {e}")
        return False, "Invalid URL format."


def is_ip_blocked(ip_str: str) -> bool:
    """
    Check if an IP address falls within any blocked range.

    Args:
        ip_str: String representation of an IP address

    Returns:
        True if the IP is blocked, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)

        # Check against all blocked ranges
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                logger.debug(f"IP {ip_str} is blocked by range {network}")
                return True

        return False
    except ValueError:
        logger.warning(f"Invalid IP address format: {ip_str}")
        return True  # Block unparseable IPs


def is_hostname_blocked(hostname: str) -> bool:
    """
    Check if hostname matches any blocked patterns.

    Args:
        hostname: Hostname to check

    Returns:
        True if hostname is blocked, False otherwise
    """
    hostname_lower = hostname.lower()

    # Check exact matches
    if hostname_lower in BLOCKED_HOSTNAMES:
        return True

    # Check pattern matches
    if hostname_lower in LOCAL_HOSTNAME_PATTERNS:
        return True

    # Check if it looks like a metadata endpoint
    if "metadata" in hostname_lower:
        return True

    return False


async def resolve_and_validate_host(
    hostname: str,
    client: httpx.AsyncClient,
) -> Tuple[bool, str]:
    """
    Resolve hostname and validate all resulting IP addresses.

    Args:
        hostname: Hostname to resolve
        client: HTTP client for DNS resolution

    Returns:
        Tuple of (is_safe, error_message)
    """
    # First check hostname blocklist
    if is_hostname_blocked(hostname):
        return False, f"Hostname '{hostname}' is blocked for security reasons."

    try:
        # Use DNS resolution via httpx or manual resolution
        import socket

        # Get all IP addresses for this hostname
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)

        for family, socktype, proto, canonname, sockaddr in addr_infos:
            ip_addr = sockaddr[0]

            if is_ip_blocked(ip_addr):
                logger.warning(f"Blocked IP {ip_addr} resolved from hostname {hostname}")
                return False, f"The URL resolves to a blocked IP address ({ip_addr})."

        return True, ""

    except socket.gaierror as e:
        logger.error(f"DNS resolution failed for {hostname}: {e}")
        return False, f"Could not resolve hostname '{hostname}'. Please check the URL."
    except Exception as e:
        logger.error(f"Unexpected error resolving {hostname}: {e}")
        return False, f"Error validating hostname: {str(e)}"


async def validate_url_for_ssrf(
    url: str,
    client: httpx.AsyncClient,
    check_redirects: bool = True,
) -> Tuple[bool, str]:
    """
    Perform complete SSRF validation on a URL.

    This includes:
    - Scheme validation
    - Hostname blocklist check
    - DNS resolution and IP validation
    - Optional redirect chain validation

    Args:
        url: URL to validate
        client: HTTP client for making requests
        check_redirects: Whether to follow redirects and validate final destination

    Returns:
        Tuple of (is_safe, error_message)
    """
    # Step 1: Validate URL scheme
    is_valid, error_msg = validate_url_scheme(url)
    if not is_valid:
        return False, error_msg

    # Step 2: Parse and extract hostname
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False, "URL does not contain a valid hostname."

        # Step 3: Check hostname blocklist
        if is_hostname_blocked(hostname):
            return False, f"Hostname '{hostname}' is not allowed."

        # Step 4: Resolve and validate IP addresses
        is_safe, error_msg = await resolve_and_validate_host(hostname, client)
        if not is_safe:
            return False, error_msg

        # Step 5: Optionally check redirects
        if check_redirects:
            try:
                # Use HEAD request to check redirects without downloading
                response = await client.head(url, follow_redirects=True)
                final_url = str(response.url)

                # If redirected, validate final URL too
                if final_url != url:
                    final_parsed = urlparse(final_url)
                    final_hostname = final_parsed.hostname

                    if final_hostname and final_hostname != hostname:
                        if is_hostname_blocked(final_hostname):
                            return False, f"Redirect target '{final_hostname}' is not allowed."

                        is_safe, error_msg = await resolve_and_validate_host(final_hostname, client)
                        if not is_safe:
                            return False, f"Redirect target is not safe: {error_msg}"

            except httpx.TooManyRedirects:
                return False, "The URL has too many redirects or a redirect loop."
            except httpx.HTTPStatusError as e:
                # Non-2xx response is okay for validation; we just wanted to check redirects
                pass
            except Exception as e:
                # Log but don't fail validation on redirect check errors
                logger.debug(f"Redirect check warning for {url}: {e}")

        return True, ""

    except Exception as e:
        logger.error(f"Error during SSRF validation: {e}")
        return False, f"URL validation failed: {str(e)}"
