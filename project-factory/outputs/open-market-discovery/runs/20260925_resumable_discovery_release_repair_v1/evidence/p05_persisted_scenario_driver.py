"""Both P04-review scenarios, driven across runs to a PERSISTED candidate report.

What is real here and what is not, stated plainly:

  real        the discovery walk, the state model and its S3-shaped serialization, the connector,
              screening, scoring, dedup, the report handler and the report it persists
  mocked      the outbound HTTP transport (provider-shaped payloads) and S3 (moto)
  absent      the network, AWS, credentials, email

So this is evidence that the repaired traversal makes the two formerly-lost postings reach the
artifact the operator reads. It is NOT evidence that the production transport works; that remains a
separate activation check (DEPLOYMENT_HANDOFF §3.4).

State is serialized and reloaded at every run boundary, because production stores it in S3 between
invocations and an in-memory handoff would prove nothing about the persisted path. Each scenario keeps
a 24-page historical backlog open so no run can reach the end of the feed, restart at page one and
re-collect the lost posting by accident — the exact way a broken walk looked correct before.

Writes: `reports/<scenario>/run<n>/daily_report.{json,md}` and `state_after.json` under this run root.
Nothing else, nowhere else.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

RUN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from src.common import s3layout  # noqa: E402
from src.common.connectors import FetchResult  # noqa: E402
from src.discovery.budget import DiscoveryState  # noqa: E402
from src.discovery.handler import run_discovery  # noqa: E402

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
BUCKET = "jprs-p05-scenarios"
DESCRIPTION = (
    "Responsibilities: build Python backend services, internal tools, AWS Lambda integrations and "
    "LLM evaluation workflows. Interview process: two live video calls with the team."
)
BACKLOG_PAGES = 24


def page(label, next_cursor, age_hours):
    return {
        "jobs": [{
            "title": "Senior Software Engineer", "companyName": f"Employer {label}",
            "companySlug": label, "excerpt": DESCRIPTION, "description": DESCRIPTION,
            "applicationLink": f"https://himalayas.app/companies/x/jobs/{label}",
            "guid": f"https://himalayas.app/companies/x/jobs/{label}",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "pubDate": str(int((NOW - timedelta(hours=age_hours)).timestamp())),
        }],
        "nextCursor": next_cursor, "totalCount": 999,
    }


def with_backlog(pages):
    for number in range(BACKLOG_PAGES):
        cursor = "OLD" if number == 0 else f"OLD_{number}"
        pages[cursor] = page(f"historical-{number}", f"OLD_{number + 1}", 300 + number)
    return pages


class Transport:
    def __init__(self, pages, *, fail_on=()):
        self.pages = pages
        self.fail_on = set(fail_on)
        self.requested: list[str | None] = []

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requested.append(cursor)
        if cursor in self.fail_on:
            raise TimeoutError(f"page {cursor} timed out")
        return FetchResult(
            raw_bytes=json.dumps(self.pages[cursor]).encode(), http_status=200,
            error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW,
        )


def persist_report(jobs, *, run_id, dt, out_dir: Path) -> dict:
    """Run the REAL report handler against mocked S3 and save what it persisted."""
    by_source: dict[str, list] = {}
    for job in jobs:
        by_source.setdefault(job.source_id, []).append(job)

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)

        def put(key, payload):
            s3.put_object(Bucket=BUCKET, Key=key,
                          Body=json.dumps(payload, default=str).encode())

        put(s3layout.run_manifest_key(run_id), {
            "run_id": run_id, "opened_at": NOW.isoformat(), "state": "RUN_OPEN",
            "expected_tasks": [], "expected_sources": sorted(by_source),
            "source_labels": {s: s.partition(":")[0].title() for s in by_source},
            "source_kinds": {s: "DISCOVERY_FEED" for s in by_source},
            "expected_discovery_sources": sorted(by_source),
            "credential_gated_sources": {},
        })
        for source, source_jobs in by_source.items():
            provider, _, board = source.partition(":")
            put(s3layout.current_jobs_key(provider, board),
                [job.model_dump(mode="json") for job in source_jobs])
            put(s3layout.current_state_key(provider, board), {
                "source_id": source, "success_count_history": [1, 1],
                "jobs": {job.job_id: {"first_seen_at": job.first_seen_at.isoformat(),
                                      "last_seen_at": job.last_seen_at.isoformat()}
                         for job in source_jobs},
            })
            put(s3layout.collect_sentinel_key(run_id, provider, board), {})

        from src.report.handler import handler
        env = {"JPRS_BUCKET": BUCKET, "AWS_DEFAULT_REGION": "us-east-1",
               "SES_SENDER": "", "DIGEST_RECIPIENT": ""}
        with patch.dict(os.environ, env):
            handler({"run_id": run_id, "dt": dt}, None)

        report = json.loads(
            s3.get_object(Bucket=BUCKET, Key=s3layout.report_json_key(dt))["Body"].read()
        )
        markdown = s3.get_object(
            Bucket=BUCKET, Key=s3layout.report_md_key(dt)
        )["Body"].read().decode()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "daily_report.json").write_text(json.dumps(report, indent=2, default=str))
    (out_dir / "daily_report.md").write_text(markdown)
    return report


def state_facts(state: DiscoveryState) -> dict:
    budget = state.budgets.get("himalayas")
    return {
        "backfill_position": state.source_cursors.get("himalayas"),
        "owed_recent_ranges": state.pending_head("himalayas"),
        "compatibility_mirror": state.head_cursors.get("himalayas"),
        "observed_frontier": state.head_frontier_at.get("himalayas"),
        "requests_spent": budget.requests_spent if budget else None,
        "failures": budget.failures if budget else None,
        "backlog_reason": state.backlog.reason,
    }


def run_scenario(name: str, mutations, *, budget: int, target: str) -> dict:
    """`mutations` is a list of callables applied to the page map before each run."""
    pages = with_backlog({})
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    collected: list = []
    runs: list[dict] = []

    for index, mutate in enumerate(mutations, start=1):
        fail_on = mutate(pages) or ()
        transport = Transport(pages, fail_on=fail_on)
        run_id = f"{name}-run{index}"
        outcome = run_discovery(
            run_id=run_id, now=NOW, fetcher=transport, providers=["himalayas"],
            state=state, env={}, max_pages_per_source=budget,
        )
        collected.extend(outcome.jobs)
        report = persist_report(
            collected, run_id=run_id, dt="2026-09-24",
            out_dir=RUN_ROOT / "reports" / name / f"run{index}",
        )
        rows = {row["job_id"]: row.get("employer")
                for row in report["complete_candidate_list"]}
        facts = state_facts(state)
        runs.append({
            "run_id": run_id,
            "cursors_requested": ["page1(None)" if c is None else c
                                  for c in transport.requested],
            "requests": len(transport.requested),
            "budget": budget,
            "within_budget": len(transport.requested) <= budget,
            "state_after": facts,
            "reported_incomplete_coverage": [
                item for item in outcome.coverage_doc()["inaccessible"]
                if "recent arrivals" in item["target"]
            ],
            "target_in_persisted_report": target in rows,
            "persisted_candidate_rows": len(rows),
            "report_dir": str((RUN_ROOT / "reports" / name / f"run{index}")
                              .relative_to(RUN_ROOT)),
        })
        (RUN_ROOT / "reports" / name / f"run{index}" / "state_after.json").write_text(
            json.dumps(facts, indent=2, default=str)
        )
        state = DiscoveryState.model_validate(json.loads(state.model_dump_json()))

    positions = [r["state_after"]["backfill_position"] for r in runs]
    indexes = [0 if p == "OLD" else int(p.split("_")[1]) for p in positions if p]
    return {
        "runs": runs,
        "target": target,
        "target_reached_on_run": next(
            (r["run_id"] for r in runs if r["target_in_persisted_report"]), None
        ),
        "every_run_within_budget": all(r["within_budget"] for r in runs),
        "backfill_never_rewound": indexes == sorted(indexes),
        "backfill_positions": positions,
        "owed_drained_by_the_end": runs[-1]["state_after"]["owed_recent_ranges"] == [],
    }


def main() -> int:
    # Scenario one: a recent page fails while a long historical backlog is open.
    def s1_run1(pages):
        pages[None] = page("fresh-one", "NEW_TWO", 1)
        pages["NEW_TWO"] = page("fresh-two", "OLD", 2)
        return {"NEW_TWO"}                       # the page that times out

    def s1_later(pages):
        return ()                                # the feed is healthy from now on

    failure = run_scenario(
        "failed_recent_page", [s1_run1, s1_later, s1_later],
        budget=3, target="himalayas:NEW_TWO#fresh-two",
    )

    # Scenario two: newer pages arrive above a saved continuation.
    def s2_run1(pages):
        pages[None] = page("burst-one", "B2", 1)
        pages["B2"] = page("burst-two", "B3", 2)
        pages["B3"] = page("burst-three", "OLD", 3)
        return ()

    def s2_run2(pages):
        pages[None] = page("newer-one", "NEWER_TWO", 0.1)
        pages["NEWER_TWO"] = page("newer-two", "B2", 0.2)
        return ()

    def s2_later(pages):
        return ()

    burst = run_scenario(
        "new_burst_above_saved_continuation",
        [s2_run1, s2_run2, s2_later, s2_later, s2_later],
        budget=3, target="himalayas:NEWER_TWO#newer-two",
    )

    result = {
        "scope": (
            "real discovery walk, real state serialization, real screening/scoring/report handler; "
            "mocked HTTP transport and mocked S3; no network, no AWS, no credential, no email"
        ),
        "failed_recent_page": failure,
        "new_burst_above_saved_continuation": burst,
        "assertions": {
            "scenario_one_formerly_lost_job_reaches_the_persisted_report":
                failure["target_reached_on_run"] is not None,
            "scenario_two_formerly_lost_job_reaches_the_persisted_report":
                burst["target_reached_on_run"] is not None,
            "every_run_stayed_within_its_source_budget":
                failure["every_run_within_budget"] and burst["every_run_within_budget"],
            "the_historical_backfill_never_rewound":
                failure["backfill_never_rewound"] and burst["backfill_never_rewound"],
            "owed_ranges_drained_to_empty_in_both_scenarios":
                failure["owed_drained_by_the_end"] and burst["owed_drained_by_the_end"],
        },
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if all(result["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
