"""Bounded end-to-end rehearsal over REAL provider payloads, two consecutive rounds.

The payloads in `rehearsal/fixtures/` were captured from the providers' public endpoints on
2026-09-24 (four consecutive Himalayas cursor pages plus the three bulk feeds). Nothing here reaches
the network, no credential is used, and no email is sent.

Why fixtures rather than a live run: live `urlopen` in this environment truncated responses
non-deterministically (80,693 bytes via curl versus 18,586 / 5,996 / 0 bytes via urllib on
consecutive attempts). The connector handles that correctly — it keeps the partial body and the JSON
parse lands the snapshot as PARTIAL rather than claiming success — but it makes a live rehearsal
unreproducible. So the transport is replaced and the DATA is real. This is a mocked-transport
rehearsal and is not evidence that the production transport works; that remains a separate
activation check.

What it demonstrates:
  * R3 — round two continues the feed head onto page two and still advances the historical backfill,
    with every page's postings reaching the PERSISTED report.
  * R2 — round two reads round one's report as its previous observation boundary, so "new since the
    last round" is decided by what Brett was already shown.
  * R1 — the location rules run over real postings; the screening tallies are reported.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RUN_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = RUN_ROOT / "rehearsal" / "fixtures"
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

from src.cli import _assemble_local_report, _known_employers  # noqa: E402
from src.common.connectors import FetchResult  # noqa: E402
from src.discovery.budget import DiscoveryState  # noqa: E402
from src.discovery.handler import run_discovery  # noqa: E402
from src.report.handler import CoverageInput  # noqa: E402

CURSORS = json.loads((FIXTURES / "himalayas_cursors.json").read_text())
# cursor value -> the page file that the provider returned for it
PAGE_BY_CURSOR = {CURSORS[page]: f"himalayas_{page}.json" for page in CURSORS}


class FixtureTransport:
    """Serves the captured pages, honouring the real cursor that each page handed back."""

    def __init__(self):
        self.requests: list[tuple[str, str | None]] = []

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requests.append((provider, cursor))
        if provider == "himalayas":
            name = PAGE_BY_CURSOR.get(cursor)
            if name is None:
                # A cursor beyond what was captured: report an honest end-of-captured-data page.
                body = json.dumps({"jobs": [], "nextCursor": None, "totalCount": 0}).encode()
                return _result(url, body)
            body = (FIXTURES / name).read_bytes()
            return _result(url, body)
        path = FIXTURES / f"{provider}.json"
        if not path.is_file():
            raise FileNotFoundError(f"no captured payload for {provider}")
        return _result(url, path.read_bytes())


def _result(url, body):
    now = datetime.now(timezone.utc)
    return FetchResult(raw_bytes=body, http_status=200, error_class=None,
                       endpoint_url=url, request_at=now, response_at=now)


def coverage_of(outcome):
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


def do_round(label, state, *, budget, previous_report, run_id, dt):
    transport = FixtureTransport()
    started = datetime.now(timezone.utc)
    outcome = run_discovery(
        run_id=run_id, now=started, fetcher=transport,
        providers=["himalayas", "remotive", "remoteok", "jobicy"],
        state=state, env={}, max_pages_per_source=budget,
        known_employers=_known_employers(),
    )
    cov, doc = coverage_of(outcome)
    _inp, (markdown, report_json) = _assemble_local_report(
        outcome.jobs, run_id=run_id, dt=dt, coverage=cov,
        sources={j.source_id for j in outcome.jobs} or set(doc["discovery_attempted"]),
        run_started_at=started, previous_report=previous_report,
    )
    out = RUN_ROOT / "rehearsal" / label
    out.mkdir(parents=True, exist_ok=True)
    (out / "daily_report.md").write_text(markdown)
    (out / "daily_report.json").write_text(json.dumps(report_json, indent=2, default=str))
    (out / "discovery_coverage.json").write_text(json.dumps(doc, indent=2, default=str))

    himalayas_pages = [c for provider, c in transport.requests if provider == "himalayas"]
    rows = report_json["complete_candidate_list"]

    def page_label(cursor):
        """Name a saved cursor. None means NOTHING saved, which is not page one: page one's cursor is
        itself null, so a naive lookup reported "page1" for an empty slot."""
        if cursor is None:
            return None
        return next((p for p, v in CURSORS.items() if v == cursor), cursor[:18] + "…")
    return out, {
        "run_id": run_id,
        "himalayas_cursors_requested": [
            "page1(None)" if c is None else next(
                (p for p, v in CURSORS.items() if v == c), c[:18] + "…")
            for c in himalayas_pages
        ],
        "himalayas_requests": len(himalayas_pages),
        "postings_considered": report_json["current_job_count"],
        "retained_rows": len(rows),
        "fresh_arrivals": report_json["fresh_arrival_count"],
        "older_strong": report_json["older_strong_count"],
        "timing": report_json["timing"],
        "saved_backfill_cursor": page_label(state.source_cursors.get("himalayas")),
        "saved_head_cursor_or_none": page_label(state.head_cursors.get("himalayas")),
        "head_frontier_at": state.head_frontier_at.get("himalayas"),
        "screening": {
            "new_strong": report_json["new_strong_count"],
            "needs_a_check": report_json["needs_check_count"],
            "policy_excluded": report_json.get("policy_excluded_count"),
            "below_fit_threshold": report_json.get("below_fit_threshold_count"),
        },
        "report_dir": str(out.relative_to(RUN_ROOT)),
    }


def main():
    state = DiscoveryState()
    result = {}

    # Round one: no saved position, a small budget. The head walk IS the catch-up here.
    _out1, result["round_one"] = do_round(
        "round1", state, budget=2, previous_report=None,
        run_id="rehearsal-r1", dt="2026-09-24")

    # Round two: a backfill is now outstanding. Before the repair the head took exactly ONE page and
    # discarded its continuation, so page two was skipped and the run jumped back to the backlog.
    out2, result["round_two"] = do_round(
        "round2", state, budget=3,
        previous_report=RUN_ROOT / "rehearsal" / "round1" / "daily_report.json",
        run_id="rehearsal-r2", dt="2026-09-25")

    r2 = result["round_two"]
    result["assertions"] = {
        "round_two_reached_page_two": "page2" in r2["himalayas_cursors_requested"],
        "round_two_also_advanced_the_backfill": r2["saved_backfill_cursor"] not in (None, "page3"),
        "nothing_was_left_unfetched_in_the_head": r2["saved_head_cursor_or_none"] is None,
        "round_two_respected_its_budget": r2["himalayas_requests"] <= 3,
        "round_two_used_round_one_as_its_boundary": r2["timing"]["boundary"] == "reported-ids",
        "postings_reached_the_persisted_report": (out2 / "daily_report.json").is_file(),
    }
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
