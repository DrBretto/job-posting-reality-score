"""Emit the P07 stage trace as a standalone artifact.

Reuses the acceptance harness in `tests/test_discovery_to_report_integration.py` rather than
re-implementing it, so the trace below describes exactly the code path the suite asserts on. Runs
the full production order — enumerate, collector, discovery, differ, report — against mocked S3, SQS
and HTTP, and writes the per-stage census of identities and counts.

Reproduce from the repository root:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. .venv/bin/python \\
      project-factory/outputs/open-market-discovery/runs/20260925_discovery_to_report_integration_v1/evidence/p07_stage_trace_probe.py
"""

from __future__ import annotations

import json

import boto3
from moto import mock_aws

from tests.test_discovery_to_report_integration import (
    BUCKET,
    EXCLUDED_BY_POLICY,
    UNREGISTERED_FIT,
    Harness,
    _round,
    _single_page_fetcher,
)


def main() -> None:
    run_id = "2026-09-25"
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        sqs = boto3.client("sqs", region_name="us-east-1")
        harness = Harness(s3, sqs.create_queue(QueueName="jprs-p07-trace")["QueueUrl"])
        harness.sqs = sqs

        _round(
            harness, run_id,
            fetcher=_single_page_fetcher([UNREGISTERED_FIT, EXCLUDED_BY_POLICY]),
        )
        entry = harness.record_stage_trace("acceptance_round", run_id)
        report = harness.saved_report(run_id)

        payload = {
            "scope": (
                "real enumerate, collector, discovery, differ and report handlers against mocked "
                "S3/SQS/HTTP; no manifest, expected_sources, normalized, current, screening, "
                "scorecard or report row is written by this script or by the harness"
            ),
            "fixture_provenance": {
                "UNREGISTERED_FIT": "synthetic fit control; proves pipeline behavior, not a live opening",
                "EXCLUDED_BY_POLICY": "synthetic exclusion control",
                "MONITORED_PAYLOAD": "synthetic monitored-board control, present so a discovery-only "
                                     "result cannot hide a monitored-path regression",
            },
            "s3_prefixes_written": sorted({key.split("/", 1)[0] for key in harness.keys("")}),
            "stage_trace": entry,
            "coverage_statements": report["coverage"]["inaccessible"],
            "health_axes": report["health_axes"],
            "timing": report["timing"],
        }
        print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
