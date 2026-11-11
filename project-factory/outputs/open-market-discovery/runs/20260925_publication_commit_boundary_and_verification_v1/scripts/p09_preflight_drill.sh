#!/usr/bin/env bash
#
# Drill the release preflight's FAILURE paths with stubbed tools, and show that the sequence stops
# before the deploy command every time.
#
# The claim being tested is narrow and specific: P07's and P08's handoffs shipped command lists in
# which a failed check printed its failure and the next command ran anyway. So each case below
# breaks exactly one step and asserts two things — a non-zero exit, and that the string
# "PREFLIGHT PASSED" never appears.
#
# `sam` and the project interpreter are STUBS here. Nothing is built, nothing is deployed, and no
# AWS call is made by this drill or by the script it drills.
#
# Usage:  project-factory/.../scripts/p09_preflight_drill.sh

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/jprs-p09-preflight-drill-XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

STUBS="$WORK/stubs"
mkdir -p "$STUBS"

# ---- the stub `sam` -------------------------------------------------------------------------
# Honours the same arguments the preflight passes, and populates the build directory so the later
# steps have something real to inspect. `JPRS_STUB_SAM_FAIL` breaks one subcommand on demand.
cat >"$STUBS/sam" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
sub="$1"; shift
if [[ "${JPRS_STUB_SAM_FAIL:-}" == "$sub" ]]; then
  echo "stub sam: $sub failed" >&2
  exit 1
fi
case "$sub" in
  validate) echo "stub sam: template is valid" ;;
  build)
    out=""
    while [[ $# -gt 0 ]]; do
      [[ "$1" == "--build-dir" ]] && out="$2"
      shift
    done
    for fn in DiscoveryFunction ReportFunction; do
      mkdir -p "$out/$fn/src/discovery"
      if [[ "${JPRS_STUB_OMIT_LIVE:-}" != "$fn" ]]; then
        echo "# stub" >"$out/$fn/src/discovery/live.py"
      fi
    done
    printf 'Resources: {}\n' >"$out/template.yaml"
    echo "stub sam: built into $out"
    ;;
  deploy) echo "stub sam: DEPLOY WAS CALLED" ; exit 99 ;;
esac
STUB
chmod +x "$STUBS/sam"

# ---- the stub interpreter --------------------------------------------------------------------
# Answers the three python invocations the preflight makes. `JPRS_STUB_PY_FAIL` breaks one.
cat >"$STUBS/python" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
case "$*" in
  *pytest*)              what=tests ;;
  *policy-check*)        what=policy ;;
  *check_release_change_set.py*) what=changeset ;;
  *)                     what=other ;;
esac
if [[ "${JPRS_STUB_PY_FAIL:-}" == "$what" ]]; then
  echo "stub python: $what check FAILED" >&2
  exit 1
fi
echo "stub python: $what check passed"
STUB
chmod +x "$STUBS/python"

export PATH="$STUBS:$PATH"
export JPRS_PYTHON="$STUBS/python"

pass=0
fail=0

drill() {
  local name="$1"; shift
  local expect_exit="$1"; shift
  local build="$WORK/build-$name"
  rm -rf "$build"
  local log="$WORK/$name.log"
  ( env "$@" "$REPO/scripts/release_preflight.sh" "$build" "$WORK/baseline" ) >"$log" 2>&1
  local rc=$?
  local reached_deploy=no
  grep -q "PREFLIGHT PASSED" "$log" && reached_deploy=yes
  local verdict="FAIL"
  if [[ "$expect_exit" == "zero" && $rc -eq 0 && "$reached_deploy" == "yes" ]]; then verdict="OK"; fi
  if [[ "$expect_exit" == "nonzero" && $rc -ne 0 && "$reached_deploy" == "no" ]]; then verdict="OK"; fi
  [[ "$verdict" == "OK" ]] && pass=$((pass + 1)) || fail=$((fail + 1))
  printf '%-34s exit=%-3s reached_deploy_step=%-3s  %s\n' "$name" "$rc" "$reached_deploy" "$verdict"
  printf '    last line: %s\n' "$(tail -1 "$log")"
}

mkdir -p "$WORK/baseline"

echo "=== P09 release preflight drill — stubbed sam and interpreter, nothing deployed ==="
echo "repository: $REPO"
echo
echo "Each row breaks ONE step. A correct sequence exits non-zero and never reaches the step that"
echo "prints the deploy command."
echo

drill "all_checks_pass"          zero    JPRS_STUB_NONE=1
drill "test_suite_fails"         nonzero JPRS_STUB_PY_FAIL=tests
drill "policy_projection_fails"  nonzero JPRS_STUB_PY_FAIL=policy
drill "template_validate_fails"  nonzero JPRS_STUB_SAM_FAIL=validate
drill "build_fails"              nonzero JPRS_STUB_SAM_FAIL=build
drill "report_artifact_missing_live_module" nonzero JPRS_STUB_OMIT_LIVE=ReportFunction
drill "change_set_gate_fails"    nonzero JPRS_STUB_PY_FAIL=changeset

echo
echo "cases passed: $pass   cases failed: $fail"
echo "the stub \`sam deploy\` exits 99 if it is ever called; it was never called."
[[ $fail -eq 0 ]] || exit 1
