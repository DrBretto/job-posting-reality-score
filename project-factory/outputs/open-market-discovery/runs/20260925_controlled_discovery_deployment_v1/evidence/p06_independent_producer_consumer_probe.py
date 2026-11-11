from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import boto3
from moto import mock_aws

from src.common import s3layout
from src.common.connectors import FetchResult
from src.discovery.handler import handler as discover
from src.enumerate.handler import handler as enumerate_sources
from src.report.handler import handler as report


def fixture_fetch(provider, token, url):
    now = datetime.now(timezone.utc)
    description = (
        "Responsibilities: build Python backend services, TypeScript applications, internal tools, "
        "AWS Lambda integrations and LLM evaluation workflows. Remote throughout the United States. "
        "Interview process: two live video calls with the team."
    )
    payload = {
        "jobs": [{
            "title": "Senior Software Engineer", "companyName": "Unlisted Employer Probe",
            "companySlug": "unlisted-employer-probe", "excerpt": description,
            "description": description, "employmentType": "Full Time",
            "applicationLink": "https://himalayas.app/companies/probe/jobs/applied-engineer",
            "guid": "https://himalayas.app/companies/probe/jobs/applied-engineer",
            "locationRestrictions": "['United States']",
            "pubDate": str(int((now - timedelta(hours=2)).timestamp())),
        }],
        "nextCursor": None, "totalCount": 1,
    }
    return FetchResult(
        raw_bytes=json.dumps(payload).encode(), http_status=200, error_class=None,
        endpoint_url=url, request_at=now, response_at=now,
    )


def main():
    bucket = "jprs-p06-independent-probe"
    run_id = datetime.now(timezone.utc).date().isoformat()
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=bucket)
        sqs = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs.create_queue(QueueName="jprs-probe-collect")["QueueUrl"]
        env = {
            "AWS_DEFAULT_REGION": "us-east-1", "JPRS_BUCKET": bucket,
            "JPRS_COLLECT_QUEUE_URL": queue_url, "JPRS_COMPANIES_SSM": "",
            "JPRS_COMPANIES_YAML": "config/companies.yaml",
            "JPRS_DISCOVERY_YAML": "config/discovery_sources.yaml",
            "JPRS_DISCOVERY_PROVIDERS": "himalayas", "JPRS_SECRETS_SSM_PREFIX": "",
            "SES_SENDER": "", "DIGEST_RECIPIENT": "",
        }
        with patch.dict(os.environ, env):
            enumerate_sources({"run_id": run_id}, None)
            with patch("src.discovery.handler._live_fetcher", side_effect=fixture_fetch):
                discovered = discover({"run_id": run_id, "dt": run_id}, None)
            report({"run_id": run_id, "dt": run_id}, None)

        def read(key):
            return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())

        manifest = read(s3layout.run_manifest_key(run_id))
        output = read(s3layout.report_json_key(run_id))
        objects = s3.list_objects_v2(Bucket=bucket).get("Contents", [])
        normalized = [item["Key"] for item in objects
                      if item["Key"].startswith("normalized/") and "provider=himalayas/" in item["Key"]]
        jobs = [job for key in normalized for job in read(key)]
        rows = output["complete_candidate_list"]
        print(json.dumps({
            "scope": "real enumerate, discovery persistence and report handlers; mocked AWS/HTTP; no hand-written manifest, normalized, current or report rows",
            "limit": "monitored-board collection is not simulated; this isolates the discovery producer-to-report edge, not the entire state machine",
            "registry_sources": len(manifest["expected_sources"]),
            "expected_discovery_sources": manifest["expected_discovery_sources"],
            "discovered": discovered["jobs_discovered"],
            "normalized_job_ids": [job["job_id"] for job in jobs],
            "current_keys": [item["Key"] for item in objects if item["Key"].startswith("current/")],
            "candidate_rows": len(rows),
            "discovery_candidate_ids": [row["job_id"] for row in rows if row["job_id"].startswith("himalayas:")],
        }, indent=2))


if __name__ == "__main__":
    main()
