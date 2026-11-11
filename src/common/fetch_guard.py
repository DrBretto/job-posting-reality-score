"""Safety guard for fetching URLs that no operator vetted.

Monitoring only ever touched four hardcoded ATS hosts, so a static `HOST_ALLOWLIST` was a complete
defense. Discovery breaks that assumption: an unsupported careers page is, by definition, a URL the
system learned at runtime from an untrusted feed. This module is the replacement boundary.

What it refuses, and why each one matters:

  - non-HTTP(S) schemes                  `file://`, `gopher://`, `data:` are not web fetches
  - credentials embedded in the URL      `https://user:pass@host` leaks secrets into logs/receipts
  - non-standard ports                   port sweeping via a job link
  - unresolvable hosts                   fail closed, never "try it and see"
  - private / loopback / link-local /    SSRF. Checked on the RESOLVED addresses, because
    CGNAT / multicast / reserved space   `intranet.example.com` can legitimately resolve to
                                         10.x — parsing the string is not enough
  - cross-host or scheme-downgrading     an allowed page must not bounce us somewhere else
    redirects, or too many hops
  - oversized responses                  streamed with a hard ceiling, so the limit actually binds
                                         instead of being checked after the bytes are already in
  - unexpected content types             a careers page is HTML or JSON

Non-negotiable: fetched job text is DATA. It is stored, hashed and scored as text. It is never
executed, never interpreted as an instruction, and text inside a job description that looks like a
directive to this system carries exactly the authority of any other posting prose: none.
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlsplit

USER_AGENT = "jprs-job-radar/1.1 (+https://github.com/jprs; personal job-posting radar)"

ALLOWED_SCHEMES = frozenset({"http", "https"})
ALLOWED_PORTS = frozenset({80, 443})
MAX_RESPONSE_BYTES = 2_000_000       # a careers page that needs >2MB is not a careers page
MAX_REDIRECTS = 3
ALLOWED_CONTENT_PREFIXES = (
    "text/html", "application/xhtml", "application/json", "application/ld+json", "text/plain",
)


class FetchRefused(Exception):
    """A fetch was refused by policy. The reason is operator-readable and gets recorded."""

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


@dataclass
class GuardedResponse:
    url: str
    final_url: str
    http_status: int
    content_type: str
    body: bytes
    truncated: bool = False
    redirects: list[str] = field(default_factory=list)


def _resolve(host: str, resolver=None) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve a host to every address it answers with.

    `resolver` is injectable so the address-range policy is unit-testable without live DNS (and so
    a sandboxed environment that blocks getaddrinfo can still exercise the rules).
    """
    if resolver is not None:
        addrs = [ipaddress.ip_address(a) for a in resolver(host)]
        if not addrs:
            raise FetchRefused("host_unresolvable", host)
        return addrs
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchRefused("host_unresolvable", f"{host} ({exc.strerror or exc})") from exc
    addrs = []
    for info in infos:
        try:
            addrs.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addrs:
        raise FetchRefused("host_unresolvable", host)
    return addrs


def _assert_public(addr) -> None:
    """Fail closed on every non-public range, named individually so the refusal is diagnosable."""
    checks = (
        (addr.is_loopback, "loopback"),
        (addr.is_link_local, "link_local"),
        (addr.is_multicast, "multicast"),
        (addr.is_reserved, "reserved"),
        (addr.is_unspecified, "unspecified"),
        (addr.is_private, "private"),
    )
    for failed, label in checks:
        if failed:
            raise FetchRefused("non_public_address", f"{addr} is {label}")
    # 100.64.0.0/10 (CGNAT) is not flagged private by ipaddress but is not public either.
    if addr.version == 4 and addr in ipaddress.ip_network("100.64.0.0/10"):
        raise FetchRefused("non_public_address", f"{addr} is cgnat")


def assert_url_allowed(url: str, *, resolver=None) -> tuple[str, str]:
    """Validate a URL before any socket is opened. Returns (scheme, host) or raises FetchRefused."""
    if not url or not str(url).strip():
        raise FetchRefused("empty_url")
    try:
        parts = urlsplit(str(url).strip())
    except ValueError as exc:
        raise FetchRefused("unparseable_url", str(exc)) from exc

    scheme = (parts.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise FetchRefused("scheme_not_allowed", scheme or "<none>")
    if parts.username or parts.password:
        raise FetchRefused("credentials_in_url", "userinfo present")
    host = (parts.hostname or "").lower()
    if not host:
        raise FetchRefused("no_host")
    try:
        port = parts.port
    except ValueError as exc:
        raise FetchRefused("invalid_port", str(exc)) from exc
    if port is not None and port not in ALLOWED_PORTS:
        raise FetchRefused("port_not_allowed", str(port))

    # A literal IP is checked directly; a name is checked on every address it resolves to, so one
    # inward-pointing record in a round-robin cannot slip through.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        for addr in _resolve(host, resolver):
            _assert_public(addr)
    else:
        _assert_public(literal)
    return scheme, host


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface redirects to the caller instead of following them blindly."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def guarded_fetch(
    url: str,
    *,
    timeout: int = 20,
    max_bytes: int = MAX_RESPONSE_BYTES,
    max_redirects: int = MAX_REDIRECTS,
    allow_content_prefixes: tuple[str, ...] = ALLOWED_CONTENT_PREFIXES,
    opener_factory=None,
    resolver=None,
) -> GuardedResponse:
    """Fetch a runtime-learned URL under every guard above.

    Redirects are walked one hop at a time and each target is re-validated from scratch, so an
    allowed page cannot redirect into private space or downgrade https to http.
    """
    scheme, host = assert_url_allowed(url, resolver=resolver)
    build = opener_factory or (lambda: urllib.request.build_opener(_NoRedirect))
    opener = build()

    current = str(url).strip()
    current_scheme, current_host = scheme, host
    redirects: list[str] = []

    for _hop in range(max_redirects + 1):
        req = urllib.request.Request(
            current, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"}
        )
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location:
                    raise FetchRefused("redirect_without_location", str(exc.code)) from exc
                nxt = urllib.parse.urljoin(current, location)
                next_scheme, next_host = assert_url_allowed(nxt, resolver=resolver)
                if next_host != current_host:
                    raise FetchRefused("cross_host_redirect", f"{current_host} -> {next_host}")
                if current_scheme == "https" and next_scheme != "https":
                    raise FetchRefused("scheme_downgrade_redirect", f"https -> {next_scheme}")
                redirects.append(nxt)
                current, current_scheme, current_host = nxt, next_scheme, next_host
                continue
            raise FetchRefused("http_error", f"{exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchRefused("transport_error", str(exc)[:120]) from exc

        with resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith(allow_content_prefixes):
                raise FetchRefused("content_type_not_allowed", content_type)
            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > max_bytes:
                raise FetchRefused("response_too_large", f"declared {declared} > {max_bytes}")
            # Read one byte past the ceiling so an undeclared oversize body is detectable, and stop
            # there — the cap binds on bytes actually transferred, not on a header we trusted.
            body = resp.read(max_bytes + 1)
            truncated = len(body) > max_bytes
            if truncated:
                body = body[:max_bytes]
            return GuardedResponse(
                url=str(url), final_url=current, http_status=resp.status,
                content_type=content_type, body=body, truncated=truncated, redirects=redirects,
            )

    raise FetchRefused("too_many_redirects", f">{max_redirects}")
