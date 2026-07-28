#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/install_codex_bootstrap_skill.sh [--name <skill-name>]

Install the bundled Codex skill for template bootstrapping into ~/.codex/skills.

Options:
  --name <skill-name>  Destination skill name (default: solo-template-bootstrap)
  -h, --help           Show help
EOF
}

SKILL_NAME="solo-template-bootstrap"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      [[ $# -ge 2 ]] || { echo "Missing value for --name" >&2; exit 1; }
      SKILL_NAME="$2"
      shift 2
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
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/codex-skills/solo-template-bootstrap"
DEST_DIR="${HOME}/.codex/skills/${SKILL_NAME}"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Bundled skill not found: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "${HOME}/.codex/skills"
mkdir -p "$DEST_DIR"
rsync -a "$SOURCE_DIR/" "$DEST_DIR/"
chmod +x "$DEST_DIR/scripts/bootstrap.sh"

echo "Installed Codex skill: ${DEST_DIR}"
echo "Skill trigger: solo-template-bootstrap"
