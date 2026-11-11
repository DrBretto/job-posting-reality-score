#!/usr/bin/env bash
#
# Everything that must pass BEFORE a deploy, in one fail-fast sequence. Deploys nothing.
#
# Why this is a script and not a list in a document
# --------------------------------------------------
# P07's and P08's handoffs shipped command lists in which a failed check PRINTED its failure and the
# next command ran anyway — `&&`-chained `echo`s, an uninitialized shell variable used to build an
# argument list, and a package check that exited 0 on an infrastructure change. A list of commands
# cannot fail closed; a script with `set -euo pipefail` can, and it can be exercised against a
# broken checker to prove it stops (see `project-factory/outputs/.../p09_release_preflight_drill.txt`).
#
# The final step prints the deploy command. It does not run it. Deployment stays an explicit,
# separate, operator action against a build this script has already verified.
#
# Usage:  scripts/release_preflight.sh <candidate-build-dir> <baseline-build-dir> \
#                                      [<recorded-identity> <declared-delta.json>]
#
# The baseline build is produced by `scripts/reconstruct_p06_baseline_build.sh`, which rebuilds it
# from the verified persisted archive. Do not point this at a temporary directory from an earlier
# session and hope it survived.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

if [[ $# -ne 2 && $# -ne 4 ]]; then
  echo "usage: $0 <candidate-build-dir> <baseline-build-dir> [<recorded-identity> <declared-delta.json>]" >&2
  exit 2
fi

BUILD="$1"
BASELINE="$2"
# Optional: the record of the version live NOW and the exact infrastructure delta this release
# declares. Without them the gate compares against P06 and accepts code-only changes only.
GATE_ARGS=()
if [[ $# -eq 4 ]]; then
  GATE_ARGS=(--recorded-identity "$3" --declared-delta "$4")
fi
# The project interpreter. Overridable so the failure paths of this sequence can be drilled
# against stubbed tools (see the P09 preflight drill); it selects an interpreter, it does not
# skip a step.
PYTHON="${JPRS_PYTHON:-${REPO}/.venv/bin/python}"
TEMPLATE="${REPO}/infra/template.yaml"
SAMCONFIG="${REPO}/infra/samconfig.toml"

step() { printf '\n=== %s ===\n' "$1"; }

step "0. the checkout is the overhaul, and stays uncommitted"
git status --short | head -20
echo "(no reset, checkout, stash or commit is part of this sequence)"

step "1. the full test suite"
"$PYTHON" -m pytest -q -p no:cacheprovider

step "2. candidate policy projection vs its sources"
"$PYTHON" -m src.cli policy-check

step "3. template validation"
sam validate --lint --template-file "$TEMPLATE"

step "4. build the candidate, into the directory named on the command line"
sam build --template-file "$TEMPLATE" --build-dir "$BUILD"

step "5. the shipped artifacts contain the module the report imports at INVOKE time"
# `src/discovery/live` is imported by the report function. A package missing it builds cleanly and
# fails in production, so this is asserted rather than eyeballed. `test` exits non-zero and
# `set -e` stops the sequence; nothing here prints a failure and carries on.
test -f "$BUILD/DiscoveryFunction/src/discovery/live.py"
test -f "$BUILD/ReportFunction/src/discovery/live.py"
echo "OK: the live-view module is present in both function artifacts"

step "6. the change set is code-only (or code plus exactly the declared delta), against the baseline"
"$PYTHON" "${REPO}/scripts/check_release_change_set.py" \
  --baseline "$BASELINE" --candidate "$BUILD" --repo "$REPO" \
  ${GATE_ARGS[@]+"${GATE_ARGS[@]}"}

step "PREFLIGHT PASSED — nothing has been deployed"
cat <<EOF

Deploy is a separate, explicit step. Run it yourself, and review the change set AWS reports
against the local verdict above before confirming:

  sam deploy \\
    --template-file "$BUILD/template.yaml" \\
    --config-file "$SAMCONFIG" \\
    --config-env default

The three email/notification parameters are NOT in samconfig.toml and must be carried forward by
CloudFormation as previous values. Do not retype them and do not print them.
EOF
