"""P09: the release checkers must fail the conditions they claim to check.

P08's helpers printed the right observations and returned the wrong verdict. The package check
exited 0 / CODE_ONLY with a built template whose IAM role property had changed; the rollback
verifier printed MISMATCH and exited 0; the live check invented a below-fit disposition for a
posting the report never consumed. A checker that cannot fail is not a check, so each of those
conditions is asserted here against the maintained entrypoints under `scripts/`.

Every fixture is local and deliberately altered. None of it is evidence of a production
infrastructure change, an actual IAM edit, or a posting that went missing in production, and
nothing here makes an AWS call.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import tarfile

import pytest

from scripts.check_release_change_set import main as change_set_main
from scripts.inspect_discovery_integration import main as inspect_main
from scripts.verify_rollback_baseline import main as baseline_main

REPO = pathlib.Path(__file__).resolve().parents[1]
P08 = REPO / (
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_durable_discovery_publication_release_repair_v1"
)
ARCHIVE = P08 / "evidence/p06_baseline_src.tar.gz"
FIXTURES = P08 / "evidence/live_check_fixtures"

IAM_TEMPLATE = (
    "Resources:\n"
    "  ExampleRole:\n"
    "    Type: AWS::IAM::Role\n"
    "    Properties:\n"
    "      MaxSessionDuration: 3600\n"
)


def _pair(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    old, new = tmp_path / "old", tmp_path / "new"
    for build in (old, new):
        (build / "DiscoveryFunction/src").mkdir(parents=True)
        (build / "DiscoveryFunction/src/control.py").write_text("UNCHANGED = True\n")
        (build / "template.yaml").write_text(IAM_TEMPLATE)
    return old, new


def _check(old, new, repo=REPO, *extra: str) -> int:
    return change_set_main(
        ["--baseline", str(old), "--candidate", str(new), "--repo", str(repo), *extra]
    )


ASL = "infra/statemachine/jprs-daily-assemble.asl.json"


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _record_matching_the_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A recorded identity equal to the repository's CURRENT infrastructure files.

    The two passing cases below test the package and template comparison. They used to borrow the
    real repository's agreement with P06's record, which a genuine template change (the 2026-09-26
    discovery list grant) correctly ends; a record of the current files isolates what they test.
    """
    names = ("infra/template.yaml", "infra/samconfig.toml", "config/discovery_sources.yaml",
             ASL)
    record = tmp_path / "live_identity.json"
    record.write_text(json.dumps({"infra_inputs": {
        name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in names
    }}))
    return record


# ==================================================================================================
# Change set — the gate that decides whether a deploy is the code-only update the handoff describes
# ==================================================================================================
def test_a_changed_iam_property_in_the_built_template_is_not_code_only(tmp_path):
    old, new = _pair(tmp_path)
    (new / "template.yaml").write_text(IAM_TEMPLATE.replace("3600", "7200"))
    assert _check(old, new) == 1


def test_an_added_function_is_not_code_only(tmp_path):
    old, new = _pair(tmp_path)
    (new / "ReportFunction/src").mkdir(parents=True)
    (new / "ReportFunction/src/control.py").write_text("NEW = True\n")
    assert _check(old, new) == 1


def test_a_removed_function_is_not_code_only(tmp_path):
    old, new = _pair(tmp_path)
    (old / "ReportFunction/src").mkdir(parents=True)
    (old / "ReportFunction/src/control.py").write_text("GOING = True\n")
    assert _check(old, new) == 1


def test_an_unavailable_baseline_build_is_not_code_only(tmp_path):
    _old, new = _pair(tmp_path)
    assert _check(tmp_path / "never-built", new) == 1


def test_an_unavailable_recorded_baseline_is_not_code_only(tmp_path):
    """An unknown baseline is not a clean one: the comparison could not be made."""
    old, new = _pair(tmp_path)
    empty = tmp_path / "repo-without-record"
    empty.mkdir()
    assert _check(old, new, repo=empty) == 1


def test_a_genuine_code_only_change_passes(tmp_path):
    old, new = _pair(tmp_path)
    (new / "DiscoveryFunction/src/control.py").write_text("UNCHANGED = False\n")
    record = _record_matching_the_repo(tmp_path)
    assert _check(old, new, REPO, "--recorded-identity", str(record)) == 0


def test_a_build_path_only_codeuri_difference_passes(tmp_path):
    """SAM rewrites CodeUri per build directory; that alone is not an infrastructure change."""
    old, new = _pair(tmp_path)
    body = (
        "Resources:\n  Fn:\n    Type: AWS::Serverless::Function\n"
        "    Properties:\n      CodeUri: {path}\n      MemorySize: 512\n"
    )
    (old / "template.yaml").write_text(body.format(path="/build/aaa/DiscoveryFunction"))
    (new / "template.yaml").write_text(body.format(path="/build/bbb/DiscoveryFunction"))
    record = _record_matching_the_repo(tmp_path)
    assert _check(old, new, REPO, "--recorded-identity", str(record)) == 0


# ==================================================================================================
# A release that NEEDS an infrastructure change: reported and gated, never waved through as code
# ==================================================================================================
LIST_GRANT_TEMPLATE = IAM_TEMPLATE + (
    "  DiscoveryRole:\n"
    "    Type: AWS::IAM::Role\n"
    "    Properties:\n"
    "      Statement:\n"
    "        - Sid: DiscoveryListOwnPrefix\n"
    "          Action: s3:ListBucket\n"
    "          Resource: !Sub arn:aws:s3:::${BucketName}\n"
)
LIST_GRANT_DELTA = [
    {"path": "Resources.DiscoveryRole.Type", "before": None, "after": "AWS::IAM::Role"},
    {"path": "Resources.DiscoveryRole.Properties.Statement[0].Sid", "before": None,
     "after": "DiscoveryListOwnPrefix"},
    {"path": "Resources.DiscoveryRole.Properties.Statement[0].Action", "before": None,
     "after": "s3:ListBucket"},
    {"path": "Resources.DiscoveryRole.Properties.Statement[0].Resource.__tag__", "before": None,
     "after": "Sub"},
    {"path": "Resources.DiscoveryRole.Properties.Statement[0].Resource.value", "before": None,
     "after": "arn:aws:s3:::${BucketName}"},
]


def _declared(tmp_path, rows, *, files=None, reason="scoped list grant") -> pathlib.Path:
    path = tmp_path / "declared_delta.json"
    path.write_text(json.dumps({
        "reason": reason, "infrastructure_source": files or {}, "template_differences": rows,
    }))
    return path


def _granted_pair(tmp_path):
    old, new = _pair(tmp_path)
    (new / "template.yaml").write_text(LIST_GRANT_TEMPLATE)
    return old, new, _record_matching_the_repo(tmp_path)


def test_an_undeclared_list_grant_is_reported_and_fails(tmp_path, capsys):
    old, new, record = _granted_pair(tmp_path)
    assert _check(old, new, REPO, "--recorded-identity", str(record)) == 1
    out = capsys.readouterr().out
    assert "CHANGE_SET_INCLUDES_INFRASTRUCTURE" in out
    assert "DiscoveryListOwnPrefix" in out


def test_an_exactly_declared_delta_passes_and_is_named_not_called_code_only(tmp_path, capsys):
    old, new, record = _granted_pair(tmp_path)
    delta = _declared(tmp_path, LIST_GRANT_DELTA)
    assert _check(old, new, REPO, "--recorded-identity", str(record),
                  "--declared-delta", str(delta)) == 0
    out = capsys.readouterr().out
    assert "CHANGE_SET_IS_CODE_PLUS_DECLARED_INFRASTRUCTURE" in out
    assert "CHANGE_SET_IS_CODE_ONLY" not in out
    assert "scoped list grant" in out


def test_an_undeclared_difference_beside_a_declared_one_fails(tmp_path, capsys):
    old, new, record = _granted_pair(tmp_path)
    (new / "template.yaml").write_text(LIST_GRANT_TEMPLATE.replace("3600", "7200"))
    delta = _declared(tmp_path, LIST_GRANT_DELTA)
    assert _check(old, new, REPO, "--recorded-identity", str(record),
                  "--declared-delta", str(delta)) == 1
    assert "UNDECLARED Resources.ExampleRole.Properties.MaxSessionDuration" in capsys.readouterr().out


def test_a_declared_difference_that_did_not_happen_fails(tmp_path, capsys):
    old, new, record = _granted_pair(tmp_path)
    rows = LIST_GRANT_DELTA + [{"path": "Resources.DiscoveryRole.Properties.Extra",
                                "before": None, "after": "x"}]
    delta = _declared(tmp_path, rows)
    assert _check(old, new, REPO, "--recorded-identity", str(record),
                  "--declared-delta", str(delta)) == 1
    assert "NOT OBSERVED Resources.DiscoveryRole.Properties.Extra" in capsys.readouterr().out


def test_a_changed_infrastructure_file_passes_only_at_its_declared_hash(tmp_path):
    old, new = _pair(tmp_path)
    stale = tmp_path / "stale_identity.json"
    stale.write_text(json.dumps({"infra_inputs": {"infra/template.yaml": "0" * 64,
                                                  ASL: _sha(ASL)}}))
    current = hashlib.sha256((REPO / "infra/template.yaml").read_bytes()).hexdigest()
    base = ["--recorded-identity", str(stale), "--declared-delta"]
    right = _declared(tmp_path, [], files={"infra/template.yaml": current})
    assert _check(old, new, REPO, *base, str(right)) == 0
    wrong = _declared(tmp_path, [], files={"infra/template.yaml": "f" * 64})
    assert _check(old, new, REPO, *base, str(wrong)) == 1
    assert _check(old, new, REPO, "--recorded-identity", str(stale)) == 1


@pytest.mark.parametrize("body", ["not json", "{}", '{"reason": "", "template_differences": []}',
                                  '{"reason": "x", "template_differences": [{"before": 1}]}'])
def test_a_malformed_declaration_is_not_a_pass(tmp_path, body):
    old, new, record = _granted_pair(tmp_path)
    delta = tmp_path / "bad.json"
    delta.write_text(body)
    assert _check(old, new, REPO, "--recorded-identity", str(record),
                  "--declared-delta", str(delta)) == 1


# ==================================================================================================
# Rollback baseline — validate before restoring, and never restore over the working tree
# ==================================================================================================
def _repack(tmp_path: pathlib.Path, name: str, mutate) -> pathlib.Path:
    extracted = tmp_path / f"{name}-src"
    with tarfile.open(ARCHIVE) as tar:
        tar.extractall(extracted, filter="data")
    mutate(extracted / "src")
    out = tmp_path / f"{name}.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        tar.add(extracted / "src", arcname="src")
    return out


def test_the_archived_p06_baseline_verifies():
    assert baseline_main(["--archive", str(ARCHIVE), "--repo", str(REPO)]) == 0


def test_a_corrupt_archive_is_refused(tmp_path):
    corrupt = tmp_path / "corrupt.tar.gz"
    raw = bytearray(ARCHIVE.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    corrupt.write_bytes(bytes(raw))
    assert baseline_main(["--archive", str(corrupt), "--repo", str(REPO)]) == 1


def test_a_modified_recorded_module_is_refused(tmp_path):
    def mutate(src: pathlib.Path) -> None:
        target = src / "discovery/handler.py"
        target.write_text(target.read_text() + "\n# tamper control\n")

    assert baseline_main(
        ["--archive", str(_repack(tmp_path, "tampered", mutate)), "--repo", str(REPO)]
    ) == 1


def test_unrecorded_executable_source_in_the_archive_is_refused(tmp_path):
    """"Extra" code is exactly what a rollback must not silently carry back."""
    def mutate(src: pathlib.Path) -> None:
        (src / "discovery/extra_module.py").write_text("SMUGGLED = True\n")

    assert baseline_main(
        ["--archive", str(_repack(tmp_path, "smuggled", mutate)), "--repo", str(REPO)]
    ) == 1


def test_a_missing_archive_is_refused(tmp_path):
    assert baseline_main(
        ["--archive", str(tmp_path / "absent.tar.gz"), "--repo", str(REPO)]
    ) == 1


def test_restoring_over_the_working_tree_source_is_refused():
    """The one thing this script must never do, asserted rather than promised."""
    before = hashlib.sha256(
        b"".join(
            p.read_bytes() for p in sorted((REPO / "src").rglob("*.py"))
        )
    ).hexdigest()
    assert baseline_main([
        "--archive", str(ARCHIVE), "--repo", str(REPO), "--restore-into", str(REPO / "src"),
    ]) == 1
    after = hashlib.sha256(
        b"".join(
            p.read_bytes() for p in sorted((REPO / "src").rglob("*.py"))
        )
    ).hexdigest()
    assert before == after


def test_restore_and_return_in_a_scratch_directory(tmp_path):
    """Restore the baseline somewhere safe, then confirm the checkout is untouched."""
    target = tmp_path / "restored"
    assert baseline_main([
        "--archive", str(ARCHIVE), "--repo", str(REPO), "--restore-into", str(target),
    ]) == 0
    restored = sorted(str(p.relative_to(target)) for p in target.rglob("*.py"))
    assert len(restored) == 36, restored
    # Returning is simply discarding the scratch tree; the working tree was never a participant.
    assert (REPO / "src/discovery/live.py").exists(), "the current source must still be in place"


def test_restoring_into_a_non_empty_directory_is_refused(tmp_path):
    target = tmp_path / "occupied"
    target.mkdir()
    (target / "something.txt").write_text("already here\n")
    assert baseline_main([
        "--archive", str(ARCHIVE), "--repo", str(REPO), "--restore-into", str(target),
    ]) == 1


# ==================================================================================================
# Per-identity report reconciliation
# ==================================================================================================
def _fixtures(tmp_path: pathlib.Path, live: dict, report: dict) -> list[str]:
    live_path = tmp_path / "live_jobs.json"
    report_path = tmp_path / "daily_report.json"
    live_path.write_text(json.dumps(live))
    report_path.write_text(json.dumps(report))
    return ["--live", str(live_path), "--report", str(report_path),
            "--registry", str(REPO / "config/companies.yaml")]


@pytest.fixture
def acceptance() -> tuple[dict, dict, str]:
    """The P08 acceptance fixture, brought up to the evidence the current consumer writes."""
    report = json.loads((FIXTURES / "A_acceptance_daily_report.json").read_text())
    live = json.loads((FIXTURES / "A_acceptance_live_jobs.json").read_text())
    listed = [row["job_id"] for row in report.get("complete_candidate_list", [])]
    listed += [row["job_id"] for row in report.get("policy_exclusions", [])]
    report["consumed_job_ids"] = sorted(set(listed))
    report["below_fit_threshold_job_ids"] = []
    report["below_fit_threshold_count"] = 0
    return live, report, next(iter(live["jobs"]))


def _clone(live: dict, source_id: str, new_id: str, **overrides) -> dict:
    copy = json.loads(json.dumps(live))
    record = json.loads(json.dumps(copy["jobs"][source_id]))
    record["job"]["job_id"] = new_id
    record["job"].update(overrides)
    copy["jobs"][new_id] = record
    return copy


def test_a_second_job_from_the_same_employer_missing_from_the_report_is_not_below_fit(
    tmp_path, acceptance
):
    """The exact control P08's review reproduced, with the opposite verdict required.

    The report consumed one posting from this employer and has ZERO below-fit jobs. Membership in
    `previously_unseen_employers` says nothing about the second posting, and the check must no
    longer read it as proof of consumption.
    """
    live, report, consumed = acceptance
    live = _clone(live, consumed, consumed + "-unconsumed-control",
                  title="Synthetic control deliberately absent from report")
    assert inspect_main(_fixtures(tmp_path, live, report)) == 1


def test_a_missing_job_from_a_different_employer_is_also_not_reconciled(tmp_path, acceptance):
    live, report, consumed = acceptance
    live = _clone(live, consumed, "himalayas:all#other-employer-control",
                  employer_name="Sunapee Regional Trust", title="Synthetic control")
    assert inspect_main(_fixtures(tmp_path, live, report)) == 1


def test_a_genuinely_below_fit_job_named_by_the_report_reconciles(tmp_path, acceptance):
    """The legitimate version of the same shape: the CONSUMER states the disposition."""
    live, report, consumed = acceptance
    below = "himalayas:all#below-fit-control"
    live = _clone(live, consumed, below, title="Scored and not listed")
    report = dict(
        report,
        consumed_job_ids=sorted({*report["consumed_job_ids"], below}),
        below_fit_threshold_job_ids=[below],
        below_fit_threshold_count=1,
    )
    assert inspect_main(_fixtures(tmp_path, live, report)) == 0


def test_a_legitimately_deduplicated_job_reconciles(tmp_path, acceptance):
    live, report, consumed = acceptance
    duplicate = "himalayas:all#duplicate-control"
    live = _clone(live, consumed, duplicate)
    report = json.loads(json.dumps(report))
    for row in report["complete_candidate_list"]:
        if row["job_id"] == consumed:
            row.setdefault("possible_duplicate_of", []).append(duplicate)
    assert inspect_main(_fixtures(tmp_path, live, report)) == 0


def test_a_live_view_newer_than_the_report_cannot_conclude_either_way(tmp_path, acceptance):
    """A later view is not the population an older report consumed; neither verdict is available."""
    live, report, consumed = acceptance
    later = "himalayas:all#later-round-control"
    live = _clone(live, consumed, later)
    live["jobs"][later].update(
        observed_run_ids=["2099-01-01"], first_seen_run_id="2099-01-01",
        last_seen_run_id="2099-01-01",
    )
    assert inspect_main(_fixtures(tmp_path, live, report)) == 2


def test_a_report_without_per_identity_evidence_is_absent_evidence_not_a_zero(
    tmp_path, acceptance
):
    live, report, _consumed = acceptance
    report = {k: v for k, v in report.items()
              if k not in ("consumed_job_ids", "below_fit_threshold_job_ids")}
    assert inspect_main(_fixtures(tmp_path, live, report)) == 2


def test_the_unmodified_acceptance_fixture_still_reconciles(tmp_path, acceptance):
    """P08's five controls keep their meaning; this is its positive one."""
    live, report, _consumed = acceptance
    assert inspect_main(_fixtures(tmp_path, live, report)) == 0


def test_the_consumer_states_the_identities_a_reconciliation_needs():
    """The evidence the inspector depends on is produced by the report, not by the inspector."""
    import inspect as _inspect

    from src.report import handler

    source = _inspect.getsource(handler.render_report)
    assert '"consumed_job_ids"' in source
    assert '"below_fit_threshold_job_ids"' in source


# ==================================================================================================
# A baseline archived after P06 (the live P10 tree) verifies against its own JSON manifest
# ==================================================================================================
def _manifest_archive(tmp_path: pathlib.Path, *, tamper: bool = False):
    tree = tmp_path / "live"
    (tree / "src/discovery").mkdir(parents=True)
    (tree / "infra").mkdir()
    (tree / "src/discovery/handler.py").write_text("LIVE = True\n")
    (tree / "infra/template.yaml").write_text(IAM_TEMPLATE)
    files = {
        rel: hashlib.sha256((tree / rel).read_bytes()).hexdigest()
        for rel in ("src/discovery/handler.py", "infra/template.yaml")
    }
    if tamper:
        (tree / "src/discovery/handler.py").write_text("LIVE = False\n")
    archive = tmp_path / "live.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(tree / "src", arcname="src")
        tar.add(tree / "infra", arcname="infra")
    manifest = tmp_path / "live_manifest.json"
    manifest.write_text(json.dumps({"files": files}))
    return archive, manifest


def test_a_json_manifest_baseline_verifies_and_restores_its_template(tmp_path):
    archive, manifest = _manifest_archive(tmp_path)
    target = tmp_path / "restored"
    assert baseline_main(["--archive", str(archive), "--repo", str(REPO),
                          "--recorded-identity", str(manifest),
                          "--restore-into", str(target)]) == 0
    assert (target / "infra/template.yaml").read_text() == IAM_TEMPLATE


def test_a_json_manifest_baseline_with_a_changed_module_is_refused(tmp_path):
    archive, manifest = _manifest_archive(tmp_path, tamper=True)
    assert baseline_main(["--archive", str(archive), "--repo", str(REPO),
                          "--recorded-identity", str(manifest)]) == 1


def test_a_state_machine_definition_the_record_does_not_cover_fails(tmp_path, capsys):
    """DefinitionUri is normalized away in the built template and ships in no function package, so
    an unrecorded definition file would be an unchecked Step Functions change."""
    old, new = _pair(tmp_path)
    record = tmp_path / "no_asl.json"
    record.write_text(json.dumps({"infra_inputs": {
        name: _sha(name)
        for name in ("infra/template.yaml", "infra/samconfig.toml", "config/discovery_sources.yaml")
    }}))
    assert _check(old, new, REPO, "--recorded-identity", str(record)) == 1
    assert ASL in capsys.readouterr().out


def test_a_changed_state_machine_definition_fails(tmp_path):
    old, new = _pair(tmp_path)
    record = _record_matching_the_repo(tmp_path)
    doc = json.loads(record.read_text())
    doc["infra_inputs"][ASL] = "0" * 64
    record.write_text(json.dumps(doc))
    assert _check(old, new, REPO, "--recorded-identity", str(record)) == 1


def test_a_declared_file_that_did_not_change_fails(tmp_path, capsys):
    old, new = _pair(tmp_path)
    record = _record_matching_the_repo(tmp_path)
    delta = _declared(tmp_path, [], files={"infra/samconfig.toml": "a" * 64})
    assert _check(old, new, REPO, "--recorded-identity", str(record),
                  "--declared-delta", str(delta)) == 1
    assert "did NOT change" in capsys.readouterr().out
