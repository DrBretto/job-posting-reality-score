import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import boto3
from botocore.client import BaseClient
from moto import mock_aws

from src.common import s3layout


root = Path.cwd()
spec = importlib.util.spec_from_file_location(
    "p07_harness", root / "tests/test_discovery_to_report_integration.py"
)
harness_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness_module)


def read_json(storage, key):
    return json.loads(storage.get_object(Bucket=harness_module.BUCKET, Key=key)["Body"].read())


def run_probe(interrupt):
    with mock_aws():
        storage = boto3.client("s3", region_name="us-east-1")
        storage.create_bucket(Bucket=harness_module.BUCKET)
        queue = boto3.client("sqs", region_name="us-east-1")
        queue_url = queue.create_queue(QueueName="p07-independent-review")["QueueUrl"]
        harness = harness_module.Harness(storage, queue_url)
        harness.sqs = queue
        first_run = "2026-09-25"
        next_run = "2026-09-26"
        harness.enumerate_round(first_run)
        harness.collect_monitored(first_run)
        harness.diff_monitored(first_run)
        original_call = BaseClient._make_api_call
        injected = []

        def interrupt_live_write(client, operation, parameters):
            if (
                interrupt and operation == "PutObject"
                and parameters.get("Key") == s3layout.discovery_live_key("himalayas")
                and not injected
            ):
                injected.append(parameters["Key"])
                raise TimeoutError("review-injected storage failure before live-view commit")
            return original_call(client, operation, parameters)

        failure = None
        with patch.object(BaseClient, "_make_api_call", interrupt_live_write):
            try:
                harness.discover(
                    first_run,
                    fetcher=harness_module._single_page_fetcher([harness_module.UNREGISTERED_FIT]),
                )
            except TimeoutError as error:
                failure = str(error)
        if interrupt:
            assert injected and failure
        normalized_before = harness.normalized_job_ids()
        first_coverage = read_json(storage, s3layout.discovery_coverage_key(first_run))
        state_before_retry = read_json(storage, s3layout.discovery_state_key())
        harness.discover(first_run, fetcher=harness_module._single_page_fetcher([]))
        harness.report(first_run)
        retry_report = harness.saved_report(first_run)
        harness_module._round(
            harness, next_run, fetcher=harness_module._single_page_fetcher([])
        )
        following_report = harness.saved_report(next_run)
        return {
            "scope": "real P07 producers/consumers with external AWS/HTTP mocked; one external storage failure and a changed feed window; no test-created intermediates",
            "fixture": "synthetic qualifying insurance-company role, not a real opening",
            "injected_failure": failure,
            "normalized_before_interruption": normalized_before,
            "source_success_persisted_before_live_commit": first_coverage["discovery_succeeded"],
            "traversal_state_persisted_before_live_commit": bool(state_before_retry),
            "live_job_ids_after_same_run_retry": harness.live_view_ids("himalayas"),
            "same_run_retry_discovery_candidates": [
                row["job_id"] for row in retry_report["complete_candidate_list"]
                if row["source_kind"] == "DISCOVERY_FEED"
            ],
            "following_run_discovery_candidates": [
                row["job_id"] for row in following_report["complete_candidate_list"]
                if row["source_kind"] == "DISCOVERY_FEED"
            ],
            "retained_raw_snapshot_count": len(harness.keys("raw/provider=himalayas/")),
        }


if __name__ == "__main__":
    print(json.dumps({
        "control": run_probe(False),
        "interrupted": run_probe(True),
    }, indent=2))
