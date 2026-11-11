"""Per-posting disposition audit over the captured posting slice, through the REAL caller path.

Purpose: the P10 packet requires the screening/ranking consequences of a policy change to be
measured on the same available captured postings before and after the change, with every changed
disposition named by job id and reason. A count is not evidence; an identity is.

What this runs: `run_discovery` over the captured provider payloads in
`…/20260924_location_and_freshness_boundaries_v1/rehearsal/fixtures/` (four consecutive Himalayas
cursor pages plus the three bulk feeds, captured from the providers' public endpoints on
2026-09-24), then the ordinary `_assemble_local_report` path — the same function the CLI and the
report Lambda reach, so dedup, scoring, screening, history and ranking are the production ones and
not a reimplementation here.

Limits, stated rather than implied:
  * Nothing here reaches the network. The transport is a fixture server; this is not evidence that
    the live transport works, and it is not a claim about the current job market.
  * The corpus is one captured slice from four keyless remote-job feeds on one day. It is not a
    census of open roles, and a posting absent from it is not absent from the market.
  * Every disposition below is this system's screening verdict on stored text, not a hiring outcome.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RUN_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = Path(__file__).resolve().parents[6]
FIXTURES = (
    REPO_ROOT
    / "project-factory/outputs/open-market-discovery/runs"
    / "20260924_location_and_freshness_boundaries_v1/rehearsal/fixtures"
)
sys.path.insert(0, str(REPO_ROOT))

from src.candidate.screening import screen_all  # noqa: E402
from src.cli import _assemble_local_report, _known_employers  # noqa: E402
from src.common.connectors import FetchResult  # noqa: E402
from src.discovery.budget import DiscoveryState  # noqa: E402
from src.discovery.handler import run_discovery  # noqa: E402
from src.report.handler import CoverageInput  # noqa: E402

CURSORS = json.loads((FIXTURES / "himalayas_cursors.json").read_text())
PAGE_BY_CURSOR = {CURSORS[page]: f"himalayas_{page}.json" for page in CURSORS}


class FixtureTransport:
    """Serves the captured pages, honouring the real cursor each page handed back."""

    def __init__(self):
        self.requests: list[tuple[str, str | None]] = []

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requests.append((provider, cursor))
        if provider == "himalayas":
            name = PAGE_BY_CURSOR.get(cursor)
            if name is None:
                body = json.dumps({"jobs": [], "nextCursor": None, "totalCount": 0}).encode()
                return _result(url, body)
            return _result(url, (FIXTURES / name).read_bytes())
        path = FIXTURES / f"{provider}.json"
        if not path.is_file():
            raise FileNotFoundError(f"no captured payload for {provider}")
        return _result(url, path.read_bytes())


def _result(url, body):
    now = datetime.now(timezone.utc)
    return FetchResult(raw_bytes=body, http_status=200, error_class=None,
                       endpoint_url=url, request_at=now, response_at=now)


def _coverage_of(outcome):
    doc = outcome.coverage_doc()
    cov = CoverageInput(
        discovery_attempted=doc["discovery_attempted"],
        discovery_succeeded=doc["discovery_succeeded"],
        query_families_total=doc["query_families_total"],
        query_families_covered=doc["query_families_covered"],
        query_families_saturated=doc["query_families_saturated"],
        query_families_deferred=doc["query_families_deferred"],
        query_families_never_run=doc["query_families_never_run"],
        backlog_items=doc["backlog_items"],
        backlog_reason=doc.get("backlog_reason"),
        budgets=doc["budgets"],
        credential_gated=doc["credential_gated"],
        inaccessible=doc["inaccessible"],
        attributions=doc["attributions"],
        admission_summary=doc["admission_summary"],
        previously_unseen_employers=sorted(
            {j.employer_name for j in outcome.jobs if j.employer_name} - _known_employers()
        ),
    )
    return cov, doc


def audit(budget: int = 4) -> dict:
    state = DiscoveryState()
    transport = FixtureTransport()
    started = datetime.now(timezone.utc)
    outcome = run_discovery(
        run_id="p10-audit", now=started, fetcher=transport,
        providers=["himalayas", "remotive", "remoteok", "jobicy"],
        state=state, env={}, max_pages_per_source=budget,
        known_employers=_known_employers(),
    )
    cov, _doc = _coverage_of(outcome)
    _inp, (_markdown, report_json) = _assemble_local_report(
        outcome.jobs, run_id="p10-audit", dt="2026-09-26", coverage=cov,
        sources={j.source_id for j in outcome.jobs},
        run_started_at=started, previous_report=None,
    )

    jobs_by_id = {j.job_id: j for j in outcome.jobs}
    screens = screen_all(outcome.jobs)

    retained_ids = {row["job_id"] for row in report_json["complete_candidate_list"]}
    excluded_ids = {row["job_id"] for row in report_json["policy_exclusions"]}
    below_ids = set(report_json["below_fit_threshold_job_ids"])

    def bucket(job_id: str) -> str:
        if job_id in excluded_ids:
            return "policy_excluded"
        if job_id in retained_ids:
            return "retained"
        if job_id in below_ids:
            return "below_fit_threshold"
        return "not_in_report"

    dispositions = {}
    for job_id, job in sorted(jobs_by_id.items()):
        screen = screens[job_id]
        dispositions[job_id] = {
            "employer": job.employer_name,
            "title": job.title,
            "bucket": bucket(job_id),
            "screen_outcome": screen.outcome,
            "exclusion_rules": sorted({h.rule_id for h in screen.exclusions}),
            "pending_rules": sorted({h.rule_id for h in screen.pending_checks}),
            "suppressed_rules": sorted({h.rule_id for h in screen.suppressed}),
            "reason": screen.human_reason(),
            "evidence_spans": [
                {"rule_id": h.rule_id, "section": h.section, "matched": h.matched_text[:160]}
                for h in screen.exclusions + screen.pending_checks
            ],
        }

    return {
        "corpus": {
            "fixtures_dir": str(FIXTURES.relative_to(REPO_ROOT)),
            "captured_on": "2026-09-24",
            "providers": ["himalayas", "remotive", "remoteok", "jobicy"],
            "pages_per_source_budget": budget,
            "network_used": False,
            "limits": (
                "one captured slice from four keyless remote-job feeds on one day; not a market "
                "census and not evidence that the live transport works"
            ),
        },
        "ruleset_version": next(iter(screens.values())).ruleset_version if screens else None,
        "totals": {
            "postings_considered": report_json["current_job_count"],
            "retained": len(retained_ids),
            "policy_excluded": report_json["policy_excluded_count"],
            "below_fit_threshold": report_json["below_fit_threshold_count"],
            "new_strong": report_json["new_strong_count"],
            "needs_a_check": report_json["needs_check_count"],
        },
        "dispositions": dispositions,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--budget", type=int, default=4)
    args = ap.parse_args()
    result = audit(budget=args.budget)
    Path(args.out).write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result["totals"], indent=2))
    print(f"wrote {args.out} with {len(result['dispositions'])} dispositions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
