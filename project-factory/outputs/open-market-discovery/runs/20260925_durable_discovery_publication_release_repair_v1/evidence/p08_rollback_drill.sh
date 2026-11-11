#!/usr/bin/env bash
# Rollback drill — prove the recovery steps work BEFORE they are ever needed.
#
# What this drills, and why it is a drill and not a rehearsal in the working tree
# ------------------------------------------------------------------------------
# The rollback in DEPLOYMENT_HANDOFF.md restores P06's source over the current overhaul. Running that
# for real against the working tree would put the uncommitted P01-P08 work at risk for the sake of a
# test, and the overhaul is not in Git. So the drill copies the working tree's `src/` into a scratch
# directory and performs the whole round trip there:
#
#   1. preserve   — copy the current overhaul aside, as step R-1 of the handoff does
#   2. restore    — extract the hash-verified P06 baseline over the scratch tree
#   3. verify     — every one of the 36 recorded P06 files matches its recorded SHA-256
#   4. return     — restore the preserved overhaul and prove it is byte-identical to what we started
#                   with, because a rollback that cannot be undone is a one-way door
#
# It contacts no AWS, deploys nothing, and does not touch the real `src/`.
#
# Usage: bash p08_rollback_drill.sh [repo-root]
set -uo pipefail

REPO="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)}"
RUN="$REPO/project-factory/outputs/open-market-discovery/runs/20260925_durable_discovery_publication_release_repair_v1"
BASELINE="$RUN/evidence/p06_baseline_src.tar.gz"
RECORDED="$REPO/project-factory/outputs/open-market-discovery/runs/20260925_controlled_discovery_deployment_v1/evidence/p06_build_identity.txt"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/p08-rollback-drill-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

echo "=== rollback drill ==="
echo "repo:     $REPO"
echo "baseline: $BASELINE"
echo "scratch:  $WORK"
echo

fail=0

echo "--- 1. preserve the current overhaul (handoff step R-1) ---"
mkdir -p "$WORK/tree" "$WORK/preserved"
( cd "$REPO" && find src -name '__pycache__' -prune -o -type f -name '*.py' -print | sort \
    | tar -cf - -T - ) | ( cd "$WORK/tree" && tar -xf - )
cp -R "$WORK/tree/src" "$WORK/preserved/src"
before="$(cd "$WORK/tree" && find src -type f -name '*.py' | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
echo "current overhaul preserved; aggregate digest $before"
echo

echo "--- 2. restore the verified P06 baseline over it (handoff step R-3) ---"
# `src/` is REPLACED rather than merged: a module P07 added and P06 never had must disappear, or the
# restored tree is a hybrid that was never deployed and never tested.
rm -rf "$WORK/tree/src"
tar -xzf "$BASELINE" -C "$WORK/tree"
restored_count="$(cd "$WORK/tree" && find src -type f -name '*.py' | wc -l | tr -d ' ')"
echo "restored $restored_count python file(s)"
if [ -e "$WORK/tree/src/discovery/live.py" ]; then
  echo "FAIL: src/discovery/live.py survived the restore; the tree is a P06/P08 hybrid"
  fail=1
else
  echo "ok: the module P07 added is absent, as it is in P06"
fi
echo

echo "--- 3. verify every restored file against P06's recorded SHA-256 ---"
matched=0; differing=0; missing=0
while read -r want rel; do
  case "$rel" in src/*) ;; *) continue ;; esac
  if [ ! -f "$WORK/tree/$rel" ]; then
    echo "MISSING $rel"; missing=$((missing+1)); continue
  fi
  have="$(shasum -a 256 "$WORK/tree/$rel" | cut -d' ' -f1)"
  if [ "$have" = "$want" ]; then
    matched=$((matched+1))
  else
    echo "DIFFERS $rel"; differing=$((differing+1))
  fi
done < <(sed -n '/--- owned source hashes/,/--- template + config/p' "$RECORDED" \
          | grep -E '^[0-9a-f]{64} ' | awk '{print $1, $2}')
echo "matched=$matched differing=$differing missing=$missing"
[ "$differing" -eq 0 ] && [ "$missing" -eq 0 ] && [ "$matched" -gt 0 ] || fail=1
echo

echo "--- 4. return to the overhaul, and prove it came back intact (handoff step R-6) ---"
rm -rf "$WORK/tree/src"
cp -R "$WORK/preserved/src" "$WORK/tree/src"
after="$(cd "$WORK/tree" && find src -type f -name '*.py' | sort | xargs shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
echo "aggregate digest after return: $after"
if [ "$before" = "$after" ]; then
  echo "ok: the overhaul is byte-identical to its pre-drill state; the rollback is reversible"
else
  echo "FAIL: the overhaul did not return intact"
  fail=1
fi
echo

if [ "$fail" -eq 0 ]; then
  echo "DRILL_PASSED — the recorded rollback restores a hash-verified P06 source tree and reverses cleanly"
else
  echo "DRILL_FAILED — the rollback steps are NOT safe to follow as written"
fi
exit "$fail"
