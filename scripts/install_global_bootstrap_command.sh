#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/install_global_bootstrap_command.sh [--command <name>]

Install a global command that bootstraps projects from this template.

Options:
  --command <name>   Command name to install (default: solo-new)
  -h, --help         Show help

The installed command:
  - Resolves this template path once at install time
  - Runs bootstrap_project_from_template.sh with that template path
EOF
}

COMMAND_NAME="solo-new"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --command)
      [[ $# -ge 2 ]] || { echo "Missing value for --command" >&2; exit 1; }
      COMMAND_NAME="$2"
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
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BOOTSTRAP_SCRIPT="${TEMPLATE_DIR}/scripts/bootstrap_project_from_template.sh"

if [[ ! -x "$BOOTSTRAP_SCRIPT" ]]; then
  echo "Bootstrap script not found or not executable: $BOOTSTRAP_SCRIPT" >&2
  exit 1
fi

INSTALL_DIR="${HOME}/.local/bin"
INSTALL_PATH="${INSTALL_DIR}/${COMMAND_NAME}"
mkdir -p "$INSTALL_DIR"

cat > "$INSTALL_PATH" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SOLO_TEMPLATE_DIR="${TEMPLATE_DIR}" exec "${BOOTSTRAP_SCRIPT}" "\$@"
EOF

chmod +x "$INSTALL_PATH"

echo "Installed command: ${INSTALL_PATH}"
echo "Usage example:"
echo "  mkdir -p ~/Desktop/Projects/my-new-project"
echo "  ${COMMAND_NAME} --target ~/Desktop/Projects/my-new-project"

if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
  echo
  echo "PATH note: ${INSTALL_DIR} is not currently in PATH."
  echo "Add this to your shell profile:"
  echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
fi
