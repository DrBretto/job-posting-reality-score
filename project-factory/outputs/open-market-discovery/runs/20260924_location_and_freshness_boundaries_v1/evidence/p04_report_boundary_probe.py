"""R2 evidence: freshness timing reaching the report through production wiring.

Why this exists alongside the P03 review's own probe. That probe writes its run manifest with
`created_at` and `run_started_at` keys, but the manifest ENUMERATE actually writes is a `RunManifest`
whose start field is **`opened_at`** (src/enumerate/handler.py). So after the repair the reviewer's
probe exercises the manifest-ABSENT fallback path: it shows `run_started_at` populated where it was
previously `null`, with the basis labelled "report_invocation_time (RUN_OPEN manifest absent)", and
still reports 0 fresh because its mocked bucket holds no previous report either. Both are correct
answers to what that fixture actually contains. The reviewer's probe is left untouched.

This probe uses the production manifest shape and two consecutive rounds, and reads what the real
`handler()` PERSISTED to S3 — never a ReportInput whose timing fields a test filled in.

Runs entirely against mocked S3. No network, no AWS, no email, no credentials.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.common import s3layout
from src.common.models import CanonicalJob, IdKind, RemoteMode
from src.report.handler import handler, resolve_run_timing

BUCKET = "p04-boundary-probe"
NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
WORK = (
    "Responsibilities: build Python backend services, internal tools and AWS Lambda integrations. "
    "Interview process: two live video calls with the team."
)


def job(key, *, first_seen, last_seen, published=None, source="remotive:all"):
    return CanonicalJob(
        source_id=source, job_id=f"{source}#{key}", id_kind=IdKind.NATIVE_ID,
        provider_native_id=key, employer_name=f"Employer {key}",
        title="Senior Software Engineer", raw_location="Remote, US",
        canonical_location="remote, us", remote_hybrid_language=RemoteMode.REMOTE,
        description_text=WORK, posting_url=f"https://example.com/{key}",
        apply_url=f"https://example.com/{key}", first_seen_at=first_seen,
        last_seen_at=last_seen, provider_published_at=published,
    )


def production_manifest(run_id, opened_at):
    """The shape src/enumerate/handler.py writes: `opened_at`, not `created_at`."""
    return {
        "run_id": run_id, "opened_at": opened_at.isoformat(), "state": "RUN_OPEN",
        "expected_tasks": [], "expected_sources": ["remotive:all"],
        "source_labels": {"remotive:all": "Remotive"},
        "source_kinds": {"remotive:all": "DISCOVERY_FEED"},
        "expected_discovery_sources": [], "credential_gated_sources": {},
    }


def lay_down_round(s3, run_id, opened_at, jobs, *, observations, succeeded=True):
    def put(key, payload):
        s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(payload, default=str).encode())

    put(s3layout.run_manifest_key(run_id), production_manifest(run_id, opened_at))
    put(s3layout.current_jobs_key("remotive", "all"), [j.model_dump(mode="json") for j in jobs])
    put(s3layout.current_state_key("remotive", "all"), {
        "source_id": "remotive:all",
        "success_count_history": [1] * observations,
        "jobs": {j.job_id: {"first_seen_at": j.first_seen_at.isoformat(),
                            "last_seen_at": j.last_seen_at.isoformat()} for j in jobs},
    })
    if succeeded:
        put(s3layout.collect_sentinel_key(run_id, "remotive", "all"), {})


def run_report(s3, run_id, dt):
    env = {"JPRS_BUCKET": BUCKET, "AWS_DEFAULT_REGION": "us-east-1",
           "SES_SENDER": "", "DIGEST_RECIPIENT": ""}
    with patch.dict(os.environ, env):
        handler({"run_id": run_id, "dt": dt}, None)
    return json.loads(
        s3.get_object(Bucket=BUCKET, Key=s3layout.report_json_key(dt))["Body"].read())


def rows(report):
    return {r["job_id"]: r["is_fresh_arrival"] for r in report["complete_candidate_list"]}


def main():
    env = {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
           "AWS_DEFAULT_REGION": "us-east-1"}
    out = {}
    with patch.dict(os.environ, env), mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)

        # ---- round one: yesterday, a warm source -------------------------------------------------
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        known = job("known-since-last-week", first_seen=yesterday - timedelta(days=6),
                    last_seen=yesterday)
        mid_round = job("found-midway-through-yesterday",
                        first_seen=yesterday + timedelta(minutes=5), last_seen=yesterday)
        lay_down_round(s3, "2026-09-23", yesterday, [known, mid_round], observations=5)
        first = run_report(s3, "2026-09-23", "2026-09-23")
        out["round_one"] = {
            "timing": first["timing"],
            "fresh_count": first["fresh_arrival_count"],
            "rows": rows(first),
        }

        # ---- round two: this morning, one genuinely new arrival -----------------------------------
        today = NOW.replace(hour=7, minute=5)
        arrived = job("arrived-this-morning", first_seen=today, last_seen=today,
                      published=NOW - timedelta(hours=20))
        undated = job("undated-new-to-us", first_seen=today, last_seen=today, published=None)
        lay_down_round(s3, "2026-09-24", today,
                       [known, mid_round, arrived, undated], observations=6)
        second = run_report(s3, "2026-09-24", "2026-09-24")
        out["round_two"] = {
            "timing": second["timing"],
            "fresh_count": second["fresh_arrival_count"],
            "rows": rows(second),
            "age_labels": {r["job_id"]: r["age_label"]
                           for r in second["complete_candidate_list"]},
            "retained_rows": len(second["complete_candidate_list"]),
        }

        # ---- a retry of round two must not read its own first attempt as the previous round -------
        retry = run_report(s3, "2026-09-24", "2026-09-24")
        out["round_two_retry"] = {
            "previous_run_id": retry["timing"]["previous_run_id"],
            "fresh_count": retry["fresh_arrival_count"],
        }

        # ---- the reviewer's manifest shape, for the record ----------------------------------------
        s3.put_object(
            Bucket=BUCKET, Key=s3layout.run_manifest_key("2026-09-25"),
            Body=json.dumps({"run_id": "2026-09-25", "expected_sources": ["remotive:all"],
                             "source_labels": {"remotive:all": "Remotive"},
                             "created_at": NOW.isoformat(),
                             "run_started_at": NOW.isoformat()}).encode())
        fallback = resolve_run_timing(s3, BUCKET, "2026-09-25", "2026-09-25")
        out["reviewer_manifest_shape"] = {
            "basis": fallback.basis,
            "note": ("the review probe writes created_at/run_started_at; production writes "
                     "opened_at, so this path is the labelled fallback, not a silent guess"),
            "previous_run_id": fallback.previous_run_id,
        }

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
