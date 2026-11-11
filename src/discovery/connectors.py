"""Employer-independent discovery connectors.

Every connector reuses the existing `Connector` contract — fetch, label the snapshot honestly, map
to `CanonicalJob`, never decide disappearance — so discovery flows through the same
raw/normalized/status/current/events tiering, the same IAM prefix split, and the same freeze
invariant as board monitoring. There is no second pipeline.

Two shapes, because the providers genuinely differ:

  BulkFeedConnector   one request returns the provider's whole current feed. Remotive, Remote OK,
                      Jobicy and Himalayas have no useful server-side text query, and Remotive's own
                      legal notice advises at most four requests per day, so one bulk pull per run
                      is both more complete and more polite than query fan-out. Matching happens
                      locally against the query plan.

  QueryFeedConnector  Adzuna is a real search API. It is queried phrase by phrase under an explicit
                      budget, which is the only source here that can ask "who in New Hampshire needs
                      an engineer for internal automation" and get an answer spanning all industries.

Attribution is not optional. Each provider's terms require a link back and a credit; the connector
records `attribution` and the report renders it. Raw provider payloads are never committed.
"""

from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from src.common.connectors import Connector, _iso
from src.common.models import (
    CanonicalJob,
    EmploymentType,
    IdKind,
    Provider,
    SalarySource,
    SalaryStruct,
    SourceKind,
    VerificationState,
)
from src.common.normalize import norm_text, url_host
from src.discovery.queries import is_obvious_non_job, match_families


def _epoch(value) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v not in (None, "")]
    text = str(value).strip()
    if text.startswith("[") and text.endswith("]"):
        # Several feeds serialize a list as its Python/JSON repr inside a string field.
        import ast

        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return [text] if text else []
        if isinstance(parsed, (list, tuple)):
            return [str(v) for v in parsed if v not in (None, "")]
    return [text] if text else []


class DiscoveryConnector(Connector):
    """Base for employer-independent sources.

    `source_kind` is DISCOVERY_FEED and the employer comes off each record, which is the whole
    mechanism by which an employer nobody named can reach the report.
    """

    source_kind = SourceKind.DISCOVERY_FEED
    attribution: str = ""
    # Provider-stated or provider-advised request ceiling per run. Respected by the budget.
    max_requests_per_run: int = 1
    # Feeds return summaries of varying completeness. A snippet is a LEAD, not a job description.
    default_verification = VerificationState.FEED_COMPLETE

    # The stable slice this feed represents. A discovery source is keyed by a QUESTION ABOUT WORK,
    # not by a board, so every page and every query slice of one provider is the same source. This
    # is the id `config/discovery_sources.yaml` declares (`DiscoverySourceEntry.source_id`) and the
    # id enumerate records in `expected_discovery_sources`, so job, config and manifest now agree.
    FEED_SLICE = "all"

    def job_source_id(self, board_token: str) -> str:
        """Jobs carry the FEED id, never the cursor or query slice they happened to arrive on.

        The cursor and the Adzuna `page|what|where` token are fetch coordinates: they rotate between
        runs while the posting behind them does not. Which query surfaced a posting is preserved on
        the job itself (`discovery_query` / `discovery_query_family`), so nothing is lost by keeping
        it out of the identity. Snapshots keep the coordinate, because two pages of one feed are two
        distinct downloads and must not overwrite each other's stored record.
        """
        return f"{self.provider.value}:{self.FEED_SLICE}"

    def employer_of(self, raw: dict) -> str:  # pragma: no cover - overridden
        raise NotImplementedError


# --------------------------------------------------------------------------------------------------
# Bulk feeds
# --------------------------------------------------------------------------------------------------
class BulkFeedConnector(DiscoveryConnector):
    """One request returns the provider's whole current feed.

    Only use this when the provider genuinely returns everything in one response. Himalayas was
    modelled this way and it was wrong: the provider caps a response at 20 jobs and paginates with a
    cursor, so one request looked like the entire feed and every job past the first page was silently
    unreachable. If a response can carry a continuation token, the source is a PaginatedFeedConnector.
    """

    def endpoint(self, board_token: str) -> str:  # board_token is the feed slice, usually "all"
        return self.feed_url

    feed_url: str = ""


class PaginatedFeedConnector(DiscoveryConnector):
    """A feed that must be walked with a cursor, one bounded page at a time.

    The contract the discovery stage relies on:
      `endpoint(cursor)` builds the URL for a page (cursor None => first page)
      `next_cursor(payload)` returns the continuation token, or None at the end of the feed
    """

    feed_url: str = ""
    page_size: int = 20
    cursor_param: str = "cursor"

    def endpoint(self, board_token: str) -> str:
        """`board_token` is the cursor, or "all"/"" for the first page."""
        cursor = None if board_token in ("", "all", None) else board_token
        params = {"limit": self.page_size}
        if cursor:
            params[self.cursor_param] = cursor
        joiner = "&" if "?" in self.feed_url else "?"
        return f"{self.feed_url}{joiner}{urlencode(params)}"

    def next_cursor(self, payload) -> str | None:  # pragma: no cover - overridden
        raise NotImplementedError


class RemotiveConnector(BulkFeedConnector):
    provider = Provider.REMOTIVE
    feed_url = "https://remotive.com/api/remote-jobs"
    # Provider's own legal notice: "you only need to GET Remotive job data ... a couple of times a
    # day (we advise max. 4 times a day)". One bulk pull per daily run sits well inside that.
    max_requests_per_run = 1
    attribution = "Jobs via Remotive (remotive.com) — linked back to the Remotive posting URL."

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise ValueError("remotive: missing 'jobs' array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise ValueError("remotive: 'jobs' is not a list")
        return jobs

    def employer_of(self, raw: dict) -> str:
        return norm_text(raw.get("company_name"))

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        native_id = str(raw.get("id") or "")
        url = raw.get("url") or ""
        native_desc = raw.get("description") or ""
        location = norm_text(raw.get("candidate_required_location")) or None
        tags = ", ".join(_as_list(raw.get("tags")))
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            employer_name=self.employer_of(raw),
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(raw.get("title")),
            department=norm_text(raw.get("category")) or None,
            industry=norm_text(raw.get("category")) or None,
            description_text=norm_text(native_desc),
            description_native=str(native_desc),
            posting_url=url,
            apply_url=url,
            apply_host=url_host(url),
            employment_type=_REMOTIVE_EMPLOYMENT.get(
                str(raw.get("job_type") or "").lower(), EmploymentType.UNSPECIFIED
            ),
            provider_published_at=_iso(raw.get("publication_date")),
            # The provider states a 24-hour delay, so "published" is theirs and "first seen" is ours.
            # An imported posting is never presented as newly posted.
            verification_state=VerificationState.FEED_COMPLETE,
            uncertainty=["provider_delay_24h", "employer_posting_not_directly_confirmed"],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, tags)
        ) or None
        stated = _salary_from_text(raw.get("salary"))
        return self._finish_job(
            job, raw_location=location, explicit_workmode="remote", stated_salary=stated, now=now
        )


_REMOTIVE_EMPLOYMENT = {
    "full_time": EmploymentType.FULL_TIME,
    "part_time": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT,
    "internship": EmploymentType.INTERN,
    "temporary": EmploymentType.TEMP,
    "freelance": EmploymentType.CONTRACT,
}


class RemoteOkConnector(BulkFeedConnector):
    provider = Provider.REMOTEOK
    feed_url = "https://remoteok.com/api"
    max_requests_per_run = 1
    attribution = "Jobs via Remote OK (remoteok.com) — linked back to the Remote OK posting URL."

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, list):
            raise ValueError("remoteok: expected a top-level list")
        # Record 0 is the provider's legal/attribution notice, not a posting. Dropping it by shape
        # (no position/company) rather than by index survives a future reordering.
        return [r for r in payload if isinstance(r, dict) and r.get("position") and r.get("company")]

    def employer_of(self, raw: dict) -> str:
        return norm_text(raw.get("company"))

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        native_id = str(raw.get("id") or raw.get("slug") or "")
        url = raw.get("url") or raw.get("apply_url") or ""
        native_desc = raw.get("description") or ""
        tags = ", ".join(_as_list(raw.get("tags")))
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            employer_name=self.employer_of(raw),
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(raw.get("position")),
            description_text=norm_text(native_desc),
            description_native=str(native_desc),
            posting_url=url,
            apply_url=raw.get("apply_url") or url,
            apply_host=url_host(raw.get("apply_url") or url),
            provider_published_at=_iso(raw.get("date")) or _epoch(raw.get("epoch")),
            verification_state=VerificationState.FEED_COMPLETE,
            uncertainty=["employer_posting_not_directly_confirmed"],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, tags)
        ) or None
        stated = _salary_from_bounds(raw.get("salary_min"), raw.get("salary_max"))
        return self._finish_job(
            job, raw_location=norm_text(raw.get("location")) or None,
            explicit_workmode="remote", stated_salary=stated, now=now,
        )


class JobicyConnector(BulkFeedConnector):
    provider = Provider.JOBICY
    feed_url = "https://jobicy.com/api/v2/remote-jobs?count=100"
    max_requests_per_run = 1
    attribution = (
        "Jobs via Jobicy (jobicy.com) — apply links point at the original Jobicy posting URL."
    )

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise ValueError("jobicy: missing 'jobs' array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise ValueError("jobicy: 'jobs' is not a list")
        return jobs

    def employer_of(self, raw: dict) -> str:
        return norm_text(raw.get("companyName"))

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        native_id = str(raw.get("id") or raw.get("jobSlug") or "")
        url = raw.get("url") or ""
        native_desc = raw.get("jobDescription") or raw.get("jobExcerpt") or ""
        industry = ", ".join(_as_list(raw.get("jobIndustry"))) or None
        levels = ", ".join(_as_list(raw.get("jobLevel"))) or None
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            employer_name=self.employer_of(raw),
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(raw.get("jobTitle")),
            industry=industry,
            job_level=levels,
            description_text=norm_text(native_desc),
            description_native=str(native_desc),
            posting_url=url,
            apply_url=url,
            apply_host=url_host(url),
            employment_type=_first_employment(_as_list(raw.get("jobType"))),
            provider_published_at=_iso(raw.get("pubDate")),
            verification_state=(
                VerificationState.FEED_COMPLETE if raw.get("jobDescription")
                else VerificationState.UNVERIFIED_LEAD
            ),
            uncertainty=(
                [] if raw.get("jobDescription")
                else ["excerpt_only_full_description_not_retrieved"]
            ) + ["employer_posting_not_directly_confirmed"],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, f"{industry or ''} {levels or ''}")
        ) or None
        return self._finish_job(
            job, raw_location=norm_text(raw.get("jobGeo")) or None,
            explicit_workmode="remote", stated_salary=None, now=now,
        )


class HimalayasConnector(PaginatedFeedConnector):
    """Cursor-paginated browse feed.

    Provider documentation, rechecked 2026-09-24 at https://himalayas.app/api :
      "limit: the number of jobs to retrieve (max 20)"
      "cursor: your position in the feed. Leave it off the first request, then pass back the
       nextCursor value from each response. This is the preferred way to paginate."
      "offset: ... Deprecated, and it will be removed in a future release. Use cursor instead."

    P01 requested `limit=100` and made exactly one request, so the provider silently returned 20 and
    the remaining feed was unreachable. `max_requests_per_run` is the page budget; whatever it does
    not reach is persisted as a cursor and resumed, not dropped.
    """

    provider = Provider.HIMALAYAS
    feed_url = "https://himalayas.app/jobs/api"
    page_size = 20             # the provider's documented maximum
    max_requests_per_run = 5   # 5 pages/run, resumable; a polite ceiling, not a coverage claim
    attribution = "Jobs via Himalayas (himalayas.app) — linked back to the Himalayas posting URL."

    def next_cursor(self, payload) -> str | None:
        if isinstance(payload, dict):
            cursor = payload.get("nextCursor")
            return str(cursor) if cursor else None
        return None

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "jobs" not in payload:
            raise ValueError("himalayas: missing 'jobs' array")
        jobs = payload["jobs"]
        if not isinstance(jobs, list):
            raise ValueError("himalayas: 'jobs' is not a list")
        return jobs

    def employer_of(self, raw: dict) -> str:
        return norm_text(raw.get("companyName"))

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        url = raw.get("applicationLink") or raw.get("guid") or ""
        native_id = str(raw.get("guid") or url)
        native_desc = raw.get("description") or raw.get("excerpt") or ""
        restrictions = _as_list(raw.get("locationRestrictions"))
        seniority = ", ".join(_as_list(raw.get("seniority"))) or None
        categories = ", ".join(_as_list(raw.get("categories")))
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{_stable_key(native_id)}",
            id_kind=IdKind.URL_SLUG,
            provider_native_id=_stable_key(native_id),
            employer_name=self.employer_of(raw),
            employer_careers_url=(
                f"https://himalayas.app/companies/{raw['companySlug']}"
                if raw.get("companySlug") else None
            ),
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(raw.get("title")),
            job_level=seniority,
            secondary_locations=restrictions[1:],
            description_text=norm_text(native_desc),
            description_native=str(native_desc),
            posting_url=url,
            apply_url=url,
            apply_host=url_host(url),
            employment_type=_first_employment([str(raw.get("employmentType") or "")]),
            provider_published_at=_epoch(raw.get("pubDate")),
            verification_state=VerificationState.FEED_COMPLETE,
            uncertainty=["employer_posting_not_directly_confirmed"],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, categories)
        ) or None
        stated = _salary_from_bounds(
            raw.get("minSalary"), raw.get("maxSalary"),
            currency=raw.get("currency"), period=raw.get("salaryPeriod"),
        )
        return self._finish_job(
            job, raw_location=(restrictions[0] if restrictions else None),
            explicit_workmode="remote", stated_salary=stated, now=now,
        )


# --------------------------------------------------------------------------------------------------
# Query feed — the breadth engine
# --------------------------------------------------------------------------------------------------
class AdzunaConnector(DiscoveryConnector):
    """Adzuna's general US job index: the one source here that spans ordinary industries.

    Credential-gated by design. `app_id` and `app_key` are obligatory per Adzuna's documentation
    (a probe without them returns 400), and this packet is not authorized to create accounts or
    spend, so the connector is implemented and fixture-tested while its LIVE path stays an
    explicitly unpassed gate. Absence of the credential blocks only this source; everything else in
    the run proceeds.
    """

    provider = Provider.ADZUNA
    attribution = "Jobs via Adzuna (adzuna.com)."
    max_requests_per_run = 20
    ENV_APP_ID = "ADZUNA_APP_ID"
    ENV_APP_KEY = "ADZUNA_APP_KEY"

    def __init__(self, *, country: str = "us", results_per_page: int = 50, env=None):
        self.country = country
        self.results_per_page = results_per_page
        # Credentials come from an INJECTED mapping, not from the process environment.
        #
        # This was the P01 runtime defect: the Lambda resolved SSM SecureStrings into a dict and
        # passed it as `env`, while this method read `os.environ`. Every request therefore went out
        # with `app_id=&app_key=` even when the credentials existed. The registry instance keeps
        # env=None (falling back to os.environ for local use) and `with_env` returns a NEW instance,
        # so a per-run credential never mutates shared state.
        self._env = env

    @property
    def env(self):
        return self._env if self._env is not None else os.environ

    def with_env(self, env) -> "AdzunaConnector":
        """Return a copy of this connector bound to `env`. Does not mutate the original."""
        return AdzunaConnector(
            country=self.country, results_per_page=self.results_per_page, env=env
        )

    @classmethod
    def credentials_present(cls, env=None) -> bool:
        env = env if env is not None else os.environ
        return bool(env.get(cls.ENV_APP_ID)) and bool(env.get(cls.ENV_APP_KEY))

    def endpoint(self, board_token: str) -> str:
        """`board_token` encodes the query slice as `page|what|where`."""
        page, _, rest = board_token.partition("|")
        what, _, where = rest.partition("|")
        env = self.env
        params = {
            "app_id": env.get(self.ENV_APP_ID, ""),
            "app_key": env.get(self.ENV_APP_KEY, ""),
            "results_per_page": self.results_per_page,
            "what": what,
            "content-type": "application/json",
            # Recency without pretending an old posting is new.
            "max_days_old": 30,
            "sort_by": "date",
        }
        if where:
            params["where"] = where
        return (
            f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/{page or 1}?"
            + urlencode(params)
        )

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "results" not in payload:
            raise ValueError("adzuna: missing 'results' array")
        results = payload["results"]
        if not isinstance(results, list):
            raise ValueError("adzuna: 'results' is not a list")
        return results

    def employer_of(self, raw: dict) -> str:
        return norm_text((raw.get("company") or {}).get("display_name"))

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        native_id = str(raw.get("id") or "")
        url = raw.get("redirect_url") or ""
        native_desc = raw.get("description") or ""
        location = (raw.get("location") or {}).get("display_name")
        category = (raw.get("category") or {}).get("label")
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            employer_name=self.employer_of(raw),
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(raw.get("title")),
            industry=norm_text(category) or None,
            description_text=norm_text(native_desc),
            description_native=str(native_desc),
            posting_url=url,
            apply_url=url,
            apply_host=url_host(url),
            employment_type=_adzuna_employment(raw),
            provider_created_at=_iso(raw.get("created")),
            # Adzuna returns a truncated description. That makes every row a LEAD: the screener must
            # not conclude "no recorded-video requirement" from text it never saw.
            verification_state=VerificationState.UNVERIFIED_LEAD,
            uncertainty=[
                "aggregator_description_truncated",
                "employer_posting_not_directly_confirmed",
            ],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, category or "")
        ) or None
        # `salary_is_predicted` means Adzuna GUESSED it. A predicted salary is not a published
        # salary and must never be rendered as one.
        predicted = str(raw.get("salary_is_predicted") or "0") in ("1", "true", "True")
        stated = None
        if not predicted:
            stated = _salary_from_bounds(raw.get("salary_min"), raw.get("salary_max"))
        elif raw.get("salary_min") or raw.get("salary_max"):
            job.uncertainty.append("salary_predicted_by_aggregator_not_published")
        return self._finish_job(
            job, raw_location=norm_text(location) or None, explicit_workmode=None,
            stated_salary=stated, now=now,
        )


# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------
# Founder / direct-employer route: Hacker News "Who is hiring?"
# --------------------------------------------------------------------------------------------------
_HN_LINK_RE = re.compile(r"""<a\s[^>]*href=["']([^"']+)["']""", re.I)
_HN_TAG_RE = re.compile(r"<[^>]+>")
_HN_ROLE_RE = re.compile(
    r"\b(engineer|engineering|developer|architect|cto|swe|sre|devops|programmer|scientist|"
    r"founding|hacker|tech lead|technical lead|full[- ]?stack|back[- ]?end|front[- ]?end|"
    r"platform|infrastructure|ml|ai|data|analyst|operations|roles?|positions?|hiring)\b",
    re.I,
)
_HN_LOCATION_RE = re.compile(
    r"\b(remote|onsite|on-site|hybrid|in[- ]office|anywhere|usa?|united states|"
    r"[A-Z][a-z]+,\s*[A-Z]{2}\b|new york|nyc|san francisco|sf|bay area|boston|seattle|austin|"
    r"london|berlin|toronto|chicago|denver|los angeles|la)\b",
    re.I,
)
_HN_EMPLOYMENT_RE = re.compile(
    r"\b(full[- ]?time|part[- ]?time|contract(?:or)?|freelance|intern(?:ship)?)\b", re.I)
_HN_MONEY_RE = re.compile(r"[$€£]\s?\d")


class HackerNewsHiringConnector(BulkFeedConnector):
    """Founder- and employer-written openings from the monthly HN "Who is hiring?" thread.

    Why this source: every top-level comment is written by someone at the hiring company — often the
    founder or CTO — and states the work, stage, pay and location in their own words. It reaches small
    funded companies whose careers page is a single static page with no supported ATS (BuildQ's is
    `buildq.ai/careers/...`, and the application is an email), which no board monitor can see.

    Access: the public HN Search API (hn.algolia.com), keyless and read-only. Two requests per run:
    one to find the current thread (`resolve_board_token`), one for the whole comment tree.
    """

    provider = Provider.HN_HIRING
    max_requests_per_run = 2
    attribution = (
        "Posts via Hacker News \"Who is hiring?\" (news.ycombinator.com) — each row links to the "
        "poster's own comment."
    )
    SEARCH_URL = (
        "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&hitsPerPage=6"
    )
    ITEM_URL = "https://hn.algolia.com/api/v1/items/{story_id}"

    def resolve_board_token(self, fetch) -> str:
        """The id of the newest "Who is hiring?" story. `fetch(url) -> FetchResult`."""
        fr = fetch(self.SEARCH_URL)
        if not fr.raw_bytes:
            raise ValueError(f"hn_hiring: thread search failed ({fr.error_class})")
        payload = json.loads(fr.raw_bytes.decode("utf-8"))
        for hit in payload.get("hits", []):
            if "who is hiring" in str(hit.get("title", "")).lower():
                return str(hit["objectID"])
        raise ValueError("hn_hiring: no 'Who is hiring?' story in the search results")

    def fetch_raw(self, board_token: str, **kwargs):
        """Retry a body that arrives cut short without any transport error.

        Measured 2026-11-11: the ~400 KB thread tree came back truncated (valid HTTP 200, no
        IncompleteRead, unparseable JSON) on 2 of 4 consecutive fetches. A parse check is the only
        signal, so up to three fetches are made; the last body is returned either way and the
        snapshot's own parse labels it PARTIAL if it is still short.
        """
        result = None
        for _ in range(3):
            result = super().fetch_raw(board_token, **kwargs)
            if not result.raw_bytes:
                return result
            try:
                json.loads(result.raw_bytes.decode("utf-8"))
                return result
            except ValueError:
                continue
        return result

    def endpoint(self, board_token: str) -> str:
        if not board_token or board_token == "all" or not board_token.isdigit():
            raise ValueError("hn_hiring needs a resolved story id")
        return self.ITEM_URL.format(story_id=board_token)

    def parse_jobs(self, payload) -> list[dict]:
        if not isinstance(payload, dict) or "children" not in payload:
            raise ValueError("hn_hiring: missing 'children' in the story tree")
        posts = []
        for child in payload.get("children") or []:
            text = child.get("text") or ""
            if not text or child.get("type") != "comment" or not child.get("author"):
                continue  # deleted / dead
            header = _hn_header(text)
            if "|" not in header:
                continue  # not in the thread's "Company | Role | Location" convention
            posts.append(dict(child, _story_id=payload.get("id"),
                              _story_title=payload.get("title")))
        return posts

    def employer_of(self, raw: dict) -> str:
        parts = [p.strip() for p in _hn_header(raw.get("text") or "").split("|")]
        name = re.sub(r"\s*\(.*?\)\s*$", "", parts[0]) if parts else ""
        name = re.sub(r"^https?://", "", name).strip(" -–:")
        return norm_text(name)[:120]

    def map_job(
        self, source_id: str, raw: dict, *, now: datetime, employer_name: str | None = None
    ) -> CanonicalJob:
        native_id = str(raw.get("id"))
        text = raw.get("text") or ""
        header = _hn_header(text)
        parts = [p.strip() for p in header.split("|") if p.strip()]
        rest = parts[1:]
        roles = [p for p in rest if _HN_ROLE_RE.search(p) and not _HN_MONEY_RE.search(p)
                 and not _HN_LOCATION_RE.fullmatch(p) and not re.match(r"^(?:https?://|www\.)", p)]
        locations = [p for p in rest if _HN_LOCATION_RE.search(p) and p not in roles]
        employment = next((p for p in rest if _HN_EMPLOYMENT_RE.search(p)), "")
        money = next((p for p in rest if _HN_MONEY_RE.search(p)), "")
        links = [html.unescape(link) for link in _HN_LINK_RE.findall(text)]
        body = norm_text(html.unescape(_HN_TAG_RE.sub(" ", text.replace("<p>", "\n"))))
        post_url = f"https://news.ycombinator.com/item?id={native_id}"
        apply = links[0] if links else post_url
        job = CanonicalJob(
            source_id=source_id,
            job_id=f"{source_id}#{native_id}",
            id_kind=IdKind.NATIVE_ID,
            provider_native_id=native_id,
            employer_name=self.employer_of(raw),
            employer_careers_url=links[0] if links else None,
            source_kind=SourceKind.DISCOVERY_FEED,
            title=norm_text(roles[0] if roles else next(
                (p for p in rest if not (_HN_LOCATION_RE.search(p) or _HN_MONEY_RE.search(p)
                                         or _HN_EMPLOYMENT_RE.search(p)
                                         or re.match(r"^(?:https?://|www\.)", p))),
                "Opening described in the post"))[:200],
            description_text=body,
            description_native=text,
            posting_url=post_url,
            apply_url=apply,
            apply_host=url_host(apply),
            employment_type=_first_employment([employment]) if employment else
            EmploymentType.UNSPECIFIED,
            provider_published_at=_iso(raw.get("created_at")),
            # The poster is the employer, so the text is first-hand; what is NOT established is that
            # the opening is still open on any later day, or that a role list names one requisition.
            verification_state=VerificationState.FEED_COMPLETE,
            uncertainty=[
                "employer_written_post_not_an_ats_requisition",
                f"hn_thread:{raw.get('_story_title') or raw.get('_story_id')}",
            ],
        )
        job.discovery_query_family = ",".join(
            match_families(job.title, job.description_text, header)
        ) or None
        # The poster's header is the authoritative work mode; prose further down ("we work remotely
        # with clients") must not turn "San Francisco (Onsite)" into a remote role.
        loc_text = " ".join(locations).lower()
        # A remote option anywhere in the header ("REMOTE (US) or ONSITE in Reno") is a remote option.
        workmode = (
            "remote" if "remote" in loc_text
            else "hybrid" if "hybrid" in loc_text
            else "onsite" if re.search(r"onsite|on-site|in[- ]office", loc_text)
            else None
        )
        return self._finish_job(
            job, raw_location=", ".join(locations)[:200] or None,
            explicit_workmode=workmode,
            stated_salary=_salary_from_text(money) if money else None,
            now=now,
        )


def _hn_header(text: str) -> str:
    """The first line of a post, where the thread convention puts `Company | Role | Location | ...`."""
    first = re.split(r"<p>|\n", text, maxsplit=1)[0]
    return norm_text(html.unescape(_HN_TAG_RE.sub("", first)))


def _stable_key(value: str) -> str:
    import hashlib

    tail = value.rstrip("/").rsplit("/", 1)[-1]
    if tail and len(tail) <= 80:
        return tail
    return hashlib.sha256(value.encode()).hexdigest()[:24]


def _salary_from_text(value) -> SalaryStruct | None:
    from src.common.normalize import parse_salary

    if not value:
        return None
    parsed = parse_salary(str(value), None)
    if parsed is None:
        return None
    parsed.source = SalarySource.STATED
    return parsed


def _salary_from_bounds(lo, hi, *, currency: str | None = None, period: str | None = None):
    def num(v):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if f > 0 else None

    low, high = num(lo), num(hi)
    if low is None and high is None:
        return None
    return SalaryStruct(
        min=low, max=high, currency=(currency or "USD"),
        period=(period or "year"), source=SalarySource.STATED,
    )


_EMPLOYMENT_WORDS = (
    ("full", EmploymentType.FULL_TIME),
    ("part", EmploymentType.PART_TIME),
    ("contract", EmploymentType.CONTRACT),
    ("freelance", EmploymentType.CONTRACT),
    ("intern", EmploymentType.INTERN),
    ("temporary", EmploymentType.TEMP),
)


def _first_employment(values: list[str]) -> EmploymentType:
    joined = " ".join(values).lower()
    for word, kind in _EMPLOYMENT_WORDS:
        if word in joined:
            return kind
    return EmploymentType.UNSPECIFIED


def _adzuna_employment(raw: dict) -> EmploymentType:
    time_ = str(raw.get("contract_time") or "").lower()
    type_ = str(raw.get("contract_type") or "").lower()
    if "part" in time_:
        return EmploymentType.PART_TIME
    if "contract" in type_:
        return EmploymentType.CONTRACT
    if "full" in time_ or "permanent" in type_:
        return EmploymentType.FULL_TIME
    return EmploymentType.UNSPECIFIED


_DISCOVERY_REGISTRY: dict[str, DiscoveryConnector] = {
    Provider.REMOTIVE.value: RemotiveConnector(),
    Provider.REMOTEOK.value: RemoteOkConnector(),
    Provider.JOBICY.value: JobicyConnector(),
    Provider.HIMALAYAS.value: HimalayasConnector(),
    Provider.ADZUNA.value: AdzunaConnector(),
    Provider.HN_HIRING.value: HackerNewsHiringConnector(),
}


def get_discovery_connector(provider: str) -> DiscoveryConnector:
    if provider not in _DISCOVERY_REGISTRY:
        raise ValueError(f"unknown discovery provider: {provider!r}")
    return _DISCOVERY_REGISTRY[provider]


def discovery_providers() -> list[str]:
    return sorted(_DISCOVERY_REGISTRY)


def keyless_discovery_providers() -> list[str]:
    """Providers that work with zero credentials — the path that is deployable today."""
    return sorted(
        p for p, c in _DISCOVERY_REGISTRY.items() if not isinstance(c, AdzunaConnector)
    )


def is_obvious_non_job_record(job: CanonicalJob) -> str | None:
    return is_obvious_non_job(job.title, job.description_text)
