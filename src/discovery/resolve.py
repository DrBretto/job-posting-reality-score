"""Resolve an aggregator apply link to the employer's own posting page.

WHY THIS EXISTS, AND WHY IT IS BOUNDED
--------------------------------------
Source growth needs the employer's own careers URL: that is the only honest way to derive a board
token (guessing one from a company name produces confident nonsense aimed at somebody else's board).

Measured against the live payloads on 2026-09-24: all four keyless discovery feeds return apply URLs
that point at the aggregator, and a regex sweep for embedded Greenhouse/Lever/Ashby URLs across the
full raw payloads of all four feeds found **zero**. So the employer's board is simply not in the data.
It can only be obtained by following the apply link to where it actually goes.

That is an outbound request to a URL learned at runtime, so it goes through `fetch_guard` — with one
deliberate policy difference: cross-host redirects are ALLOWED here, because arriving at a different
host is the entire point of resolving an apply link. Every hop is still re-validated against the
SSRF address rules (no private/loopback/link-local/CGNAT/reserved space, no credentials in the URL,
no odd ports, no scheme downgrade), the chain is short, and the body is capped.

It is bounded and off by default:
  - disabled unless JPRS_RESOLVE_CAREERS_URLS is truthy
  - at most `max_resolutions` per run, spent on the highest-scoring employers only
  - one request per employer, never per posting
"""

from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

from src.common.fetch_guard import (
    ALLOWED_CONTENT_PREFIXES,
    FetchRefused,
    assert_url_allowed,
)
from src.discovery.admission import detect_board

ENV_FLAG = "JPRS_RESOLVE_CAREERS_URLS"
MAX_RESOLUTION_HOPS = 4
MAX_RESOLUTION_BYTES = 500_000


@dataclass
class ResolutionOutcome:
    resolved: dict[str, str] = field(default_factory=dict)      # employer_name -> careers URL
    refused: list[dict] = field(default_factory=list)
    spent: int = 0
    enabled: bool = True
    disabled_reason: str | None = None


def enabled(env=None) -> bool:
    env = env if env is not None else os.environ
    return str(env.get(ENV_FLAG, "")).strip().lower() in ("1", "true", "yes", "on")


def follow_to_employer(
    url: str,
    *,
    timeout: int = 15,
    max_hops: int = MAX_RESOLUTION_HOPS,
    opener_factory=None,
    resolver=None,
) -> str:
    """Follow redirects to the final destination, re-validating every hop. Returns the final URL.

    Unlike `guarded_fetch`, a cross-host hop is permitted — that is what resolving an apply link
    means. The address-range, scheme, port and credential rules still apply at every single hop, so
    a redirect cannot be used to reach inside the network.
    """
    from src.common.fetch_guard import _NoRedirect

    build = opener_factory or (lambda: urllib.request.build_opener(_NoRedirect))
    opener = build()
    current = str(url).strip()
    current_scheme, _host = assert_url_allowed(current, resolver=resolver)

    for _hop in range(max_hops):
        req = urllib.request.Request(
            current,
            headers={"User-Agent": "jprs-job-radar/1.1 (+https://github.com/jprs)",
                     "Accept": "text/html,application/json"},
            method="GET",
        )
        try:
            resp = opener.open(req, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (301, 302, 303, 307, 308):
                location = exc.headers.get("Location")
                if not location:
                    raise FetchRefused("redirect_without_location", str(exc.code)) from exc
                nxt = urllib.parse.urljoin(current, location)
                next_scheme, _next_host = assert_url_allowed(nxt, resolver=resolver)
                if current_scheme == "https" and next_scheme != "https":
                    raise FetchRefused("scheme_downgrade_redirect", f"https -> {next_scheme}")
                current, current_scheme = nxt, next_scheme
                continue
            raise FetchRefused("http_error", str(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise FetchRefused("transport_error", str(exc)[:120]) from exc

        with resp:
            content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith(ALLOWED_CONTENT_PREFIXES):
                raise FetchRefused("content_type_not_allowed", content_type)
            # The body is read and discarded except for its size cap: only the FINAL URL matters,
            # and a page's text is untrusted data we have no reason to keep here.
            resp.read(MAX_RESOLUTION_BYTES)
            return resp.url or current

    raise FetchRefused("too_many_redirects", f">{max_hops}")



def resolve_careers_urls(
    candidates: list[tuple[str, str]],
    *,
    now: datetime,
    max_resolutions: int = 10,
    env=None,
    follower=None,
    growth=None,
) -> ResolutionOutcome:
    """Resolve up to `max_resolutions` (employer_name, apply_url) pairs to employer careers URLs.

    `follower(url) -> final_url` is injectable so the policy is testable without network. Returns
    only resolutions whose final URL actually parses as a supported board — anything else stays an
    unsupported lead rather than becoming a guessed board token.
    """
    env = env if env is not None else os.environ
    outcome = ResolutionOutcome()
    if not enabled(env):
        outcome.enabled = False
        outcome.disabled_reason = (
            f"careers-URL resolution is off; set {ENV_FLAG}=true to enable it. While it is off, "
            "employers discovered through an aggregator stay unsupported leads because the feeds do "
            "not publish the employer's own board URL."
        )
        return outcome

    follow = follower or follow_to_employer
    for employer_name, apply_url in candidates[:max_resolutions]:
        if not apply_url:
            continue
        outcome.spent += 1
        try:
            final_url = follow(apply_url)
        except FetchRefused as refused:
            outcome.refused.append({
                "employer": employer_name, "url": apply_url,
                "reason": refused.reason, "detail": refused.detail,
            })
            continue
        except Exception as exc:  # noqa: BLE001 - one employer must not fail the pass
            outcome.refused.append({
                "employer": employer_name, "url": apply_url,
                "reason": "unexpected_error", "detail": f"{type(exc).__name__}: {exc}",
            })
            continue
        if detect_board(final_url) is None:
            outcome.refused.append({
                "employer": employer_name, "url": final_url,
                "reason": "no_supported_board_at_destination",
                "detail": "resolved successfully but the destination is not a supported public board",
            })
            continue
        outcome.resolved[employer_name] = final_url
    return outcome
