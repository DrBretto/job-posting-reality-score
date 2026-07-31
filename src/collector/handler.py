"""Collector Lambda — SQS-triggered (V1, replaces the P2/P3 scratch handlers).

Per SQS message: run the connector, then write (in this order, so evidence exists even if a later
step fails):
  1. raw/       — immutable exact response bytes (gzipped) + SourceReceipt  (WRITTEN BEFORE PARSE)
  2. normalized/— CanonicalJob set  (collector-owns per ADR-24)
  3. status/    — _source_status.json (snapshot status; drives "did collectors run")
  4. status/    — per-task SUCCESS sentinel (ONLY on SUCCESS/EMPTY_SUCCESS, after raw durable)

M4: the collector writes ONLY status/ + raw/ + normalized/. It never touches current/ (differ-owned),
so a prefix-scoped `current/*` grant is not needed and the live-job set is out of its blast radius.

Failure handling (RELIABILITY §4): the connector labels the snapshot; the handler decides retry.
  - permanent 404 (unknown board)      -> log + SKIP (consume the message; do not re-DLQ forever)
  - transient FETCH_FAILED (timeout/5xx/429) -> record in batchItemFailures -> SQS redelivers -> DLQ
  - SUCCESS/EMPTY_SUCCESS/PARTIAL       -> processed; snapshot written; message consumed
`ReportBatchItemFailures` shape is used so one bad record cannot force the whole batch to redeliver.
"""

from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timezone

from src.common import s3layout
from src.common.connectors import get_connector
from src.common.models import SnapshotStatus


def _prior_job_count(s3, bucket, provider, board):  # pragma: no cover - AWS glue
    import botocore.exceptions

    try:
        obj = s3.get_object(Bucket=bucket, Key=s3layout.source_status_key(provider, board))
        return json.loads(obj["Body"].read()).get("job_count_observed")
    except botocore.exceptions.ClientError:
        return None


def collect_one(s3, bucket: str, msg: dict) -> dict:  # pragma: no cover - network + AWS glue
    """Fetch + persist one task. Raises on transient failure so SQS retries; returns dict otherwise."""
    provider = msg["provider"]
    board = msg["board_token"]
    run_id = msg.get("run_id", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    connector = get_connector(provider)

    fr = connector.fetch_raw(board)
    prior = _prior_job_count(s3, bucket, provider, board)
    snapshot, jobs = connector.build_snapshot(board, fr, prior_job_count=prior)
    dt = snapshot.fetched_at.strftime("%Y-%m-%d")

    # 1. raw + receipt FIRST (court-of-record), even on failure
    if fr.raw_bytes is not None:
        raw_key = s3layout.raw_snapshot_key(provider, board, dt, snapshot.snapshot_id)
        s3.put_object(
            Bucket=bucket, Key=raw_key, Body=gzip.compress(fr.raw_bytes),
            ContentType="application/json", ContentEncoding="gzip",
        )
        snapshot.raw_object_key = raw_key
    if snapshot.request_receipt is not None:
        s3.put_object(
            Bucket=bucket,
            Key=s3layout.raw_receipt_key(provider, board, dt, snapshot.snapshot_id),
            Body=snapshot.request_receipt.model_dump_json().encode(),
            ContentType="application/json",
        )

    # permanent 404 -> skip (consume message), record status, no raise, no sentinel
    if snapshot.status == SnapshotStatus.FETCH_FAILED and (fr.error_class == "http_404"):
        _write_status(s3, bucket, provider, board, snapshot)
        return {"status": snapshot.status.value, "skipped_permanent": True, "board": board}

    # transient failure -> raise so SQS redelivers toward the DLQ
    if snapshot.status == SnapshotStatus.FETCH_FAILED:
        _write_status(s3, bucket, provider, board, snapshot)
        raise RuntimeError(f"transient fetch failure board={board} class={fr.error_class}")

    # 2. normalized
    s3.put_object(
        Bucket=bucket, Key=s3layout.normalized_key(provider, board, dt),
        Body=json.dumps([j.model_dump(mode="json") for j in jobs], default=str).encode(),
        ContentType="application/json",
    )
    # 3. status
    _write_status(s3, bucket, provider, board, snapshot)
    # 4. SUCCESS sentinel (only for trusted successes, after raw durable)
    if snapshot.status in (SnapshotStatus.SUCCESS, SnapshotStatus.EMPTY_SUCCESS):
        s3.put_object(
            Bucket=bucket, Key=s3layout.collect_sentinel_key(run_id, provider, board),
            Body=json.dumps({
                "run_id": run_id, "source_id": snapshot.source_id,
                "snapshot_id": snapshot.snapshot_id, "status": snapshot.status.value,
                "job_count": snapshot.job_count_observed,
                "written_at": datetime.now(timezone.utc).isoformat(),
            }).encode(),
            ContentType="application/json",
        )
    return {"status": snapshot.status.value, "board": board, "jobs": snapshot.job_count_observed}


def _write_status(s3, bucket, provider, board, snapshot):  # pragma: no cover - AWS glue
    s3.put_object(
        Bucket=bucket, Key=s3layout.source_status_key(provider, board),
        Body=json.dumps({
            "source_id": snapshot.source_id,
            "status": snapshot.status.value,
            "snapshot_id": snapshot.snapshot_id,
            "fetched_at": snapshot.fetched_at.isoformat(),
            "job_count_observed": snapshot.job_count_observed,
            "http_status": snapshot.http_status,
            "error_class": snapshot.error_class,
        }, default=str).encode(),
        ContentType="application/json",
    )


def handler(event, context):  # pragma: no cover - AWS glue
    import boto3

    bucket = os.environ["JPRS_BUCKET"]
    s3 = boto3.client("s3")
    failures = []
    for record in event.get("Records", []):
        message_id = record.get("messageId")
        try:
            msg = json.loads(record["body"])
            result = collect_one(s3, bucket, msg)
            print(json.dumps({"collector": "ok", "message_id": message_id, **result}))
        except Exception as exc:  # noqa: BLE001 - per-record isolation for partial batch response
            print(json.dumps({"collector": "fail", "message_id": message_id, "error": str(exc)}))
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
