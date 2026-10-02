"""Fetch a remote file by URL, safely enough to block the common SSRF
targets: Oracle Cloud's own instance metadata service, loopback, and
other internal-only addresses this same host can reach. This does not
fully close a sophisticated DNS-rebinding race between resolution and
connection; a hardened production deployment should also set
TENANT_FETCH_ALLOWED_HOSTS to a real allowlist of trusted storage
providers (S3, OCI Object Storage) rather than relying on IP checks
alone against a fully open set of hosts.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse
import urllib.request

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_REDIRECTS_ALLOWED = 0


class UnsafeURLError(ValueError):
    pass


def _allowed_hosts() -> frozenset[str]:
    raw = os.getenv("TENANT_FETCH_ALLOWED_HOSTS", "").strip()
    if not raw:
        return frozenset()
    return frozenset(host.strip().lower() for host in raw.split(",") if host.strip())


def _is_public_ip(ip_text: str) -> bool:
    address = ipaddress.ip_address(ip_text)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def validate_remote_url(url: str) -> str:
    """Raise UnsafeURLError unless the URL's scheme, host, and every
    resolved address pass. Returns the hostname on success.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"scheme must be http or https, got {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL must include a hostname")
    allowed = _allowed_hosts()
    if allowed and hostname.lower() not in allowed:
        raise UnsafeURLError(f"host {hostname!r} is not on the configured allowlist")
    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as error:
        raise UnsafeURLError(f"could not resolve host {hostname!r}") from error
    if not resolved:
        raise UnsafeURLError(f"host {hostname!r} resolved to no addresses")
    for family, _, _, _, sockaddr in resolved:
        ip_text = sockaddr[0]
        if not _is_public_ip(ip_text):
            raise UnsafeURLError(f"host {hostname!r} resolves to a non-public address: {ip_text}")
    return hostname


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UnsafeURLError(f"refusing to follow redirect to {newurl!r}")


def fetch_remote_file(url: str, max_bytes: int, timeout_seconds: float = 15.0) -> bytes:
    """Validate, then fetch, enforcing a hard size cap during the read
    rather than after it, and refusing any redirect rather than following
    it, since a redirect target is not re-validated by this function.
    """
    validate_remote_url(url)
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(url, method="GET")
    with opener.open(request, timeout=timeout_seconds) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise UnsafeURLError(f"remote file exceeds {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
