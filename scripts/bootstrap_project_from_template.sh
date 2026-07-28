#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap_project_from_template.sh [options]

Initialize a target directory from the solo template.

Options:
  --target <path>      Target directory to populate (default: current directory)
  --template <path>    Template source directory (default: SOLO_TEMPLATE_DIR or script repo root)
  --force              Allow bootstrap into a non-empty target directory
  -h, --help           Show help

Environment:
  SOLO_TEMPLATE_DIR    Default template directory if --template is not set

Notes:
  - Copies all template files except .git and common macOS artifacts.
  - Does not overwrite your target .git directory (if one already exists).
EOF
}

TARGET_DIR="$(pwd)"
FORCE=0
TEMPLATE_DIR="${SOLO_TEMPLATE_DIR:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      [[ $# -ge 2 ]] || { echo "Missing value for --target" >&2; exit 1; }
      TARGET_DIR="$2"
      shift 2
      ;;
    --template)
      [[ $# -ge 2 ]] || { echo "Missing value for --template" >&2; exit 1; }
      TEMPLATE_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_DIR="${TEMPLATE_DIR:-$DEFAULT_TEMPLATE_DIR}"

mkdir -p "$TARGET_DIR"

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "Template directory does not exist: $TEMPLATE_DIR" >&2
  exit 1
fi

if [[ "$TARGET_DIR" == "$TEMPLATE_DIR" ]]; then
  echo "Target directory cannot be the template directory itself." >&2
  exit 1
fi

if [[ ! -f "$TEMPLATE_DIR/CLAUDE.md" || ! -f "$TEMPLATE_DIR/.cursorrules" ]]; then
  echo "Template directory does not look like a valid solo template: $TEMPLATE_DIR" >&2
  exit 1
fi

if [[ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -not -name '.DS_Store' -print -quit)" && "$FORCE" -ne 1 ]]; then
  echo "Target directory is not empty: $TARGET_DIR" >&2
  echo "Re-run with --force to allow bootstrapping into a non-empty directory." >&2
  exit 1
fi

RSYNC_EXCLUDES=(
  "--exclude=.git"
  "--exclude=.DS_Store"
  "--exclude=.Spotlight-V100"
  "--exclude=.Trashes"
)

if [[ -d "$TARGET_DIR/.git" ]]; then
  RSYNC_EXCLUDES+=("--exclude=.git/")
fi

rsync -a "${RSYNC_EXCLUDES[@]}" "$TEMPLATE_DIR/" "$TARGET_DIR/"

echo "Bootstrapped project from template."
echo "Template: $TEMPLATE_DIR"
echo "Target:   $TARGET_DIR"
