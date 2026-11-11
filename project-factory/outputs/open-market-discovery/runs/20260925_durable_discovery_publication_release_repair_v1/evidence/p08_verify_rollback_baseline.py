"""Verify a candidate P06 rollback baseline against P06's OWN recorded source hashes.

Why this script exists
----------------------
P07's handoff proposed copying the current working files aside before a rollback. Those files are the
P07/P08 overhaul, so restoring them restores the thing being rolled back. A baseline is only a
baseline if its identity can be checked against a record made BEFORE the change — and P06 left exactly
that record: a per-file SHA-256 of every `src/` module it deployed.

So this compares a candidate build tree, file by file, against those recorded hashes. It reports
MATCHES only when every recorded file is present and identical in that function's package. Content
hashes, never modification times: an mtime comparison cannot distinguish a restored file from a
rewritten one, and P07's review named that specifically.

Usage:  python p08_verify_rollback_baseline.py <candidate-build-dir> [repo-root]
Exit code 0 means the candidate is a verified P06 baseline; 1 means it is not, and the release
condition that depends on it is unmet.
"""

from __future__ import annotations

import hashlib
import pathlib
import re
import sys

RECORDED = (
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt"
)


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _recorded_hashes(repo: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    text = (repo / RECORDED).read_text()
    source: dict[str, str] = {}
    template: dict[str, str] = {}
    section = None
    for line in text.splitlines():
        if line.startswith("--- owned source hashes"):
            section = "src"
            continue
        if line.startswith("--- template + config"):
            section = "tpl"
            continue
        match = re.match(r"^([0-9a-f]{64})\s+(\S+)$", line.strip())
        if not match:
            continue
        if section == "src":
            source[match.group(2)] = match.group(1)
        elif section == "tpl":
            template[match.group(2)] = match.group(1)
    return source, template


def main(argv: list[str]) -> int:
    build = pathlib.Path(argv[1]).resolve()
    repo = pathlib.Path(argv[2] if len(argv) > 2 else ".").resolve()
    source, template = _recorded_hashes(repo)

    functions = sorted(d.name for d in build.iterdir() if d.is_dir())
    print(f"candidate build: {build}")
    print(f"functions present: {', '.join(functions) or '(none)'}")
    print(f"recorded P06 source files: {len(source)}")
    print()

    verified: list[str] = []
    for function in functions:
        root = build / function
        matched = missing = differing = 0
        detail: list[str] = []
        for rel, want in sorted(source.items()):
            candidate = root / rel
            if not candidate.exists():
                missing += 1
                detail.append(f"MISSING {rel}")
            elif _sha256(candidate) == want:
                matched += 1
            else:
                differing += 1
                detail.append(f"DIFFERS {rel}")
        ok = differing == 0 and missing == 0
        if ok:
            verified.append(function)
        print(
            f"{function}: {'MATCHES P06' if ok else 'DOES NOT MATCH'} "
            f"(matched={matched} differing={differing} missing={missing})"
        )
        for line in detail[:10]:
            print(f"    {line}")
    print()

    shipped = build / "template.yaml"
    if shipped.exists():
        print("--- template inside the candidate build ---")
        print(f"{_sha256(shipped)}  {shipped}")
        print("    SAM rewrites CodeUri when it builds, so this hash is deliberately NOT compared")
        print("    against the recorded source-template hash; the source template is checked below.")
        print()

    print("--- current working-tree template/config vs P06 recorded ---")
    for rel, want in sorted(template.items()):
        have = _sha256(repo / rel)
        print(f"{'SAME   ' if have == want else 'CHANGED'} {rel}")
        print(f"        recorded {want}")
        print(f"        current  {have}")
    print()

    if verified and len(verified) == len(functions):
        print(f"BASELINE_VERIFIED — every packaged function matches P06 ({len(functions)} functions)")
        return 0
    if verified:
        print(f"BASELINE_PARTIAL — only {', '.join(verified)} match P06; treat as unverified")
        return 1
    print("BASELINE_NOT_VERIFIED — no packaged function matches P06's recorded source")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
