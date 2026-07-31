"""JPRS single-company collector for Step Functions (P5).

Direct-invoke (NOT SQS-wrapped): the event IS one company, e.g.
{"provider": "greenhouse", "board_token": "stripe"}. Raises on failure so Step Functions sees a
failed Task and its Retry/Catch can act. Deploy this as a SEPARATE Lambda `jprs-collect-one` so the
SQS-driven `jprs-collector` keeps working untouched. Reuses the same execution role (it already has
s3:PutObject on raw/*).
"""

import datetime
import gzip
import json
import os
import urllib.request
import uuid

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["JPRS_BUCKET"]


def handler(event, context):
    provider = event.get("provider", "greenhouse")
    board = event["board_token"]

    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "jprs-collector/0.1 (personal job radar)"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # bad board -> 404 -> raises -> SFN Task fails
        raw = resp.read()

    now = datetime.datetime.now(datetime.timezone.utc)
    dt = now.strftime("%Y-%m-%d")
    snap_id = uuid.uuid4().hex
    key = f"raw/provider={provider}/board={board}/dt={dt}/snapshot={snap_id}.json.gz"
    s3.put_object(
        Bucket=BUCKET, Key=key, Body=gzip.compress(raw),
        ContentType="application/json", ContentEncoding="gzip",
    )
    try:
        job_count = len(json.loads(raw).get("jobs", []))
    except Exception:
        job_count = None
    return {"ok": True, "board": board, "job_count": job_count, "snapshot_key": key}
