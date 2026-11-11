"""Emit the durable-acceptance fault matrix as JSON, from the same code the regressions use.

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        project-factory/outputs/open-market-discovery/runs/\
20260925_publication_commit_boundary_and_verification_v1/scripts/p09_publication_boundary_matrix.py

Every boundary is one refused external `PutObject` inside the real discovery stage, with the feed
returning the posting once and nothing afterwards. The matrix is derived, not restated: the table
and the expectations come from `tests/test_publication_commit_boundary.py`, so this file cannot
report a boundary the regressions do not also enforce.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

from tests.test_discovery_to_report_integration import BUCKET, Harness  # noqa: E402
from tests.test_publication_commit_boundary import BOUNDARIES, exercise  # noqa: E402


def main() -> int:
    rows = []
    for label, factory, expect_accepted, expect_source in BOUNDARIES:
        with mock_aws():
            s3 = boto3.client("s3", region_name="us-east-1")
            s3.create_bucket(Bucket=BUCKET)
            sqs = boto3.client("sqs", region_name="us-east-1")
            queue_url = sqs.create_queue(QueueName="p09-matrix")["QueueUrl"]
            harness = Harness(s3, queue_url)
            harness.sqs = sqs
            result = exercise(harness, factory())
        rows.append({
            "boundary": label,
            "expected_durably_accepted": expect_accepted,
            "expected_recovery_source": expect_source,
            **result,
        })
    print(json.dumps({
        "scope": (
            "P09 working tree; real enumerate/collect/discovery/differ/report code with external "
            "AWS and HTTP mocked; one refused PutObject per row; the feed returns the posting once "
            "and nothing on any later attempt; no test-authored intermediate records"
        ),
        "fixture": "synthetic qualifying insurance-company role, not a real opening",
        "serial_execution": (
            "every row is a single scheduled writer doing read-modify-write on its own objects; "
            "no concurrent writer is exercised and no exactly-once claim under concurrency is made"
        ),
        "boundaries": rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
