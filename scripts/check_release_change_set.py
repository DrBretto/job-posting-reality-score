"""Decide whether a candidate build is the CODE-ONLY change the release handoff describes.

Why this script exists, and what replaced what
----------------------------------------------
P07's handoff asserted that a deploy could only change two functions. P07's review refuted that from
the build: every function inherits `Globals.Function.CodeUri: ../`, so a shared-module edit changes
all six artifacts and a two-function stop rule would reject a correct deploy. P08 answered by
MEASURING the change set — and then did not gate on what it measured. Its review reproduced the
consequence: with identical application files and a built template whose IAM role property moved
from 3600 to 7200, it printed the difference and exited 0 / CODE_ONLY. `infra_source_changed` was
initialized false and never assigned; current source hashes were printed rather than compared;
added and removed functions only printed.

So this script gates. Every check below is either PERFORMED and passed, PERFORMED and failed, or
NOT PERFORMED — and the third case fails exactly like the second. A check that could not run is not
evidence that nothing changed, which is the specific way the previous version was false-green.

What is compared
----------------
  infrastructure source     `infra/template.yaml`, `infra/samconfig.toml` and the shipped discovery
                            source config, against the hashes P06 RECORDED before it deployed. An
                            unavailable record fails; it is an unknown baseline, not a clean one.
  function set              directories present in the baseline build and the candidate build. An
                            added or removed function is an infrastructure change.
  resource definitions      the two BUILT templates, parsed and compared resource by resource and
                            property by property. IAM statements, schedules, parameters, state
                            machine definitions and retention all live here. Only `CodeUri` and
                            absolute build paths are normalized away, because SAM rewrites those per
                            build directory; the normalization is named in the output so it can be
                            argued with rather than assumed.
  packaged contents         every file in every function package, by content hash. Modification
                            times cannot tell a restored file from a rewritten one.

What this is NOT
----------------
This is a LOCAL comparison of two built packages. It is not an AWS change set, it makes no AWS call,
and it must not be described as one. `sam deploy --no-execute-changeset` followed by an inspection
of the real change set remains a separate, later, required step: CloudFormation can change resources
for reasons no local package diff can see — a parameter's previous value, a drifted resource, a
transform's own output.

Comparing against what is live NOW, and a declared infrastructure delta
----------------------------------------------------------------------
The recorded baseline defaults to P06's record. After P10 was deployed that record describes a
version that is no longer live, so `--recorded-identity` names the record of the version actually
running (a P06-format text record, or a JSON record carrying `infra_inputs` or `files`).

A release that genuinely needs an infrastructure change must not be squeezed through a code-only
gate and must not bypass it. `--declared-delta` names a JSON file that states the change EXACTLY:

    {"reason": "...",
     "infrastructure_source": {"infra/template.yaml": "<sha256 of the candidate file>"},
     "template_differences": [{"path": "<flattened path>", "before": <value or null>,
                               "after": <value or null>}, ...]}

With it, the gate still performs every comparison and still prints every difference. It passes only
when the observed infrastructure differences and the declared ones are the SAME set: an undeclared
difference fails, a declared difference that did not happen fails, and a changed infrastructure
file passes only at exactly the declared hash. The verdict then names the delta
(`CHANGE_SET_IS_CODE_PLUS_DECLARED_INFRASTRUCTURE`) instead of calling it code-only. `null` means
absent on that side.

Usage
-----
    python scripts/check_release_change_set.py --baseline <old-build-dir> \
        --candidate <new-build-dir> [--repo <repository-root>] \
        [--recorded-identity <record>] [--declared-delta <delta.json>]

Exit code 0 only when every check was performed and the change set is code-only, or code plus
exactly the declared infrastructure delta. 1 otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

RECORDED_IDENTITY = (
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt"
)

# Directories inside a built package that are vendored dependencies rather than application code.
VENDORED_MARKERS = (".dist-info", ".egg-info")
VENDORED_TOP = {
    "pydantic", "pydantic_core", "yaml", "_yaml", "annotated_types",
    "typing_extensions.py", "typing_inspection",
}

# Files whose difference inside a package is an INFRASTRUCTURE change, not a code change.
INFRA_FILES = {"template.yaml"}

# Properties SAM rewrites per build directory. Normalizing these is the one allowance, and it is
# stated in the report: a build at a different path is not an infrastructure change.
BUILD_PATH_PROPERTIES = {"CodeUri", "ContentUri", "DefinitionUri"}


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------------------------------
# Template parsing — structural, so a reordered mapping is not reported as a change
# --------------------------------------------------------------------------------------------------
def _load_template(path: pathlib.Path):
    """Parse a CloudFormation/SAM template, keeping intrinsic tags as comparable markers."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    def _tagged(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return {"__tag__": suffix, "value": loader.construct_scalar(node)}
        if isinstance(node, yaml.SequenceNode):
            return {"__tag__": suffix, "value": loader.construct_sequence(node, deep=True)}
        return {"__tag__": suffix, "value": loader.construct_mapping(node, deep=True)}

    Loader.add_multi_constructor("!", _tagged)
    Loader.add_multi_constructor("tag:yaml.org,2002:", yaml.SafeLoader.construct_undefined)
    for tag in ("str", "int", "float", "bool", "null", "seq", "map", "timestamp"):
        Loader.add_constructor(
            f"tag:yaml.org,2002:{tag}", getattr(yaml.SafeLoader, f"construct_yaml_{tag}")
        )
    return yaml.load(path.read_text(), Loader=Loader) or {}


def _normalize(value, *, roots: tuple[str, ...]):
    """Strip build-path noise so two builds of the same template compare equal."""
    if isinstance(value, dict):
        return {
            key: ("<normalized build path>" if key in BUILD_PATH_PROPERTIES
                  else _normalize(item, roots=roots))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize(item, roots=roots) for item in value]
    if isinstance(value, str):
        text = value
        for root in roots:
            if root:
                text = text.replace(root, "<normalized build path>")
        return text
    return value


def _flatten(value, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(_flatten(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            out.update(_flatten(item, f"{prefix}[{index}]"))
    else:
        out[prefix] = value
    return out


# --------------------------------------------------------------------------------------------------
# Package indexing
# --------------------------------------------------------------------------------------------------
def _is_vendored(rel: pathlib.PurePath) -> bool:
    top = rel.parts[0]
    if top in VENDORED_TOP:
        return True
    return any(marker in top for marker in VENDORED_MARKERS)


def _index(root: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        out[str(path.relative_to(root))] = _sha256(path)
    return out


def _classify(rel: str) -> str:
    parts = pathlib.PurePath(rel)
    if rel in INFRA_FILES:
        return "infrastructure"
    if _is_vendored(parts):
        return "dependency"
    if parts.parts[0] == "src":
        return "application code"
    if parts.parts[0] in {"config", "policies"}:
        return "shipped configuration"
    return "repository payload"


def _referenced_sources(repo: pathlib.Path) -> list[str]:
    """Repository paths of files the source template pulls in by a `*Uri` property (not CodeUri)."""
    template = repo / "infra/template.yaml"
    if not template.exists():
        return []
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in BUILD_PATH_PROPERTIES - {"CodeUri"} and isinstance(value, str):
                    found.append(str((pathlib.PurePosixPath("infra") / value)))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(_load_template(template))
    return sorted(set(found))


def _recorded_infrastructure(repo: pathlib.Path,
                             record: pathlib.Path | None = None) -> dict[str, str] | None:
    """The deployed version's own record of its infrastructure. `None` means no baseline.

    Defaults to P06's record. A JSON record (the P10 release identity's `infra_inputs`, or a
    baseline manifest's non-`src/` `files`) is read the same way: path -> sha256.
    """
    record = record if record is not None else repo / RECORDED_IDENTITY
    if not record.exists():
        return None
    if record.suffix == ".json":
        doc = json.loads(record.read_text())
        hashes = doc.get("infra_inputs") or {
            rel: digest for rel, digest in (doc.get("files") or {}).items()
            if not rel.startswith("src/")
        }
        return dict(hashes) or None
    hashes: dict[str, str] = {}
    section = None
    for line in record.read_text().splitlines():
        if line.startswith("--- template + config"):
            section = "tpl"
            continue
        if line.startswith("--- ") and section == "tpl":
            section = None
            continue
        match = re.match(r"^([0-9a-f]{64})\s+(\S+)$", line.strip())
        if match and section == "tpl":
            hashes[match.group(2)] = match.group(1)
    return hashes or None


class Report:
    """Checks with an explicit performed/passed state, so a skipped check cannot read as a pass."""

    def __init__(self) -> None:
        self.checks: list[dict] = []

    def record(self, name: str, *, performed: bool, passed: bool, detail: list[str]) -> None:
        self.checks.append(
            {"name": name, "performed": performed, "passed": passed, "detail": detail}
        )

    def failed(self) -> list[dict]:
        return [c for c in self.checks if not c["performed"] or not c["passed"]]

    def render(self) -> None:
        for check in self.checks:
            state = (
                "PASS" if check["performed"] and check["passed"]
                else "FAIL" if check["performed"] else "NOT PERFORMED"
            )
            print(f"[{state:13s}] {check['name']}")
            for line in check["detail"]:
                print(f"                  {line}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local code-only release gate. Makes no AWS call.")
    parser.add_argument("--baseline", required=True, type=pathlib.Path,
                        help="build directory of the currently deployed version")
    parser.add_argument("--candidate", required=True, type=pathlib.Path,
                        help="build directory of the version proposed for deployment")
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--recorded-identity", type=pathlib.Path,
                        help="record of the version live now (default: P06's record)")
    parser.add_argument("--declared-delta", type=pathlib.Path,
                        help="JSON stating the exact infrastructure change this release makes")
    args = parser.parse_args(argv)

    baseline = args.baseline.resolve()
    candidate = args.candidate.resolve()
    repo = args.repo.resolve()
    report = Report()
    declared = _load_declared_delta(args.declared_delta)
    if args.declared_delta is not None and declared is None:
        report.record("declared infrastructure delta", performed=False, passed=False,
                      detail=[f"unreadable or malformed: {args.declared_delta}"])
        report.render()
        return _verdict(report, declared=None)

    print("=== local release change-set check ===")
    print(f"baseline build:  {baseline}")
    print(f"candidate build: {candidate}")
    print("This is a comparison of two locally built packages. It is NOT an AWS change set and no")
    print("AWS call is made here; inspecting the real change set is a separate, later step.")
    print()

    # ---- 1. infrastructure source against P06's recorded baseline --------------------------------
    record_path = args.recorded_identity
    if record_path is not None and not record_path.is_absolute():
        record_path = repo / record_path
    recorded = _recorded_infrastructure(repo, record_path)
    declared_files = (declared or {}).get("infrastructure_source", {})
    if recorded is None:
        report.record(
            "infrastructure source vs recorded baseline", performed=False, passed=False,
            detail=[f"no recorded baseline at {record_path or RECORDED_IDENTITY}",
                    "an unavailable baseline is an unknown baseline, not a clean one"],
        )
    else:
        detail: list[str] = [f"recorded baseline: {record_path or RECORDED_IDENTITY}"]
        changed = False
        for rel, want in sorted(recorded.items()):
            path = repo / rel
            if not path.exists():
                changed = True
                detail.append(f"MISSING  {rel} (recorded {want[:12]}…)")
                continue
            have = _sha256(path)
            if have == want:
                detail.append(f"SAME     {rel}")
                if rel in declared_files:
                    changed = True
                    detail.append("           declared as changed, but it did NOT change")
                continue
            if declared_files.get(rel) == have:
                detail.append(f"DECLARED {rel} — changed, at exactly the declared hash")
            else:
                changed = True
                detail.append(f"CHANGED  {rel}"
                              + (" — NOT at the declared hash" if rel in declared_files else ""))
            detail.append(f"           recorded {want}")
            detail.append(f"           current  {have}")
        stray = sorted(set(declared_files) - set(recorded))
        if stray:
            changed = True
            detail.append(f"declared files the record does not cover: {stray}")
        # A resource defined by a separate source file (a state machine's DefinitionUri) is outside
        # every function package and is normalized away in the built template, so the ONLY place a
        # change to it can be seen is here. An unrecorded one is an unchecked one.
        unrecorded = sorted(set(_referenced_sources(repo)) - set(recorded))
        if unrecorded:
            changed = True
            detail.append(f"infrastructure sources the record does not cover: {unrecorded}")
        report.record("infrastructure source vs recorded baseline",
                      performed=True, passed=not changed, detail=detail)

    # ---- 2. the function set ---------------------------------------------------------------------
    if not baseline.is_dir() or not candidate.is_dir():
        missing = [str(p) for p in (baseline, candidate) if not p.is_dir()]
        report.record("function set", performed=False, passed=False,
                      detail=[f"build directory unavailable: {', '.join(missing)}"])
        report.record("built template resource definitions", performed=False, passed=False,
                      detail=["skipped: a build directory is unavailable"])
        report.record("packaged contents", performed=False, passed=False,
                      detail=["skipped: a build directory is unavailable"])
        print()
        report.render()
        return _verdict(report, declared=declared)

    old_functions = {d.name for d in baseline.iterdir() if d.is_dir()}
    new_functions = {d.name for d in candidate.iterdir() if d.is_dir()}
    added = sorted(new_functions - old_functions)
    removed = sorted(old_functions - new_functions)
    report.record(
        "function set", performed=True, passed=not (added or removed),
        detail=(
            [f"{len(old_functions)} function(s) in both builds"] if not (added or removed)
            else [f"added: {added or '(none)'}", f"removed: {removed or '(none)'}",
                  "adding or removing a function is an infrastructure change"]
        ),
    )

    # ---- 3. built template resource definitions ---------------------------------------------------
    old_template = baseline / "template.yaml"
    new_template = candidate / "template.yaml"
    if not old_template.exists() or not new_template.exists():
        report.record(
            "built template resource definitions", performed=False, passed=False,
            detail=[f"baseline template present: {old_template.exists()}",
                    f"candidate template present: {new_template.exists()}",
                    "without both templates the resource comparison cannot be made"],
        )
    else:
        roots = (str(baseline), str(candidate))
        old_doc = _normalize(_load_template(old_template), roots=roots)
        new_doc = _normalize(_load_template(new_template), roots=roots)
        detail = [
            "normalized away: " + ", ".join(sorted(BUILD_PATH_PROPERTIES))
            + " and absolute build-directory paths (SAM rewrites these per build)",
        ]
        differences: list[str] = []
        observed: set[tuple[str, str, str]] = set()
        for section in sorted(set(old_doc) | set(new_doc)):
            old_flat = _flatten(old_doc.get(section), section)
            new_flat = _flatten(new_doc.get(section), section)
            for path in sorted(set(old_flat) | set(new_flat)):
                if old_flat.get(path) != new_flat.get(path):
                    differences.append(
                        f"{path}: {old_flat.get(path, '(absent)')!r} -> "
                        f"{new_flat.get(path, '(absent)')!r}"
                    )
                    observed.add((path, json.dumps(old_flat.get(path), default=str),
                                  json.dumps(new_flat.get(path), default=str)))
        if differences:
            detail.append(f"{len(differences)} resource/property difference(s):")
            detail.extend(f"  {line}" for line in differences[:25])
            if len(differences) > 25:
                detail.append(f"  … and {len(differences) - 25} more")
        else:
            detail.append("resource definitions are identical once build paths are normalized")
        passed = not differences
        if declared is not None:
            wanted = {
                (row["path"], json.dumps(row.get("before"), default=str),
                 json.dumps(row.get("after"), default=str))
                for row in declared.get("template_differences", [])
            }
            undeclared = sorted(observed - wanted)
            unobserved = sorted(wanted - observed)
            detail.append(f"declared delta: {len(wanted)} difference(s); "
                          f"undeclared observed: {len(undeclared)}; declared not observed: "
                          f"{len(unobserved)}")
            detail.extend(f"  UNDECLARED {row[0]}: {row[1]} -> {row[2]}" for row in undeclared)
            detail.extend(f"  NOT OBSERVED {row[0]}: {row[1]} -> {row[2]}" for row in unobserved)
            passed = not undeclared and not unobserved
        report.record("built template resource definitions",
                      performed=True, passed=passed, detail=detail)

    # ---- 4. packaged contents ---------------------------------------------------------------------
    categories: dict[str, set[str]] = {}
    changed_functions: list[str] = []
    detail = []
    for function in sorted(old_functions & new_functions):
        old = _index(baseline / function)
        new = _index(candidate / function)
        differing = sorted(rel for rel in set(old) | set(new) if old.get(rel) != new.get(rel))
        if not differing:
            detail.append(f"{function}: identical")
            continue
        changed_functions.append(function)
        per: dict[str, list[str]] = {}
        for rel in differing:
            per.setdefault(_classify(rel), []).append(rel)
            categories.setdefault(_classify(rel), set()).add(rel)
        detail.append(
            f"{function}: {len(differing)} file(s) differ — "
            + ", ".join(f"{kind}={len(items)}" for kind, items in sorted(per.items()))
        )
        for kind, items in sorted(per.items()):
            if kind == "dependency":
                continue
            for rel in items[:20]:
                state = "added" if rel not in old else "removed" if rel not in new else "modified"
                detail.append(f"    [{kind}] {state}: {rel}")
    detail.append(
        f"functions whose artifact changes: {len(changed_functions)} of "
        f"{len(old_functions & new_functions)} — {', '.join(changed_functions) or '(none)'}"
    )
    infra_in_packages = "infrastructure" in categories
    if infra_in_packages:
        detail.append("an infrastructure file differs INSIDE a function package")
    report.record("packaged contents", performed=True, passed=not infra_in_packages, detail=detail)

    print()
    report.render()
    return _verdict(report, declared=declared)


def _load_declared_delta(path: pathlib.Path | None) -> dict | None:
    if path is None:
        return None
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    rows = doc.get("template_differences")
    files = doc.get("infrastructure_source", {})
    if not isinstance(rows, list) or not isinstance(files, dict) or not doc.get("reason"):
        return None
    if any(not isinstance(row, dict) or "path" not in row for row in rows):
        return None
    return doc


def _verdict(report: Report, *, declared: dict | None = None) -> int:
    print()
    print("--- verdict ---")
    failures = report.failed()
    if not failures and declared is not None:
        print("CHANGE_SET_IS_CODE_PLUS_DECLARED_INFRASTRUCTURE — every check was performed; the")
        print("  infrastructure differences are EXACTLY the declared ones, and nothing else differs")
        print("  beyond packaged application code. This is NOT a code-only release. Declared:")
        print(f"    reason: {declared['reason']}")
        for row in declared.get("template_differences", []):
            print(f"    {row['path']}: {row.get('before')!r} -> {row.get('after')!r}")
        print("  The real AWS change set is still a separate inspection before deployment.")
        return 0
    if not failures:
        print("CHANGE_SET_IS_CODE_ONLY — every check was performed and found only packaged")
        print("  application code differing. No IAM, schedule, parameter, state-machine or")
        print("  retention difference is present in these packages or in the recorded baseline.")
        print("  The real AWS change set is still a separate inspection before deployment.")
        return 0
    unperformed = [c["name"] for c in failures if not c["performed"]]
    if unperformed:
        print("COMPARISON_INCOMPLETE — these checks could not be made, so the change set is")
        print("  UNKNOWN and must not be treated as code-only:")
        for name in unperformed:
            print(f"    {name}")
    failed = [c["name"] for c in failures if c["performed"]]
    if failed:
        print("CHANGE_SET_INCLUDES_INFRASTRUCTURE — not the code-only update the handoff describes:")
        for name in failed:
            print(f"    {name}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
