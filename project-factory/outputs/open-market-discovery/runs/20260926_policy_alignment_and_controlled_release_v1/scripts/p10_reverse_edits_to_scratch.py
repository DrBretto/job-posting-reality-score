"""Build a scratch copy of the tree with THIS run's source edits reversed, and nothing else changed.

Why: a regression that passes proves nothing about whether the behavior is new. The packet requires
the new defect regressions to be demonstrated failing against pre-P10 behavior. `src/candidate/` is
untracked in this repository, so there is no committed baseline to check out — the pre-P10 source is
reconstructed here by removing exactly the regions this run added, by their own delimiters, and
failing loudly if any region is not found.

The working checkout is never modified. Everything happens under the scratch directory.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[6]

# (file, start marker, end marker) — the end marker is preserved, the start marker is removed.
CUT_REGIONS: tuple[tuple[str, str, str], ...] = (
    (
        "src/candidate/screening.py",
        "# ---- external customer service / call-center work ---",
        "# ---- location ---",
    ),
    (
        "src/candidate/screening.py",
        "@dataclass\nclass QueueDuty:",
        "def screen_job(job: CanonicalJob) -> ScreenResult:",
    ),
    (
        "src/candidate/screening.py",
        "    # ---- 6. external customer service / call-center work ---",
        "    # ---- 7. location eligibility from New Hampshire ---",
    ),
)

REPLACEMENTS: tuple[tuple[str, str, str], ...] = (
    ("src/candidate/screening.py", 'SCREENING_RULESET_VERSION = "1.5.0"',
     'SCREENING_RULESET_VERSION = "1.4.0"'),
    ("src/candidate/screening.py", "    # ---- 7. location eligibility",
     "    # ---- 6. location eligibility"),
    ("src/candidate/screening.py", "    # ---- 8. can we even see the process?",
     "    # ---- 7. can we even see the process?"),
    ("src/candidate/policy.py", 'PROJECTION_VERSION = "1.1.0"', 'PROJECTION_VERSION = "1.0.0"'),
)

# The rule-map entry plus its three comment lines.
POLICY_RULE_BLOCK = re.compile(
    r"\n    # 2026-09-26: \"Adjacent roles.*?\n    \"customer-service-queue\": \([^)]*\),",
    re.S,
)


def build(dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in ("src", "tests", "config", "pyproject.toml", "conftest.py"):
        src = REPO_ROOT / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest / name,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, dest / name)

    for rel, start, end in CUT_REGIONS:
        path = dest / rel
        text = path.read_text()
        i = text.find(start)
        j = text.find(end, i + 1) if i >= 0 else -1
        if i < 0 or j < 0:
            raise SystemExit(f"FAILED to locate region in {rel}: {start!r} .. {end!r}")
        path.write_text(text[:i] + text[j:])

    for rel, old, new in REPLACEMENTS:
        path = dest / rel
        text = path.read_text()
        if old not in text:
            raise SystemExit(f"FAILED to locate {old!r} in {rel}")
        path.write_text(text.replace(old, new))

    policy = dest / "src/candidate/policy.py"
    text = policy.read_text()
    if not POLICY_RULE_BLOCK.search(text):
        raise SystemExit("FAILED to locate the customer-service-queue rule-map entry")
    policy.write_text(POLICY_RULE_BLOCK.sub("", text))

    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    ap.add_argument("--run-tests", action="store_true")
    args = ap.parse_args()
    dest = build(Path(args.dest))
    print(f"pre-P10 scratch tree at {dest}")
    if args.run_tests:
        proc = subprocess.run(
            [str(REPO_ROOT / ".venv/bin/pytest"), "-q", "-p", "no:cacheprovider",
             "tests/test_adjacent_roles_and_customer_service.py"],
            cwd=dest, capture_output=True, text=True,
        )
        sys.stdout.write(proc.stdout)
        sys.stdout.write(proc.stderr)
        print(f"pytest exit={proc.returncode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
