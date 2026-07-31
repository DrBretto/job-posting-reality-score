"""JPRS collector — SQS-triggered, v2 (the P3 redrive "fix").

The v1 handler raised on ANY fetch error, so a bad/unknown board (404) failed forever -> DLQ.
v2 distinguishes PERMANENT failure from TRANSIENT failure:
  - 404 (board doesn't exist)  -> log + skip, do NOT raise. A permanently-bad message should not
    loop through the DLQ forever; we consume it so the queue drains.
  - any other HTTP/URL error   -> raise, so genuinely transient failures still retry -> DLQ.
That distinction is the interview answer to "how do you handle poison vs transient failures."
After deploying this, you REDRIVE the DLQ: the parked 404 message flows back, v2 handles it
gracefully, and the DLQ drains instead of re-filling.
"""

import datetime
import gzip
import json
import os
import urllib.error
import urllib.request
import uuid

import boto3

s3 = boto3.client("s3")
BUCKET = os.environ["JPRS_BUCKET"]


def _collect_one(provider, board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "jprs-collector/0.1 (personal job radar)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
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
    return key, job_count


def handler(event, context):
    for record in event["Records"]:
        received = record.get("attributes", {}).get("ApproximateReceiveCount", "?")
        msg = json.loads(record["body"])
        provider = msg.get("provider", "greenhouse")
        board = msg["board_token"]
        print(f"processing board={board} (ApproximateReceiveCount={received})")
        try:
            key, n = _collect_one(provider, board)
            print(f"OK board={board} jobs={n} -> {key}")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # PERMANENT: unknown board. Don't raise -> message is consumed, won't re-DLQ.
                print(f"SKIP board={board}: 404 not found (permanent bad input, dropping)")
                continue
            raise  # TRANSIENT (5xx, throttle): let SQS retry -> DLQ
    return {"ok": True}
