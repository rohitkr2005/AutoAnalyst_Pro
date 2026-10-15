"""
AutoAnalyst Pro - Security Engineering & Threat Protection Utilities
Provides defensive hardening across critical OWASP Top 10 attack surfaces:
1. SSRF Guard: Validates destination IPs and schemes, blocks private/cloud-metadata ranges, and checks redirects.
2. Database URL SSRF Validator: Restricts user-supplied connection strings to public external hosts.
3. Safe HTTP Dispatcher: Custom urllib opener preventing redirect-based SSRF and protocol smuggling.
4. Path & Filename Sanitizer: Strips directory traversal sequences, null bytes, and script characters.
5. JSON Script Injection Shield: Neutralizes </script> breakouts in inline templates.
"""

import os
import re
import socket
import ipaddress
import urllib.parse
import urllib.request
from typing import Tuple, Optional, Dict, Any


# Prohibited Hostnames & IP strings
PROHIBITED_HOSTNAMES = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata.internal",
    "169.254.169.254",
    "instance-data",
}


def is_prohibited_ip(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Checks whether an IP address belongs to private, loopback, link-local, multicast, or reserved ranges."""
    return (
        ip_obj.is_loopback or
        ip_obj.is_private or
        ip_obj.is_link_local or
        ip_obj.is_multicast or
        ip_obj.is_reserved or
        ip_obj.is_unspecified
    )


def validate_safe_external_url(url: str, allow_private: bool = False) -> Tuple[bool, str]:
    """
    Validates that a URL is safe for server-side outbound HTTP requests.
    Prevents Server-Side Request Forgery (SSRF) against internal services and cloud metadata APIs.
    """
    if not url or not isinstance(url, str):
        return False, "URL cannot be empty."

    url = url.strip()
    if len(url) > 2048:
        return False, "URL exceeds maximum permitted length (2,048 characters)."

    try:
        parsed = urllib.parse.urlsplit(url)
    except Exception as e:
        return False, f"Malformed URL syntax: {str(e)}"

    # 1. Enforce strictly HTTP or HTTPS
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Prohibited URL scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    # 2. Extract and validate hostname
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "URL does not specify a valid hostname."

    # 3. Check against known prohibited names
    if hostname in PROHIBITED_HOSTNAMES:
        return False, f"Requests to '{hostname}' are blocked for security reasons."

    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return False, f"Internal domain '{hostname}' is not accessible."

    # 4. If private requests are explicitly allowed (e.g. dev mode), bypass DNS IP checks
    if allow_private:
        return True, ""

    # 5. Resolve DNS and inspect all IP addresses (handles both IPv4 and IPv6)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        return False, f"DNS resolution failed for hostname '{hostname}': {str(e)}"
    except Exception as e:
        return False, f"Network resolution error for '{hostname}': {str(e)}"

    if not addr_info:
        return False, f"Could not resolve an IP address for hostname '{hostname}'."

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if is_prohibited_ip(ip_obj):
                return False, f"Destination resolved to prohibited internal/private address: {ip_str}."
        except ValueError:
            return False, f"Invalid resolved IP format: {ip_str}."

    return True, ""


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom redirect handler that validates target redirect URLs against SSRF before following."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Validate target of the 301/302 redirect
        is_safe, err = validate_safe_external_url(newurl)
        if not is_safe:
            raise urllib.error.HTTPError(
                newurl, 403, f"SSRF Guard: Redirect target rejected ({err})", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def safe_post_webhook(url: str, payload_bytes: bytes, timeout: int = 5, user_agent: str = "AutoAnalystPro-Alerts/1.0") -> Tuple[bool, int, str]:
    """
    Dispatches a webhook POST request through SSRF-validated opener with redirect protection.
    Returns (success: bool, status_code: int, message: str).
    """
    is_safe, err = validate_safe_external_url(url)
    if not is_safe:
        return False, 400, f"SSRF Protection: {err}"

    opener = urllib.request.build_opener(SafeRedirectHandler())
    req = urllib.request.Request(
        url,
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, */*"
        },
        method="POST"
    )

    try:
        with opener.open(req, timeout=timeout) as resp:
            code = resp.getcode()
            return True, code, f"Webhook delivered successfully (HTTP {code})."
    except urllib.error.HTTPError as he:
        return False, he.code, f"HTTP error {he.code}: {he.reason}"
    except urllib.error.URLError as ue:
        return False, 502, f"Network error: {str(ue.reason)}"
    except Exception as e:
        return False, 500, f"Delivery exception: {str(e)}"


def validate_safe_db_url(db_url: str) -> Tuple[bool, str]:
    """
    Validates user-supplied database connection strings to prevent SSRF and internal port scanning.
    Checks PostgreSQL URLs for safe remote hostnames.
    """
    if not db_url or not isinstance(db_url, str):
        return False, "Database connection URL cannot be empty."

    db_url = db_url.strip()
    try:
        parsed = urllib.parse.urlsplit(db_url)
    except Exception as e:
        return False, f"Invalid database URL format: {str(e)}"

    if parsed.scheme.lower() not in ("postgresql", "postgres"):
        return False, f"Unsupported database scheme '{parsed.scheme}'. Only postgresql:// or postgres:// connections are allowed."

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        return False, "Database connection URL missing host."

    if hostname in PROHIBITED_HOSTNAMES:
        return False, f"Connecting to '{hostname}' is not permitted for security reasons."

    if hostname.endswith(".local") or hostname.endswith(".internal"):
        return False, f"Internal domain '{hostname}' is not accessible."

    # If ALLOW_LOCAL_DB is explicitly set (e.g. local dev testing), allow loopback
    if os.environ.get("ALLOW_LOCAL_DB", "").lower() in ("1", "true"):
        return True, ""

    # Resolve and verify IP address
    port = parsed.port or 5432
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        for item in addr_info:
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if is_prohibited_ip(ip_obj):
                return False, f"Database host resolves to prohibited private or loopback address ({ip_str})."
    except Exception as e:
        return False, f"Could not resolve database host '{hostname}': {str(e)}"

    return True, ""


def sanitize_filename(filename: str, fallback: str = "uploaded_dataset.csv") -> str:
    """
    Sanitizes uploaded file names to prevent path traversal (../), control characters, and injection attacks.
    """
    if not filename or not isinstance(filename, str):
        return fallback

    # Strip directory components (handle both UNIX and Windows separators)
    name = os.path.basename(filename.replace("\\", "/"))

    # Remove null bytes and non-printable characters
    name = re.sub(r'[\x00-\x1f\x7f]', '', name)

    # Remove dangerous characters like quotes, angle brackets, backticks
    name = re.sub(r'[<>\":/\\|?*`]', '_', name)

    # Normalize multiple dots or leading dots (prevent hidden files and traversal)
    name = re.sub(r'^\.+', '', name)
    name = re.sub(r'\.{2,}', '.', name)

    name = name.strip()
    if not name or name == ".":
        return fallback

    # Enforce safe length limit (max 120 chars)
    if len(name) > 120:
        base, ext = os.path.splitext(name)
        ext = ext[:10]
        base = base[:110 - len(ext)]
        name = f"{base}{ext}"

    return name


def escape_json_for_script(json_str: str) -> str:
    """
    Safely escapes a JSON string for inclusion in HTML <script> tags.
    Prevents XSS breakouts like </script><script>alert(1)</script>.
    """
    if not json_str:
        return "{}"
    return json_str.replace("</", "<\\/").replace("<!--", "<\\!--")
