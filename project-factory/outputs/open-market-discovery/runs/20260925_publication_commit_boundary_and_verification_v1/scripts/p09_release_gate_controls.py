"""Negative and positive controls for the P09 release checkers. Local fixtures only, no AWS call.

Every fixture here is deliberately altered on disk in a scratch directory to test a CHECKER. None
of it is evidence of a production infrastructure change, a real IAM edit, or a posting that
actually went missing in production.

Run from the repository root:

    PYTHONDONTWRITEBYTECODE=1 .venv/bin/python \
        project-factory/outputs/open-market-discovery/runs/\
20260925_publication_commit_boundary_and_verification_v1/scripts/p09_release_gate_controls.py

Each control names the condition it creates and records the checker's verdict and exit code. The
expected verdicts are NOT printed alongside: a fresh verifier should read the conditions, decide
what each one ought to return, and compare.
"""

import json
import pathlib
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT = pathlib.Path.cwd()
P08 = ROOT / (
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_durable_discovery_publication_release_repair_v1"
)
ARCHIVE = P08 / "evidence/p06_baseline_src.tar.gz"
FIXTURES = P08 / "evidence/live_check_fixtures"

CHANGE_SET = ROOT / "scripts/check_release_change_set.py"
BASELINE = ROOT / "scripts/verify_rollback_baseline.py"
INSPECTOR = ROOT / "scripts/inspect_discovery_integration.py"

IAM_TEMPLATE = (
    "Resources:\n"
    "  ExampleRole:\n"
    "    Type: AWS::IAM::Role\n"
    "    Properties:\n"
    "      MaxSessionDuration: 3600\n"
)


def _run(argv: list[str]) -> dict:
    done = subprocess.run([sys.executable, *argv], capture_output=True, text=True)
    output = done.stdout + done.stderr
    verdict = next(
        (line.split(" —")[0].split(" -")[0].strip()
         for line in reversed(output.splitlines())
         if line[:1].isupper() and line.split(" ")[0].isupper() and "_" in line.split(" ")[0]),
        None,
    )
    return {"exit": done.returncode, "verdict": verdict, "output": output}


def _package_pair(work: pathlib.Path, name: str, *, mutate_template=None,
                  mutate_code: bool = False, extra_function: bool = False) -> tuple[str, str]:
    old = work / name / "old"
    new = work / name / "new"
    for build in (old, new):
        (build / "DiscoveryFunction/src").mkdir(parents=True)
        (build / "DiscoveryFunction/src/control.py").write_text("UNCHANGED = True\n")
        (build / "template.yaml").write_text(IAM_TEMPLATE)
    if mutate_template:
        (new / "template.yaml").write_text(mutate_template(IAM_TEMPLATE))
    if mutate_code:
        (new / "DiscoveryFunction/src/control.py").write_text("UNCHANGED = False\n")
    if extra_function:
        (new / "ReportFunction/src").mkdir(parents=True)
        (new / "ReportFunction/src/control.py").write_text("NEW = True\n")
    return str(old), str(new)


def main() -> int:
    controls: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="jprs-p09-controls-") as temporary:
        work = pathlib.Path(temporary)

        # ---- change-set gate -------------------------------------------------------------------
        old, new = _package_pair(
            work, "iam", mutate_template=lambda t: t.replace("3600", "7200")
        )
        controls["built_template_iam_property_changed"] = {
            "condition": "identical application files; the built template's IAM role "
                         "MaxSessionDuration moves from 3600 to 7200",
            **_run([str(CHANGE_SET), "--baseline", old, "--candidate", new, "--repo", str(ROOT)]),
        }

        old, new = _package_pair(work, "codeonly", mutate_code=True)
        controls["genuine_code_only_change"] = {
            "condition": "one packaged application module differs; templates identical",
            **_run([str(CHANGE_SET), "--baseline", old, "--candidate", new, "--repo", str(ROOT)]),
        }

        old, new = _package_pair(work, "added", extra_function=True)
        controls["function_added_to_the_build"] = {
            "condition": "a function directory present in the candidate build and not the baseline",
            **_run([str(CHANGE_SET), "--baseline", old, "--candidate", new, "--repo", str(ROOT)]),
        }

        old, new = _package_pair(work, "codeuri")
        (work / "codeuri/old/template.yaml").write_text(
            "Resources:\n  Fn:\n    Type: AWS::Serverless::Function\n"
            "    Properties:\n      CodeUri: /build/aaa/DiscoveryFunction\n      MemorySize: 512\n"
        )
        (work / "codeuri/new/template.yaml").write_text(
            "Resources:\n  Fn:\n    Type: AWS::Serverless::Function\n"
            "    Properties:\n      CodeUri: /build/bbb/DiscoveryFunction\n      MemorySize: 512\n"
        )
        controls["only_the_build_path_codeuri_differs"] = {
            "condition": "the two built templates differ only in CodeUri, as SAM rewrites it per "
                         "build directory",
            **_run([str(CHANGE_SET), "--baseline", old, "--candidate", new, "--repo", str(ROOT)]),
        }

        controls["baseline_build_directory_absent"] = {
            "condition": "the baseline build directory does not exist on this machine",
            **_run([str(CHANGE_SET), "--baseline", str(work / "never-existed"),
                    "--candidate", new, "--repo", str(ROOT)]),
        }

        empty_repo = work / "repo-without-the-record"
        empty_repo.mkdir()
        controls["recorded_p06_identity_unavailable"] = {
            "condition": "the repository root supplied carries no recorded P06 build identity",
            **_run([str(CHANGE_SET), "--baseline", old, "--candidate", new,
                    "--repo", str(empty_repo)]),
        }

        # ---- rollback baseline ------------------------------------------------------------------
        controls["archive_is_the_real_p06_baseline"] = {
            "condition": "the archived P06 source tree, unmodified",
            **_run([str(BASELINE), "--archive", str(ARCHIVE), "--repo", str(ROOT)]),
        }

        corrupt = work / "corrupt.tar.gz"
        raw = bytearray(ARCHIVE.read_bytes())
        raw[len(raw) // 2] ^= 0xFF
        corrupt.write_bytes(bytes(raw))
        controls["archive_bytes_corrupted"] = {
            "condition": "one byte in the middle of the gzip stream is flipped",
            **_run([str(BASELINE), "--archive", str(corrupt), "--repo", str(ROOT)]),
        }

        tampered = work / "tampered.tar.gz"
        extracted = work / "tampered-src"
        with tarfile.open(ARCHIVE) as tar:
            tar.extractall(extracted, filter="data")
        target = extracted / "src/discovery/handler.py"
        target.write_text(target.read_text() + "\n# rollback tamper control\n")
        with tarfile.open(tampered, "w:gz") as tar:
            tar.add(extracted / "src", arcname="src")
        controls["archive_source_file_modified"] = {
            "condition": "one recorded module in the archive no longer matches its P06 hash",
            **_run([str(BASELINE), "--archive", str(tampered), "--repo", str(ROOT)]),
        }

        smuggled = work / "smuggled.tar.gz"
        extra = extracted / "src/discovery/extra_module.py"
        target.write_text(target.read_text().replace("\n# rollback tamper control\n", ""))
        extra.write_text("SMUGGLED = True\n")
        with tarfile.open(smuggled, "w:gz") as tar:
            tar.add(extracted / "src", arcname="src")
        controls["archive_carries_unrecorded_executable_source"] = {
            "condition": "the archive contains a .py module P06 never recorded",
            **_run([str(BASELINE), "--archive", str(smuggled), "--repo", str(ROOT)]),
        }
        extra.unlink()

        controls["restore_into_the_working_tree_src"] = {
            "condition": "a restore is requested directly into the repository's own src/",
            **_run([str(BASELINE), "--archive", str(ARCHIVE), "--repo", str(ROOT),
                    "--restore-into", str(ROOT / "src")]),
        }

        scratch_restore = work / "scratch-restore"
        controls["restore_into_a_scratch_directory"] = {
            "condition": "a restore into an empty scratch directory outside the repository",
            **_run([str(BASELINE), "--archive", str(ARCHIVE), "--repo", str(ROOT),
                    "--restore-into", str(scratch_restore)]),
        }
        restored = sorted(
            str(p.relative_to(scratch_restore))
            for p in scratch_restore.rglob("*.py")
        ) if scratch_restore.exists() else []
        controls["restore_into_a_scratch_directory"]["restored_module_count"] = len(restored)
        controls["restore_into_a_scratch_directory"]["working_tree_untouched"] = (
            _run([str(BASELINE), "--archive", str(ARCHIVE), "--repo", str(ROOT)])["exit"] == 0
        )

        # ---- per-identity report reconciliation ---------------------------------------------------
        controls.update(_inspection_controls(work))

    print(json.dumps({
        "scope": (
            "Local negative and positive controls for the P09 release checkers. Every fixture is a "
            "deliberately altered local copy; none of it is production evidence, an actual IAM "
            "edit, or a posting that went missing in production. No AWS call is made."
        ),
        "controls": controls,
    }, indent=2))
    return 0


def _inspection_controls(work: pathlib.Path) -> dict:
    """Report/live-view pairs that separate a real gap from an honest zero."""
    base_report = json.loads((FIXTURES / "A_acceptance_daily_report.json").read_text())
    base_live = json.loads((FIXTURES / "A_acceptance_live_jobs.json").read_text())
    consumed_id = next(iter(base_live["jobs"]))

    # The P08 fixtures predate per-identity consumption evidence, so they are brought up to what the
    # current consumer writes. Only the identities the fixture's own rows already express are
    # stated; nothing is invented about a posting the fixture does not contain.
    listed = [row["job_id"] for row in base_report.get("complete_candidate_list", [])]
    listed += [row["job_id"] for row in base_report.get("policy_exclusions", [])]
    base_report["consumed_job_ids"] = sorted(set(listed))
    base_report["below_fit_threshold_job_ids"] = []
    base_report["below_fit_threshold_count"] = 0

    def case(name: str, condition: str, live: dict, report: dict, coverage: dict | None = None
             ) -> tuple[str, dict]:
        directory = work / name
        directory.mkdir(parents=True, exist_ok=True)
        live_path = directory / "live_jobs.json"
        report_path = directory / "daily_report.json"
        live_path.write_text(json.dumps(live))
        report_path.write_text(json.dumps(report))
        argv = [str(INSPECTOR), "--live", str(live_path), "--report", str(report_path),
                "--registry", str(ROOT / "config/companies.yaml")]
        if coverage is not None:
            coverage_path = directory / "coverage.json"
            coverage_path.write_text(json.dumps(coverage))
            argv += ["--coverage", str(coverage_path)]
        return name, {"condition": condition, **_run(argv)}

    def clone_job(live: dict, new_id: str, **overrides) -> dict:
        copy = json.loads(json.dumps(live))
        record = json.loads(json.dumps(copy["jobs"][consumed_id]))
        record["job"]["job_id"] = new_id
        record["job"].update(overrides)
        copy["jobs"][new_id] = record
        return copy

    out: dict = {}
    for name, payload in [
        case("same_employer_second_job_missing_from_the_report",
             "two stored postings from the SAME employer; the report consumed one and says "
             "nothing about the other, and its below-fit count is zero",
             clone_job(base_live, consumed_id + "-unconsumed-control",
                       title="Synthetic control deliberately absent from report"),
             base_report),
        case("different_employer_job_missing_from_the_report",
             "a stored posting from a different employer, absent from the report",
             clone_job(base_live, "himalayas:all#other-employer-control",
                       employer_name="Sunapee Regional Trust",
                       title="Synthetic control from another employer"),
             base_report),
        case("second_job_genuinely_below_the_fit_threshold",
             "a second stored posting the report NAMES in below_fit_threshold_job_ids",
             clone_job(base_live, "himalayas:all#below-fit-control",
                       title="Synthetic control the consumer scored and did not list"),
             {**base_report,
              "consumed_job_ids": sorted(set(base_report["consumed_job_ids"])
                                         | {"himalayas:all#below-fit-control"}),
              "below_fit_threshold_job_ids": ["himalayas:all#below-fit-control"],
              "below_fit_threshold_count": 1}),
        case("second_job_absorbed_as_a_duplicate",
             "a second stored posting merged into a retained row's provenance",
             clone_job(base_live, "himalayas:all#duplicate-control"),
             _with_duplicate(base_report, consumed_id, "himalayas:all#duplicate-control")),
        case("stored_posting_first_observed_after_this_report",
             "the live view holds a posting first observed in a LATER run than the report's",
             clone_job(base_live, "himalayas:all#later-round-control")
             | {},
             base_report),
        case("report_predates_per_identity_evidence",
             "the report carries no consumed_job_ids at all",
             base_live,
             {k: v for k, v in base_report.items()
              if k not in ("consumed_job_ids", "below_fit_threshold_job_ids")}),
        case("every_stored_posting_reconciled",
             "the unmodified acceptance fixture, with the consumer's per-identity evidence",
             base_live, base_report),
    ]:
        out[name] = payload

    # The "observed later" control needs its record's run ids moved forward; do that explicitly so
    # the alteration is visible rather than buried in a helper.
    later_live = clone_job(base_live, "himalayas:all#later-round-control")
    later = later_live["jobs"]["himalayas:all#later-round-control"]
    later["observed_run_ids"] = ["2099-01-01"]
    later["first_seen_run_id"] = "2099-01-01"
    later["last_seen_run_id"] = "2099-01-01"
    name, payload = case(
        "stored_posting_first_observed_after_this_report",
        "the live view holds a posting first observed in a LATER run than the report's",
        later_live, base_report,
    )
    out[name] = payload
    return out


def _with_duplicate(report: dict, retained_id: str, absorbed_id: str) -> dict:
    copy = json.loads(json.dumps(report))
    for row in copy.get("complete_candidate_list", []):
        if row["job_id"] == retained_id:
            row.setdefault("possible_duplicate_of", []).append(absorbed_id)
    return copy


if __name__ == "__main__":
    shutil.get_terminal_size()
    raise SystemExit(main())
