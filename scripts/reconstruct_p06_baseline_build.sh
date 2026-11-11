#!/usr/bin/env bash
# Rebuild the deployed P06 baseline package from the VERIFIED archive, in a scratch directory.
#
# Why this exists
# ---------------
# The forward release check compares the candidate build against the build that is deployed. P08's
# handoff named a temporary directory (`/private/tmp/.../jprs-build-p06-*`) for that baseline, and
# temporary directories do not survive: a reboot, a cleanup or a different machine and the check
# silently has nothing to compare against. The persisted evidence is the verified source archive, so
# the baseline build is RECONSTRUCTED from it here rather than assumed to still be on disk.
#
# Nothing here touches the repository working tree, and nothing here calls AWS. `sam build` is a
# local packaging operation.
#
# Usage:  scripts/reconstruct_p06_baseline_build.sh <scratch-directory> [<archive> <manifest.json>]
# Exit 0 only when a baseline build exists at <scratch-directory>/build.
#
# With no archive named, the baseline is P06's. Once a later version is live, name ITS archive and
# JSON manifest instead (the 2026-09-26 recovery archived the live P10 tree that way). If that
# archive carries `infra/template.yaml`, the baseline is built from THAT template too, so an
# infrastructure change in the candidate shows up in the built-template comparison rather than
# being hidden by a baseline that silently borrowed the candidate's template.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${REPO}/project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1/evidence/p06_baseline_src.tar.gz"
IDENTITY_ARGS=()

if [[ $# -ne 1 && $# -ne 3 ]]; then
  echo "usage: $0 <scratch-directory> [<archive> <manifest.json>]" >&2
  exit 2
fi
WORK="$1"
if [[ $# -eq 3 ]]; then
  ARCHIVE="$2"
  IDENTITY_ARGS=(--recorded-identity "$3")
fi

case "${WORK}" in
  "${REPO}"|"${REPO}"/*)
    echo "REFUSED — ${WORK} is inside the repository. Use a scratch directory outside it." >&2
    exit 1
    ;;
esac

PYTHON="${REPO}/.venv/bin/python"
[[ -x "${PYTHON}" ]] || PYTHON="python3"

echo "--- 1. verify the archived baseline before anything is written ---"
"${PYTHON}" "${REPO}/scripts/verify_rollback_baseline.py" --archive "${ARCHIVE}" --repo "${REPO}" \
  ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"}

echo
echo "--- 2. assemble a P06 source tree in scratch ---"
mkdir -p "${WORK}"
# The repository shell, minus its history and build products, because every function inherits
# `CodeUri: ../` and therefore packages the whole tree. Only `src/` is replaced with P06's.
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude '.aws-sam' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude 'project-factory/outputs' \
  "${REPO}/" "${WORK}/tree/"
rm -rf "${WORK}/tree/src"
"${PYTHON}" "${REPO}/scripts/verify_rollback_baseline.py" \
  --archive "${ARCHIVE}" --repo "${REPO}" --restore-into "${WORK}/p06-src" \
  ${IDENTITY_ARGS[@]+"${IDENTITY_ARGS[@]}"} >/dev/null
cp -R "${WORK}/p06-src/src" "${WORK}/tree/src"
echo "baseline source placed at ${WORK}/tree/src"
if [[ -f "${WORK}/p06-src/infra/template.yaml" ]]; then
  cp "${WORK}/p06-src/infra/template.yaml" "${WORK}/tree/infra/template.yaml"
  echo "baseline template placed at ${WORK}/tree/infra/template.yaml"
fi
echo "NOTE: everything OUTSIDE src/ is the current tree, so the reconstructed package differs from"
echo "      the real P06 artifact in repository payload (tests, docs). Those differences are"
echo "      classified as payload, not infrastructure, by the change-set check."

echo
echo "--- 3. build it locally (no AWS call) ---"
cd "${WORK}/tree"
sam build --template infra/template.yaml --build-dir "${WORK}/build" >"${WORK}/sam_build.log" 2>&1 \
  || { echo "BASELINE_BUILD_FAILED — see ${WORK}/sam_build.log" >&2; tail -20 "${WORK}/sam_build.log" >&2; exit 1; }

echo "BASELINE_BUILD_READY — ${WORK}/build"
echo "Compare a candidate against it with:"
echo "  ${PYTHON} ${REPO}/scripts/check_release_change_set.py \\"
echo "      --baseline ${WORK}/build --candidate ${REPO}/.aws-sam/build --repo ${REPO}"
