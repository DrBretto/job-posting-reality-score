"""Exercise `scripts/inspect_discovery_integration.py` on reports the REAL stages produced.

A live acceptance check is worth nothing until it has been shown to give different answers to
situations that look identical from the outside. So this drives the real enumerate, collector,
discovery, differ and report stages through four rounds and runs the shipped inspection script,
unmodified, on each resulting `daily_report.json`:

  A. a registry-absent employer's fitting role   -> must read ACCEPTANCE_MET
  B. a genuine zero-fit discovery day            -> must read INTEGRATION_OK
  C. the consumer connection removed             -> must read MISSING_INGESTION
  D. an interrupted publication, nothing owed yet published -> must read PENDING_PUBLICATION
  E. a retained posting whose employer IS in the registry    -> must read INTEGRATION_OK

B and C are the pair that matters. Both produce a morning report with no discovered candidate, and
P07's proposed check could not tell them apart; one is a normal quiet day and the other is the
product being broken.

Every intermediate artifact is written by the production stage that owns it. This file supplies
provider bytes only. No AWS is contacted and nothing is deployed.

Usage: python p08_exercise_live_check.py <output-dir>
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from unittest.mock import patch

import boto3
from botocore.client import BaseClient
from moto import mock_aws

ROOT = pathlib.Path(__file__).resolve().parents[6]
sys.path.insert(0, str(ROOT))

from src.common import s3layout  # noqa: E402

from tests.test_discovery_to_report_integration import (  # noqa: E402
    BUCKET,
    EXCLUDED_BY_POLICY,
    UNREGISTERED_FIT,
    Harness,
    _single_page_fetcher,
)

SCRIPT = ROOT / "scripts/inspect_discovery_integration.py"
RUN_ID = "2026-09-25"


def _dump(out: pathlib.Path, name: str, payload) -> pathlib.Path:
    path = out / name
    path.write_text(json.dumps(payload, indent=2, default=str))
    return path


def _inspect(out: pathlib.Path, label: str, report, live, coverage) -> tuple[str, str]:
    report_path = _dump(out, f"{label}_daily_report.json", report)
    args = [sys.executable, str(SCRIPT), "--report", str(report_path),
            "--registry", str(ROOT / "config/companies.yaml")]
    if live is not None:
        args += ["--live", str(_dump(out, f"{label}_live_jobs.json", live))]
    if coverage is not None:
        args += ["--coverage", str(_dump(out, f"{label}_coverage.json", coverage))]
    proc = subprocess.run(args, capture_output=True, text=True, cwd=ROOT)
    verdict = next(
        (line.split(" ")[0] for line in proc.stdout.splitlines()
         if line[:1].isupper() and line.split(" ")[0].isupper() and "_" in line.split(" ")[0]),
        "NO_VERDICT",
    )
    return verdict, proc.stdout + proc.stderr


def _world():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    sqs = boto3.client("sqs", region_name="us-east-1")
    queue_url = sqs.create_queue(QueueName="jprs-p08-exercise")["QueueUrl"]
    harness = Harness(s3, queue_url)
    harness.sqs = sqs
    return harness


def _read(harness, key):
    import botocore.exceptions

    try:
        return json.loads(harness.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except botocore.exceptions.ClientError:
        return None


def _artifacts(harness):
    return (
        harness.saved_report(RUN_ID),
        _read(harness, s3layout.discovery_live_key("himalayas")),
        _read(harness, s3layout.discovery_coverage_key(RUN_ID)),
    )


def case_a(out):
    """A registry-absent employer's fitting role reaches the report."""
    with mock_aws():
        harness = _world()
        harness.enumerate_round(RUN_ID)
        harness.collect_monitored(RUN_ID)
        harness.discover(RUN_ID, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
        harness.diff_monitored(RUN_ID)
        harness.report(RUN_ID)
        return _inspect(out, "A_acceptance", *_artifacts(harness))


def case_b(out):
    """A genuine zero-fit day: the feed produced a posting the candidate policy excludes."""
    with mock_aws():
        harness = _world()
        harness.enumerate_round(RUN_ID)
        harness.collect_monitored(RUN_ID)
        harness.discover(RUN_ID, fetcher=_single_page_fetcher([EXCLUDED_BY_POLICY]))
        harness.diff_monitored(RUN_ID)
        harness.report(RUN_ID)
        return _inspect(out, "B_zero_fit", *_artifacts(harness))


def case_c(out):
    """The consumer connection removed, on inputs identical to case A."""
    with mock_aws():
        harness = _world()
        harness.enumerate_round(RUN_ID)
        harness.collect_monitored(RUN_ID)
        harness.discover(RUN_ID, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
        harness.diff_monitored(RUN_ID)
        # Exactly what P07 added, and nothing else, is disabled.
        with patch("src.common.s3layout.discovery_live_key",
                   return_value="discovery/live/absent.json"):
            harness.report(RUN_ID)
        return _inspect(out, "C_missing_ingestion", *_artifacts(harness))


def case_d(out):
    """An interrupted publication: the observation is owed and nothing is published yet."""
    original = BaseClient._make_api_call
    live_key = s3layout.discovery_live_key("himalayas")
    fired: list[str] = []

    def refuse_live_write(client, operation, parameters):
        if operation == "PutObject" and parameters.get("Key") == live_key and not fired:
            fired.append(live_key)
            raise TimeoutError("exercise-injected storage failure before live-view commit")
        return original(client, operation, parameters)

    with mock_aws():
        harness = _world()
        harness.enumerate_round(RUN_ID)
        harness.collect_monitored(RUN_ID)
        with patch.object(BaseClient, "_make_api_call", refuse_live_write):
            try:
                harness.discover(RUN_ID, fetcher=_single_page_fetcher([UNREGISTERED_FIT]))
            except TimeoutError:
                pass
        assert fired, "the injected failure never fired"
        harness.diff_monitored(RUN_ID)
        harness.report(RUN_ID)
        return _inspect(out, "D_pending", *_artifacts(harness))


def case_e(out):
    """A discovery posting whose employer IS already monitored.

    The control for the defect P07's review named in the thin-day check: a discovery source id differs
    from every ATS source id by construction, so a check comparing source ids would call this a
    previously unseen employer. It is Machinify, which is in `config/companies.yaml`. The verdict must
    therefore be INTEGRATION_OK — the integration works, and the open-market condition is NOT met.
    """
    monitored_employer = dict(UNREGISTERED_FIT)
    monitored_employer["companyName"] = "Machinify"
    monitored_employer["companySlug"] = "machinify"
    monitored_employer["guid"] = "https://himalayas.app/companies/machinify/jobs/internal-tools-2"
    monitored_employer["applicationLink"] = monitored_employer["guid"]
    with mock_aws():
        harness = _world()
        harness.enumerate_round(RUN_ID)
        harness.collect_monitored(RUN_ID)
        harness.discover(RUN_ID, fetcher=_single_page_fetcher([monitored_employer]))
        harness.diff_monitored(RUN_ID)
        harness.report(RUN_ID)
        return _inspect(out, "E_monitored_employer", *_artifacts(harness))


CASES = [
    ("A_acceptance", "registry-absent employer retained", "ACCEPTANCE_MET", case_a),
    ("B_zero_fit", "genuine zero-fit discovery day", "INTEGRATION_OK", case_b),
    ("C_missing_ingestion", "consumer connection removed", "MISSING_INGESTION", case_c),
    ("D_pending", "interrupted publication, nothing published", "PENDING_PUBLICATION", case_d),
    ("E_monitored_employer", "retained, but the employer is already monitored",
     "INTEGRATION_OK", case_e),
]


def main(argv: list[str]) -> int:
    out = pathlib.Path(argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    print(f"inspection script under test: {SCRIPT}")
    print(f"fixtures and full output written to: {out}")
    print()

    failures = 0
    for label, description, expected, runner in CASES:
        verdict, output = runner(out)
        (out / f"{label}_inspection.txt").write_text(output)
        ok = verdict == expected
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {label}: {description}")
        print(f"      expected {expected}, got {verdict}")
    print()
    if failures:
        print(f"LIVE_CHECK_NOT_DISCRIMINATING — {failures} case(s) gave the wrong verdict")
        return 1
    print("LIVE_CHECK_DISCRIMINATES — every situation is told apart on real report output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
