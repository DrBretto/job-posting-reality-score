"""JPRS collector Lambda — fetch one job board, write one immutable snapshot to S3.

Thin, dependency-free handler (stdlib + boto3, both in the Lambda runtime) so it pastes
straight into the inline console editor. This is the P2 refresher target: the interesting part
is the EXECUTION ROLE and the AccessDenied you'll deliberately hit, not this code.
"""

import datetime
import gzip
import json
import os
import urllib.request
import uuid

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["JPRS_BUCKET"]  # set as a Lambda env var = your bucket name


def handler(event, context):
    provider = event.get("provider", "greenhouse")
    board = event["board_token"]  # passed in the test event, e.g. "greenhouse" or a real company slug

    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "jprs-collector/0.1 (personal job radar)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()  # exact bytes from the ATS

    now = datetime.datetime.now(datetime.timezone.utc)
    dt = now.strftime("%Y-%m-%d")
    snap_id = uuid.uuid4().hex

    # immutable raw snapshot (unique key => never overwrites a prior snapshot)
    snapshot_key = f"raw/provider={provider}/board={board}/dt={dt}/snapshot={snap_id}.json.gz"
    s3.put_object(
        Bucket=BUCKET,
        Key=snapshot_key,
        Body=gzip.compress(raw),
        ContentType="application/json",
        ContentEncoding="gzip",
    )

    # a small receipt so "did the collector run" is a positive fact, not an inference
    try:
        job_count = len(json.loads(raw).get("jobs", []))
    except Exception:
        job_count = None
    receipt_key = f"raw/provider={provider}/board={board}/dt={dt}/receipt={snap_id}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=receipt_key,
        Body=json.dumps({
            "provider": provider,
            "board": board,
            "fetched_at": now.isoformat(),
            "status": "SUCCESS",
            "job_count": job_count,
            "snapshot_key": snapshot_key,
            "http_bytes": len(raw),
        }).encode(),
        ContentType="application/json",
    )

    return {"ok": True, "snapshot_key": snapshot_key, "job_count": job_count}
