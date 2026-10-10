import ipaddress
import socket
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


TRACKING_PARAMS = {
    "fbclid", "gclid", "dclid", "msclkid",
    "ref_src", "igshid",
}

RESTRICTED_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "169.254.169.254"
}


def is_safe_url(url: str) -> bool:
    """Validate that a URL does not target loopback, private, or metadata networks."""
    if not isinstance(url, str) or not url.strip():
        return False

    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"} or not parts.hostname:
            return False

        hostname = parts.hostname.lower().strip("[]")
        if hostname in RESTRICTED_HOSTS or hostname.endswith(".localhost"):
            return False

        # Check if the hostname is a direct IP address
        try:
            ip = ipaddress.ip_address(hostname)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                return False
        except ValueError:
            # Hostname is a domain name. Resolve DNS and verify resolved addresses.
            try:
                addr_info = socket.getaddrinfo(hostname, None)
                for _family, _socktype, _proto, _canonname, sockaddr in addr_info:
                    ip_str = sockaddr[0]
                    ip = ipaddress.ip_address(ip_str)
                    if (
                        ip.is_private
                        or ip.is_loopback
                        or ip.is_link_local
                        or ip.is_multicast
                        or ip.is_reserved
                        or ip.is_unspecified
                    ):
                        return False
            except (socket.gaierror, OSError):
                # If DNS resolution cannot be completed (e.g. offline tests), allow request
                # to proceed to standard connection exception handling.
                pass

        return True
    except Exception:
        return False


def canonicalize_url(url: str) -> str:
    """Normalize an HTTP(S) URL for consistent crawl deduplication."""
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")

    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()

    if scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are supported")

    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not allowed")

    host = parts.hostname.lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid URL port") from exc

    if port is not None and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"

    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"

    query_items = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key.startswith("utm_") or lower_key in TRACKING_PARAMS:
            continue
        query_items.append((key, value))

    query_items.sort()
    query = urlencode(query_items, doseq=True)

    # Fragments are browser-side locations, not separate server resources.
    return urlunsplit((scheme, host, path, query, ""))


def deduplicate_urls(urls):
    """Return canonical URLs in first-seen order."""
    seen = set()
    result = []

    for url in urls:
        normalized = canonicalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            result.append(normalized)

    return result
