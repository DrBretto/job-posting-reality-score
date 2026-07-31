"""JPRS collector — SQS-triggered version (P3).

Now the Lambda is driven by an SQS queue instead of a manual test event. Each SQS message body is
a JSON job like {"provider": "greenhouse", "board_token": "stripe"}. If processing a message RAISES,
the function fails, SQS makes the message visible again after the visibility timeout, redelivers it
up to maxReceiveCount, and then routes it to the DLQ. That poison -> DLQ -> redrive path is the P3
refresher. Function name stays `handler` so the Lambda Handler setting (lambda_function.handler) is
unchanged.
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


def _collect_one(provider, board):
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    req = urllib.request.Request(url, headers={"User-Agent": "jprs-collector/0.1 (personal job radar)"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # a bad board_token 404s here -> raises
        raw = resp.read()

    now = datetime.datetime.now(datetime.timezone.utc)
    dt = now.strftime("%Y-%m-%d")
    snap_id = uuid.uuid4().hex
    key = f"raw/provider={provider}/board={board}/dt={dt}/snapshot={snap_id}.json.gz"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=gzip.compress(raw),
        ContentType="application/json",
        ContentEncoding="gzip",
    )
    try:
        job_count = len(json.loads(raw).get("jobs", []))
    except Exception:
        job_count = None
    return key, job_count


def handler(event, context):
    # SQS delivers a batch: event["Records"]. With batch size 1 that's one message per invoke.
    for record in event["Records"]:
        received = record.get("attributes", {}).get("ApproximateReceiveCount", "?")
        msg = json.loads(record["body"])
        provider = msg.get("provider", "greenhouse")
        board = msg["board_token"]
        print(f"processing board={board} (ApproximateReceiveCount={received})")
        key, n = _collect_one(provider, board)  # raises on failure -> message retried -> DLQ
        print(f"OK board={board} jobs={n} -> {key}")
    return {"ok": True}
