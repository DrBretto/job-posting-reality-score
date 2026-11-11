#!/usr/bin/env bash
#
# Everything that must pass BEFORE a rollback to P06, in one fail-fast sequence. Deploys nothing,
# and never touches the working tree's `src/`.
#
# Why the shape is different from P08's
# --------------------------------------
# P08's rollback block replaced the checkout's `src/` in place and verified the result AFTER the
# replacement, with a check that printed `MISMATCH` and still exited 0. So a corrupt or wrong
# archive would have left a hybrid tree and continued into a deploy. Here the archive is verified
# first, the restore happens in a scratch directory, and the rollback package is BUILT from that
# scratch tree — the checkout is never a participant and there is nothing to put back afterwards.
#
# Usage:  scripts/rollback_preflight.sh <scratch-directory>
#
# The scratch directory must be outside the repository. On success it holds a P06 build ready to
# deploy, and the command to deploy it is printed but not run.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${JPRS_PYTHON:-${REPO}/.venv/bin/python}"
ARCHIVE="${REPO}/project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p06_baseline_src.tar.gz"
SAMCONFIG="${REPO}/infra/samconfig.toml"

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <scratch-directory>" >&2
  exit 2
fi
WORK="$1"

step() { printf '\n=== %s ===\n' "$1"; }

step "1. verify the persisted baseline archive before anything is written"
"$PYTHON" "${REPO}/scripts/verify_rollback_baseline.py" --archive "$ARCHIVE" --repo "$REPO"

step "2. reconstruct the P06 build in scratch"
"${REPO}/scripts/reconstruct_p06_baseline_build.sh" "$WORK"

step "3. the reconstructed tree is P06, not a P06/P09 hybrid"
# P06 has no `src/discovery/live.py`: that module is P07's. Its ABSENCE is the check appropriate to
# this baseline, and a hybrid tree is the specific failure an in-place restore produces.
test ! -e "$WORK/tree/src/discovery/live.py"
test -f "$WORK/tree/src/discovery/handler.py"
echo "OK: the restored tree is the deployed P06 shape"

step "4. the working checkout was not a participant"
test -f "${REPO}/src/discovery/live.py"
echo "OK: the overhaul is still in place at ${REPO}/src"

step "ROLLBACK PREFLIGHT PASSED — nothing has been deployed"
cat <<EOF

Before deploying this rollback, read the latest coverage receipt's \`pending_publication\`:

  aws s3 cp "s3://\$BUCKET/discovery/run=\$DT/coverage.json" - | \\
    "$PYTHON" -c 'import json,sys; print(json.load(sys.stdin).get("pending_publication"))'

If it is non-empty, P06 will never drain those observations — it has no live view and no owed
ledger — and the postings named there are lost from the automatic path. Let one more discovery
round publish them first if they matter.

Then deploy the reconstructed baseline:

  sam deploy \\
    --template-file "$WORK/build/template.yaml" \\
    --config-file "$SAMCONFIG" \\
    --config-env default

An August-era rollback is a different and larger operation: the P05 handoff §6 still controls and
its \`downgrade-state\` step is still required. This sequence reverts P07-P09 source only.
EOF
