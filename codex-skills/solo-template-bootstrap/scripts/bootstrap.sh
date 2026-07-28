#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./bootstrap.sh [--template <path>] [--target <path>] [--force]
USAGE
}

TARGET_DIR="$(pwd)"
TEMPLATE_DIR="${SOLO_TEMPLATE_DIR:-/Users/drbretto/Desktop/Projects/solo-template}"
FORCE=0

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
  echo "Template directory does not look like the expected solo template: $TEMPLATE_DIR" >&2
  exit 1
fi

if [[ -n "$(find "$TARGET_DIR" -mindepth 1 -maxdepth 1 -not -name '.DS_Store' -print -quit)" && "$FORCE" -ne 1 ]]; then
  echo "Target directory is not empty: $TARGET_DIR" >&2
  echo "Re-run with --force to allow bootstrapping into a non-empty directory." >&2
  exit 1
fi

rsync -a \
  --exclude='.git' \
  --exclude='.DS_Store' \
  --exclude='.Spotlight-V100' \
  --exclude='.Trashes' \
  "$TEMPLATE_DIR/" "$TARGET_DIR/"

echo "Bootstrapped project from template."
echo "Template: $TEMPLATE_DIR"
echo "Target:   $TARGET_DIR"
