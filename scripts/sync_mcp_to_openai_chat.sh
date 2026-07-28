#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/sync_mcp_to_openai_chat.sh [--dry-run]

Merges MCP servers from:
  - Cursor: ~/.cursor/mcp.json
  - Claude: ~/Library/Application Support/Claude/claude_desktop_config.json
into:
  - OpenAI Chat/Codex: ~/Library/Application Support/com.openai.chat/mcp.json

Behavior:
  - Existing target servers are never overwritten.
  - Missing servers are appended from Cursor/Claude.
  - Claude's "AbletonMCP" alias is ignored to avoid duplicate Ableton entries.
  - A timestamped backup is created before writing.

Overrides:
  CURSOR_MCP_FILE, CLAUDE_MCP_FILE, OPENAI_MCP_FILE
EOF
}

DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 1
      ;;
  esac
done

CURSOR_MCP_FILE="${CURSOR_MCP_FILE:-$HOME/.cursor/mcp.json}"
CLAUDE_MCP_FILE="${CLAUDE_MCP_FILE:-$HOME/Library/Application Support/Claude/claude_desktop_config.json}"
OPENAI_MCP_FILE="${OPENAI_MCP_FILE:-$HOME/Library/Application Support/com.openai.chat/mcp.json}"

for file in "$CURSOR_MCP_FILE" "$CLAUDE_MCP_FILE" "$OPENAI_MCP_FILE"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file" >&2
    exit 1
  fi
done

tmp="$(mktemp)"
jq -s '
  def servers: .mcpServers // {};
  .[0] as $target |
  (.[1] | servers) as $cursor |
  (.[2] | servers | del(.AbletonMCP)) as $claude |
  ($target.mcpServers // {}) as $base |
  ($cursor + $claude) as $incoming |
  ($incoming | to_entries | map(select(.key as $k | ($base | has($k) | not))) | from_entries) as $additions |
  $target * { mcpServers: ($base + $additions) }
' "$OPENAI_MCP_FILE" "$CURSOR_MCP_FILE" "$CLAUDE_MCP_FILE" > "$tmp"

added="$(jq -s -r '((.[1].mcpServers | keys) - (.[0].mcpServers | keys))[]?' "$OPENAI_MCP_FILE" "$tmp")"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "Dry run complete. Would add:"
  if [[ -n "$added" ]]; then
    printf '%s\n' "$added"
  else
    echo "(none)"
  fi
  rm -f "$tmp"
  exit 0
fi

backup="${OPENAI_MCP_FILE}.bak-$(date +%Y%m%d-%H%M%S)"
cp "$OPENAI_MCP_FILE" "$backup"
mv "$tmp" "$OPENAI_MCP_FILE"

echo "MCP merge complete."
echo "Backup: $backup"
echo "Added servers:"
if [[ -n "$added" ]]; then
  printf '%s\n' "$added"
else
  echo "(none)"
fi
