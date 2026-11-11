import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.candidate.screening import screen_job
from src.common import s3layout
from src.common.connectors import FetchResult
from src.common.models import CanonicalJob, IdKind, RemoteMode, VerificationState
from src.common.normalize import detect_remote_mode
from src.discovery.budget import DiscoveryState
from src.discovery.handler import run_discovery
from src.report.handler import assemble_report_input, handler, render_report


NOW = datetime(2026, 9, 24, 12, tzinfo=timezone.utc)
DESCRIPTION = (
    "Responsibilities: Build Python backend services, internal tools, AWS Lambda integrations, "
    "LLM applications and evaluation workflows. Interview process: two live calls with humans."
)


def make_job(key, location, description=DESCRIPTION, mode=None, **fields):
    return CanonicalJob(
        source_id="remotive:all", job_id=f"remotive:all#{key}",
        id_kind=IdKind.NATIVE_ID, provider_native_id=key,
        employer_name=f"Review Employer {key}", title="Senior Software Engineer, Applied AI",
        raw_location=location, canonical_location=location.lower(),
        remote_hybrid_language=mode or detect_remote_mode(None, location, description),
        verification_state=VerificationState.FEED_COMPLETE,
        description_text=description, posting_url=f"https://example.com/jobs/{key}",
        apply_url=f"https://example.com/jobs/{key}", **fields,
    )


def probe_location():
    rows = []
    for location, extra in (
        ("Belmont, NH", "On-site at our office five days per week. "),
        ("Belmont NH", "On-site at our office five days per week. "),
        ("Alton, IL", "On-site at our office five days per week. "),
        ("Remote / Boston, MA", "Hybrid: must attend the Boston office three days per week. "),
        ("Remote, US", "This remote role may only employ residents of California or New York. "),
    ):
        job = make_job(str(len(rows)), location, extra + DESCRIPTION)
        verdict = screen_job(job)
        rows.append({
            "location": location, "mode": job.remote_hybrid_language.value,
            "condition": extra.strip(), "verdict": verdict.outcome,
            "reason": verdict.human_reason(),
        })
    return rows


def feed_page(label, next_cursor, age_hours):
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


def probe_head_gap():
    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLDER_CURSOR"
    pages = {
        None: feed_page("new-page-one", "NEW_PAGE_TWO", 1),
        "NEW_PAGE_TWO": feed_page("new-page-two", "OLDER_CURSOR", 2),
        "OLDER_CURSOR": feed_page("old-page", "OLDER_AGAIN", 240),
        "OLDER_AGAIN": feed_page("older-again", "EVEN_OLDER", 480),
        "EVEN_OLDER": feed_page("even-older", "STILL_OLDER", 720),
        "STILL_OLDER": feed_page("still-older", "DEEPER_BACKLOG", 960),
    }
    requested = []

    def fetcher(provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        requested.append(cursor)
        payload = pages.get(cursor, feed_page("ancient", "STILL_OLDER", 720))
        return FetchResult(
            raw_bytes=json.dumps(payload).encode(), http_status=200,
            error_class=None, endpoint_url=url, request_at=NOW, response_at=NOW,
        )

    outcome = run_discovery(
        run_id="review-day-two", now=NOW, fetcher=fetcher,
        providers=["himalayas"], state=state, env={}, max_pages_per_source=5,
    )
    return {
        "requests": requested, "new_page_two_requested": "NEW_PAGE_TWO" in requested,
        "employers_seen": sorted({job.employer_name for job in outcome.jobs}),
        "next_backfill_cursor": outcome.state.source_cursors["himalayas"],
    }


def probe_report_boundary():
    env = {
        "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_DEFAULT_REGION": "us-east-1", "JPRS_BUCKET": "independent-review-bucket",
        "SES_SENDER": "", "DIGEST_RECIPIENT": "",
    }
    with patch.dict(os.environ, env), mock_aws():
        storage = boto3.client("s3", region_name="us-east-1")
        bucket = env["JPRS_BUCKET"]
        storage.create_bucket(Bucket=bucket)

        def put(key, payload):
            storage.put_object(Bucket=bucket, Key=key, Body=json.dumps(payload, default=str).encode())

        previous = NOW - timedelta(days=1)
        jobs = [
            make_job("established", "Remote, US", mode=RemoteMode.REMOTE,
                     first_seen_at=NOW - timedelta(days=20), last_seen_at=NOW,
                     provider_published_at=NOW - timedelta(days=21)),
            make_job("newly-observed-undated", "Remote, US", mode=RemoteMode.REMOTE,
                     first_seen_at=NOW - timedelta(hours=1), last_seen_at=NOW),
            make_job("twenty-hours-old", "Remote, US", mode=RemoteMode.REMOTE,
                     first_seen_at=NOW - timedelta(hours=1), last_seen_at=NOW,
                     provider_published_at=NOW - timedelta(hours=20)),
        ]
        for day, timestamp in (("2026-09-23", previous), ("2026-09-24", NOW)):
            put(s3layout.run_manifest_key(day), {
                "run_id": day, "expected_sources": ["remotive:all"],
                "source_labels": {"remotive:all": "Remotive"},
                "created_at": timestamp.isoformat(), "run_started_at": timestamp.isoformat(),
            })
        put(s3layout.current_jobs_key("remotive", "all"), [job.model_dump(mode="json") for job in jobs])
        put(s3layout.current_state_key("remotive", "all"), {
            "source_id": "remotive:all", "success_count_history": [1, 3],
            "jobs": {job.job_id: {
                "first_seen_at": job.first_seen_at.isoformat(), "last_seen_at": NOW.isoformat(),
            } for job in jobs},
        })
        put(s3layout.collect_sentinel_key("2026-09-24", "remotive", "all"), {})
        assembled = assemble_report_input(storage, bucket, "2026-09-24", "2026-09-24")
        observed_timing = {
            "run_started_at": assembled.run_started_at,
            "previous_run_at": assembled.previous_run_at,
        }
        handler({"run_id": "2026-09-24", "dt": "2026-09-24"}, None)
        persisted = json.loads(storage.get_object(
            Bucket=bucket, Key=s3layout.report_json_key("2026-09-24"),
        )["Body"].read())
        assembled.run_started_at = NOW
        assembled.previous_run_at = previous
        _, with_timing = render_report(assembled)
        return {
            "production_timing_fields": observed_timing,
            "persisted_fresh_count": persisted["fresh_arrival_count"],
            "fresh_count_when_actual_timing_is_supplied": with_timing["fresh_arrival_count"],
            "retained": [{"job_id": row["job_id"], "fresh": row["is_fresh_arrival"]}
                         for row in persisted["complete_candidate_list"]],
        }


if __name__ == "__main__":
    print(json.dumps({
        "location": probe_location(), "head_gap": probe_head_gap(),
        "report_boundary": probe_report_boundary(),
    }, indent=2, default=str))
