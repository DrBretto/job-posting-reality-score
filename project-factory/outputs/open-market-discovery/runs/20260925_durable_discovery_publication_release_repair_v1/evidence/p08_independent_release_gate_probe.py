"""Negative controls for P08 validation helpers, not production data or cloud operations."""

import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


root = Path.cwd()
run = root / "project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1"
spec = importlib.util.spec_from_file_location("baseline_verifier", run / "evidence/p08_verify_rollback_baseline.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
expected, templates = verifier._recorded_hashes(root)
with tarfile.open(run / "evidence/p06_baseline_src.tar.gz") as archive:
    archived = {
        member.name: hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        for member in archive.getmembers() if member.isfile()
    }
baseline = {
    "expected_files": len(expected),
    "archived_files": len(archived),
    "missing_or_different": [name for name, digest in expected.items() if archived.get(name) != digest],
    "unexpected_files": sorted(set(archived) - set(expected)),
    "current_template_config_match_p06": all(
        hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
        for name, digest in templates.items()
    ),
}

with tempfile.TemporaryDirectory(prefix="jprs-p08-gate-probe-") as temporary:
    work = Path(temporary)
    old = work / "old"
    new = work / "new"
    for build in (old, new):
        (build / "DiscoveryFunction/src").mkdir(parents=True)
        (build / "DiscoveryFunction/src/control.py").write_text("UNCHANGED = True\n")
        (build / "template.yaml").write_text("Resources:\n  ExampleRole:\n    Type: AWS::IAM::Role\n    Properties:\n      MaxSessionDuration: 3600\n")
    (new / "template.yaml").write_text((old / "template.yaml").read_text().replace("3600", "7200"))
    package = subprocess.run(
        [sys.executable, str(run / "evidence/p08_package_scope.py"), str(old), str(new), str(root)],
        capture_output=True, text=True,
    )

    fixtures = run / "evidence/live_check_fixtures"
    report = json.loads((fixtures / "A_acceptance_daily_report.json").read_text())
    live = json.loads((fixtures / "A_acceptance_live_jobs.json").read_text())
    first_id = next(iter(live["jobs"]))
    missing_id = first_id + "-unconsumed-control"
    missing = json.loads(json.dumps(live["jobs"][first_id]))
    missing["job"]["job_id"] = missing_id
    missing["job"]["title"] = "Synthetic control deliberately absent from report"
    live["jobs"][missing_id] = missing
    live_path = work / "two_stored_jobs.json"
    report_path = work / "one_consumed_job.json"
    live_path.write_text(json.dumps(live))
    report_path.write_text(json.dumps(report))
    inspection = subprocess.run(
        [sys.executable, str(root / "scripts/inspect_discovery_integration.py"),
         "--live", str(live_path), "--report", str(report_path),
         "--registry", str(root / "config/companies.yaml")],
        capture_output=True, text=True,
    )
    result = {
        "scope": "Local negative controls for validation helpers only; synthetic altered fixtures, not production/runtime failure evidence",
        "baseline_archive_check": baseline,
        "changed_iam_template_control": {"exit": package.returncode, "output": package.stdout + package.stderr},
        "stored_identity_absent_from_report_control": {
            "omitted_id": missing_id,
            "same_employer_as_consumed_job": True,
            "id_exists_in_report": missing_id in json.dumps(report),
            "exit": inspection.returncode,
            "output": inspection.stdout + inspection.stderr,
        },
    }
    print(json.dumps(result, indent=2))
