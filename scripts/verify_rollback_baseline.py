"""Validate the archived P06 rollback baseline, and restore it only where that is safe.

Why this script exists, and what replaced what
----------------------------------------------
P07's handoff proposed copying the current working files aside before a rollback. Those files ARE
the overhaul being rolled back, so restoring them restores the thing you are trying to undo. P06
left the record that makes a real baseline possible: a per-file SHA-256 of every `src/` module it
deployed. P08 archived a tree matching that record — the useful half — but its verification PRINTED
`MISMATCH` and still exited 0, so a corrupted or wrong archive would not have stopped the sequence,
and its forward check named a temporary build directory that no longer exists.

This version fails closed. Validation happens against the archive's own bytes, BEFORE anything is
written anywhere, and the exit code is the gate.

What is checked, and what is deliberately ignored
-------------------------------------------------
  every recorded file present       a missing module is a failure, not a smaller baseline
  every recorded file identical     by content hash; an mtime cannot tell a restored file from a
                                    rewritten one
  no unexpected executable source   any `.py` in the archive that P06 did not record is a failure.
                                    An archive is only a baseline if its contents are exactly the
                                    baseline; "extra" code is the thing a rollback must not carry
  identified metadata ignored       macOS AppleDouble `._*` members, `.DS_Store` and `__MACOSX/`
                                    entries are archiving noise. They are LISTED, not silently
                                    skipped, and nothing else is ignored

Restoring
---------
`--restore-into` extracts the verified archive into a directory you name, and only after every
check above has passed. It refuses any destination inside the repository working tree: this script
must never be the thing that replaces the `src/` you are working in. Rolling the deployed stack back
is a SAM operation against a reconstructed baseline build, not an edit to your checkout.

Usage
-----
    python scripts/verify_rollback_baseline.py --archive <p06_baseline_src.tar.gz> \
        [--repo <repository-root>] [--restore-into <empty-directory>]

Exit code 0 only when the archive is a verified P06 baseline. 1 otherwise, and on 1 the release or
rollback sequence must stop rather than continue.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
import tarfile

RECORDED_IDENTITY = (
    "project-factory/outputs/open-market-discovery/runs/"
    "20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt"
)

# Archiving noise, identified by name. Nothing outside these patterns is ever ignored.
METADATA_PATTERNS = (
    re.compile(r"(^|/)\._[^/]*$"),      # macOS AppleDouble resource forks
    re.compile(r"(^|/)\.DS_Store$"),
    re.compile(r"^__MACOSX/"),
    re.compile(r"(^|/)__pycache__/"),
)

EXECUTABLE_SUFFIXES = {".py", ".sh", ".pyc", ".so"}


def _is_metadata(name: str) -> bool:
    return any(pattern.search(name) for pattern in METADATA_PATTERNS)


def _recorded_hashes(record: pathlib.Path) -> tuple[dict[str, str], dict[str, str]]:
    if record.suffix == ".json":
        # A baseline manifest: every archived file is recorded, and its non-`src/` entries are the
        # template/config the working tree is compared against below.
        import json

        files = dict(json.loads(record.read_text()).get("files") or {})
        return files, {rel: digest for rel, digest in files.items() if not rel.startswith("src/")}
    text = record.read_text()
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


def _archive_hashes(archive: pathlib.Path) -> tuple[dict[str, str], list[str]]:
    """Content hashes of every real file in the archive, plus the metadata members ignored."""
    contents: dict[str, str] = {}
    ignored: list[str] = []
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name[2:] if member.name.startswith("./") else member.name
            if _is_metadata(name):
                ignored.append(name)
                continue
            handle = tar.extractfile(member)
            if handle is None:
                ignored.append(name)
                continue
            contents[name] = hashlib.sha256(handle.read()).hexdigest()
    return contents, ignored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=pathlib.Path)
    parser.add_argument("--repo", type=pathlib.Path, default=pathlib.Path("."))
    parser.add_argument("--restore-into", type=pathlib.Path)
    parser.add_argument("--recorded-identity", type=pathlib.Path,
                        help="record to verify against (default: P06's). A JSON manifest's "
                             "`files` map is used for a baseline archived after P06")
    args = parser.parse_args(argv)

    repo = args.repo.resolve()
    archive = args.archive
    record = args.recorded_identity or pathlib.Path(RECORDED_IDENTITY)
    if not record.is_absolute():
        record = repo / record  # same resolution as the change-set gate: relative to --repo

    print("=== P06 rollback baseline verification ===")
    print(f"archive: {archive}")
    print("Validation runs against the archive's own bytes. Nothing is written before it passes.")
    print()

    if not archive.exists():
        print(f"BASELINE_UNAVAILABLE — no archive at {archive}")
        print("  A rollback with no verified baseline is not a rollback. STOP.")
        return 1
    if not record.exists():
        print(f"BASELINE_UNVERIFIABLE — no recorded identity at {record}")
        print("  Without the record made before the change there is nothing to verify against. STOP.")
        return 1

    recorded, template = _recorded_hashes(record)
    print(f"recorded identity: {record}")
    try:
        contents, ignored = _archive_hashes(archive)
    except (tarfile.TarError, OSError, EOFError) as error:
        print(f"ARCHIVE_UNREADABLE — {type(error).__name__}: {error}")
        print("  The archive could not be read end to end, so its contents are unknown. STOP.")
        return 1

    missing = sorted(rel for rel in recorded if rel not in contents)
    differing = sorted(
        rel for rel, want in recorded.items()
        if rel in contents and contents[rel] != want
    )
    unexpected = sorted(set(contents) - set(recorded))
    unexpected_executable = [
        rel for rel in unexpected if pathlib.PurePath(rel).suffix in EXECUTABLE_SUFFIXES
    ]

    print(f"recorded P06 source files:      {len(recorded)}")
    print(f"archive members checked:        {len(contents)}")
    print(f"identified metadata ignored:    {len(ignored)}")
    for name in ignored[:5]:
        print(f"    ignored (metadata): {name}")
    if len(ignored) > 5:
        print(f"    … and {len(ignored) - 5} more identified metadata members")
    print()

    for label, rows in (("MISSING", missing), ("DIFFERS", differing),
                        ("UNEXPECTED EXECUTABLE SOURCE", unexpected_executable),
                        ("unexpected non-executable member", [
                            r for r in unexpected if r not in unexpected_executable])):
        if rows:
            print(f"--- {label}: {len(rows)} ---")
            for rel in rows[:20]:
                print(f"    {rel}")
            if len(rows) > 20:
                print(f"    … and {len(rows) - 20} more")
            print()

    print("--- current working-tree template/config vs P06 recorded ---")
    for rel, want in sorted(template.items()):
        path = repo / rel
        have = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "(absent)"
        print(f"{'SAME   ' if have == want else 'CHANGED'} {rel}")
    print()

    fatal = bool(missing or differing or unexpected_executable)
    if fatal:
        print("BASELINE_NOT_VERIFIED — the archive is not an exact P06 source baseline.")
        print("  Restoring or deploying from it is refused. STOP before the restore step.")
        return 1

    print(f"BASELINE_VERIFIED — all {len(recorded)} recorded P06 source files are present and")
    print("  identical in the archive, and it carries no unexpected executable source.")

    if args.restore_into is not None:
        target = args.restore_into.resolve()
        if target == repo or repo in target.parents or target in repo.parents:
            print()
            print(f"RESTORE_REFUSED — {target} is inside (or contains) the repository at {repo}.")
            print("  This script never replaces the working tree's source. Restore to a scratch")
            print("  directory and build the rollback package from there.")
            return 1
        if target.exists() and any(target.iterdir()):
            print()
            print(f"RESTORE_REFUSED — {target} is not empty; refusing to overwrite it.")
            return 1
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if not _is_metadata(m.name)]
            for member in members:
                if member.name.startswith("/") or ".." in pathlib.PurePath(member.name).parts:
                    print(f"RESTORE_REFUSED — unsafe member path {member.name!r}")
                    return 1
            tar.extractall(target, members=members, filter="data")
        print()
        print(f"RESTORED — verified baseline extracted to {target}")
        print("  The repository working tree was not touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
