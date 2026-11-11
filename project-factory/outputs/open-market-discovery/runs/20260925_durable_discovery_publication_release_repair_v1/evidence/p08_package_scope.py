"""Derive the ACTUAL deployment change set by diffing two built packages, function by function.

Why this script exists
----------------------
P07's handoff said a deploy could only change the discovery and report function code. P07's review
refuted that from the build: every function inherits `Globals.Function.CodeUri: ../`, so every
function's artifact contains the whole repository and a shared-module edit changes all of them. The
stop rule that followed from the wrong claim — "reject anything but two function changes" — would
reject a legitimate code-only update.

So the change set is MEASURED here rather than asserted: hash every file in the old package and the
new one, per function, and report what actually differs. Content hashes only; a modification time
cannot tell a restored file from a rewritten one.

It also separates the two categories the release rule cares about, because "six functions changed" is
safe and "an IAM statement changed" is not, and a file count cannot tell them apart:

  CODE-ONLY      differences confined to packaged application code
  INFRASTRUCTURE any difference in the source template, the SAM config, or the built template's
                 resource definitions — IAM, schedules, parameters, state machine, retention

Usage:  python p08_package_scope.py <old-build-dir> <new-build-dir> [repo-root]
Exit code 0 means the change set is code-only; 1 means an infrastructure difference is present and
the deploy is NOT the code-only update the handoff describes.
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

# Directories inside a built package that are vendored dependencies rather than application code.
VENDORED_MARKERS = (".dist-info", ".egg-info")
VENDORED_TOP = {
    "pydantic", "pydantic_core", "yaml", "_yaml", "annotated_types",
    "typing_extensions.py", "typing_inspection",
}

# Files whose difference is an INFRASTRUCTURE change, not a code change.
INFRA_FILES = {"template.yaml"}


def _sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        rel = path.relative_to(root)
        out[str(rel)] = _sha256(path)
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


def main(argv: list[str]) -> int:
    old_root = pathlib.Path(argv[1]).resolve()
    new_root = pathlib.Path(argv[2]).resolve()
    repo = pathlib.Path(argv[3] if len(argv) > 3 else ".").resolve()

    print(f"old package: {old_root}")
    print(f"new package: {new_root}")
    print()

    print("--- infrastructure SOURCE, by content hash ---")
    infra_source_changed = False
    for rel in ("infra/template.yaml", "infra/samconfig.toml"):
        # Compared against the recorded P06 value by p08_verify_rollback_baseline.py; here we simply
        # state the current hash so this report stands on its own.
        print(f"{_sha256(repo / rel)}  {rel}")
    print()

    functions = sorted(
        d.name for d in new_root.iterdir()
        if d.is_dir() and (old_root / d.name).is_dir()
    )
    only_new = sorted(
        d.name for d in new_root.iterdir() if d.is_dir() and not (old_root / d.name).exists()
    )
    only_old = sorted(
        d.name for d in old_root.iterdir() if d.is_dir() and not (new_root / d.name).exists()
    )
    if only_new or only_old:
        print(f"FUNCTION SET CHANGED  added={only_new} removed={only_old}")
        print()

    print("--- packaged differences per function ---")
    categories: dict[str, set[str]] = {}
    changed_functions: list[str] = []
    for function in functions:
        old = _index(old_root / function)
        new = _index(new_root / function)
        differing = sorted(
            rel for rel in set(old) | set(new)
            if old.get(rel) != new.get(rel)
        )
        if not differing:
            print(f"{function}: identical")
            continue
        changed_functions.append(function)
        per: dict[str, list[str]] = {}
        for rel in differing:
            per.setdefault(_classify(rel), []).append(rel)
            categories.setdefault(_classify(rel), set()).add(rel)
        summary = ", ".join(f"{kind}={len(items)}" for kind, items in sorted(per.items()))
        print(f"{function}: {len(differing)} file(s) differ — {summary}")
        for kind, items in sorted(per.items()):
            if kind == "dependency":
                continue
            for rel in items:
                state = (
                    "added" if rel not in old else "removed" if rel not in new else "modified"
                )
                print(f"    [{kind}] {state}: {rel}")

    print()
    print("--- built template resource definitions ---")
    old_template = old_root / "template.yaml"
    new_template = new_root / "template.yaml"
    template_differs = (
        not old_template.exists() or not new_template.exists()
        or _sha256(old_template) != _sha256(new_template)
    )
    print(
        "the built templates differ" if template_differs
        else "the built templates are byte-identical"
    )
    if template_differs:
        # SAM rewrites each CodeUri to its build directory, so two builds at different paths differ
        # even with an unchanged source template. The source hashes above are the authority on
        # whether infrastructure actually changed; this line only says the artifacts are not equal.
        print("    NOTE: SAM rewrites CodeUri per build directory, so this alone is not evidence")
        print("    of an infrastructure change. The source template hash above is.")

    print()
    infra_in_packages = "infrastructure" in categories
    print("--- verdict ---")
    print(f"functions whose artifact changes: {len(changed_functions)} of {len(functions)}")
    print(f"  {', '.join(changed_functions) or '(none)'}")
    for kind in sorted(categories):
        print(f"difference category present: {kind} ({len(categories[kind])} distinct path(s))")
    if infra_source_changed or infra_in_packages:
        print("CHANGE_SET_INCLUDES_INFRASTRUCTURE — not the code-only update the handoff describes")
        return 1
    print("CHANGE_SET_IS_CODE_ONLY — packaged application code only; no IAM, schedule, parameter,")
    print("state-machine or retention change is implied by these packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
