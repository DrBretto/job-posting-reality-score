"""End-to-end integration tests for the S3 glue (differ + report handlers).

Unlike the pure-function unit tests, these run the ACTUAL Lambda handler code against a mocked S3
(moto), seeded the way the collector really writes it. They assert the wiring — the exact class of
bug that shipped: the differ silently writing nothing, and the report rendering an empty 0/0 input.
"""

import json
from datetime import datetime, timezone

import boto3
import pytest
from moto import mock_aws

from src.common import s3layout
from src.common.models import SCHEMA_VERSION

BUCKET = "jprs-test-bucket"
PROVIDER, BOARD = "greenhouse", "acme"
SID = f"{PROVIDER}:{BOARD}"
DT = "2026-08-01"


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        monkeypatch.setenv("JPRS_BUCKET", BUCKET)
        monkeypatch.delenv("SES_SENDER", raising=False)
        monkeypatch.delenv("DIGEST_RECIPIENT", raising=False)
        yield client


def _put(client, key, obj):
    client.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(obj).encode())


def _get(client, key):
    return json.loads(client.get_object(Bucket=BUCKET, Key=key)["Body"].read())


def _job(job_id, title="Engineer", dept="Eng", body="b"):
    return {
        "source_id": SID, "job_id": job_id, "id_kind": "NATIVE_ID", "title": title, "department": dept,
        "canonical_location": "remote", "raw_location": "Remote - United States",
        "remote_hybrid_language": "REMOTE", "description_text": body,
        "posting_url": f"https://job-boards.greenhouse.io/acme/jobs/{job_id}",
        "content_hash": f"h-{job_id}-{title}-{body}",
        "field_hashes": {"title_hash": f"t-{title}", "body_hash": f"b-{body}"},
        "schema_version": SCHEMA_VERSION,
    }


def _status(status="SUCCESS", n=2, snap="snap-1"):
    return {
        "source_id": SID, "status": status, "snapshot_id": snap,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "job_count_observed": n, "http_status": 200, "error_class": None,
    }


def _seed_collection(client, jobs, status="SUCCESS", snap="snap-1", run_id=DT, dt=DT):
    """Mimic what the collector writes for one source: status/, normalized/, and (on SUCCESS) the sentinel."""
    _put(client, s3layout.source_status_key(PROVIDER, BOARD), _status(status, len(jobs), snap))
    _put(client, s3layout.normalized_key(PROVIDER, BOARD, dt), jobs)
    if status in ("SUCCESS", "EMPTY_SUCCESS"):
        _put(client, s3layout.collect_sentinel_key(run_id, PROVIDER, BOARD),
             {"run_id": run_id, "source_id": SID, "snapshot_id": snap, "status": status})


def _seed_manifest(client, run_id=DT, sources=(SID,)):
    _put(client, s3layout.run_manifest_key(run_id),
         {"run_id": run_id, "state": "RUN_OPEN", "expected_sources": list(sources)})


# --------------------------------------------------------------------------------------------------

def test_differ_first_run_writes_events_and_current(s3):
    """First run: two jobs -> two first-seen events + current/ baseline + persisted state."""
    from src.differ import handler as differ

    _seed_collection(s3, [_job("j1"), _job("j2")])
    now = datetime.now(timezone.utc)
    out = differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=DT, dt=DT, today=now)

    assert out["events"] == 2 and not out["frozen"] and not out["suspect"]
    events = _get(s3, s3layout.events_key(PROVIDER, BOARD, DT))
    assert {e["event_type"] for e in events} == {"first-seen"}
    current = _get(s3, s3layout.current_jobs_key(PROVIDER, BOARD))
    assert {j["job_id"] for j in current} == {"j1", "j2"}
    # state persisted so tomorrow can diff against it
    _get(s3, s3layout.current_state_key(PROVIDER, BOARD))


def test_report_assembles_nonempty_from_s3(s3):
    """The bug we shipped: report rendered 0/0. Now it must reflect the real manifest + sentinels + events."""
    from src.differ import handler as differ
    from src.report import handler as report

    _seed_manifest(s3, sources=(SID,))
    _seed_collection(s3, [_job("j1"), _job("j2")])
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=DT, dt=DT, today=datetime.now(timezone.utc))

    out = report.handler({"mode": "assemble", "run_id": DT}, None)
    rj = _get(s3, s3layout.report_json_key(DT))

    assert rj["expected_sources"] == [SID]
    assert rj["succeeded_sources"] == [SID]
    assert rj["completeness_ratio"] == 1.0          # NOT 0/0
    assert out["expected"] == 1 and out["succeeded"] == 1
    # the two first-seen changes are actually in the report
    assert sum(1 for e in rj["events"] if e["event_type"] == "first-seen") == 2
    md = s3.get_object(Bucket=BUCKET, Key=s3layout.report_md_key(DT))["Body"].read().decode()
    assert "1/1 sources succeeded" in md


def test_report_ignores_success_sentinels_outside_current_manifest(s3):
    from src.differ import handler as differ
    from src.report import handler as report

    _seed_manifest(s3, sources=(SID,))
    _seed_collection(s3, [_job("j1")])
    _put(
        s3,
        s3layout.collect_sentinel_key(DT, "greenhouse", "retired-board"),
        {"run_id": DT, "source_id": "greenhouse:retired-board", "status": "SUCCESS"},
    )
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=DT, dt=DT, today=datetime.now(timezone.utc))

    out = report.handler({"mode": "assemble", "run_id": DT}, None)
    rj = _get(s3, s3layout.report_json_key(DT))

    assert rj["succeeded_sources"] == [SID]
    assert out["expected"] == 1 and out["succeeded"] == 1


def test_report_scores_and_links_current_jobs(s3):
    from src.differ import handler as differ
    from src.report import handler as report

    _seed_manifest(s3, sources=(SID,))
    _seed_collection(s3, [
        _job(
            "agent-1",
            title="Agentic AI Engineer",
            body="Build multi-agent LLM workflows with MCP, Python, AWS, orchestration, and evals.",
        )
    ])
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=DT, dt=DT, today=datetime.now(timezone.utc))

    out = report.handler({"mode": "assemble", "run_id": DT}, None)
    rj = _get(s3, s3layout.report_json_key(DT))
    md = s3.get_object(Bucket=BUCKET, Key=s3layout.report_md_key(DT))["Body"].read().decode()

    assert out["matches"] == 1
    assert rj["current_job_count"] == 1 and rj["matching_job_count"] == 1
    assert rj["top_matches"][0]["title"] == "Agentic AI Engineer"
    assert "https://job-boards.greenhouse.io/acme/jobs/agent-1" in md


def test_differ_preserves_authoritative_first_seen_in_current_jobs(s3):
    from src.differ import handler as differ

    day1 = "2026-08-01"
    day2 = "2026-08-02"
    _seed_collection(s3, [_job("j1")], snap="snap-1", run_id=day1, dt=day1)
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=day1, dt=day1,
                    today=datetime.now(timezone.utc))
    first_seen = _get(s3, s3layout.current_jobs_key(PROVIDER, BOARD))[0]["first_seen_at"]

    _seed_collection(s3, [_job("j1")], snap="snap-2", run_id=day2, dt=day2)
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=day2, dt=day2,
                    today=datetime.now(timezone.utc))
    current = _get(s3, s3layout.current_jobs_key(PROVIDER, BOARD))[0]

    assert current["first_seen_at"] == first_seen
    assert current["last_seen_at"] >= first_seen


def test_report_sends_digest_once(s3, monkeypatch):
    from src.differ import handler as differ
    from src.report import handler as report

    address = "brett@example.com"
    ses = boto3.client("ses", region_name="us-east-1")
    ses.verify_email_identity(EmailAddress=address)
    monkeypatch.setenv("SES_SENDER", address)
    monkeypatch.setenv("DIGEST_RECIPIENT", address)
    _seed_manifest(s3, sources=(SID,))
    _seed_collection(s3, [_job("j1")])
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id=DT, dt=DT, today=datetime.now(timezone.utc))

    first = report.handler({"mode": "assemble", "run_id": DT}, None)
    second = report.handler({"mode": "assemble", "run_id": DT}, None)

    assert first["digest_delivery"] == "sent"
    assert second["digest_delivery"] == "already-sent"
    marker = _get(s3, s3layout.digest_delivery_key(DT))
    assert marker["recipient"] == address and marker["message_id"]


def test_incomplete_when_a_source_lacks_sentinel(s3):
    """Manifest expects 2 sources but only 1 succeeded -> INCOMPLETE naming the missing one, never quiet."""
    from src.report import handler as report

    other = "greenhouse:beta"
    _seed_manifest(s3, sources=(SID, other))
    _seed_collection(s3, [_job("j1")])  # only acme succeeded
    report.handler({"mode": "assemble", "run_id": DT}, None)
    rj = _get(s3, s3layout.report_json_key(DT))

    assert rj["run_health"] == "INCOMPLETE"
    assert rj["incomplete_sources"] == [other]


def test_source_failure_never_marks_mass_removal(s3):
    """The core invariant, through the real glue: day1 SUCCESS(2) then day2 FETCH_FAILED must produce
    ZERO 'disappeared' events, keep current/ unchanged, and freeze state."""
    from src.differ import handler as differ

    day1 = datetime.now(timezone.utc)
    _seed_collection(s3, [_job("j1"), _job("j2")], status="SUCCESS", snap="snap-1")
    differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id="2026-08-01", dt="2026-08-01", today=day1)
    current_before = _get(s3, s3layout.current_jobs_key(PROVIDER, BOARD))

    # day 2: fetch failed, no normalized jobs written
    _put(s3, s3layout.source_status_key(PROVIDER, BOARD), _status("FETCH_FAILED", 0, "snap-2"))
    s3.delete_object(Bucket=BUCKET, Key=s3layout.normalized_key(PROVIDER, BOARD, "2026-08-02"))
    out = differ.run_diff(s3, BUCKET, PROVIDER, BOARD, run_id="2026-08-02", dt="2026-08-02",
                          today=day1)

    assert out["frozen"] is True
    events = _get(s3, s3layout.events_key(PROVIDER, BOARD, "2026-08-02"))
    assert all(e["event_type"] != "disappeared" for e in events)
    assert any(e["event_type"] == "source-fetch-failed" for e in events)
    # current/ must be untouched by a failed fetch
    current_after = _get(s3, s3layout.current_jobs_key(PROVIDER, BOARD))
    assert {j["job_id"] for j in current_after} == {j["job_id"] for j in current_before}


def test_no_run_when_manifest_missing(s3):
    """No manifest for the run_id -> NO-RUN (the scheduler/dispatcher never opened it), never quiet."""
    from src.report import handler as report

    report.handler({"mode": "assemble", "run_id": "2099-01-01"}, None)
    rj = _get(s3, s3layout.report_json_key("2099-01-01"))
    assert rj["run_health"] == "NO-RUN"
