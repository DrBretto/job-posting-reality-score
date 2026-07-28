# 2026-02-17 - Codex Guardrails and MCP Sync

## Context

Add Codex-specific project instructions aligned with existing `CLAUDE.md` and `.cursorrules`, and reduce MCP setup overhead by syncing existing Claude/Cursor MCP server definitions into OpenAI Chat/Codex desktop config.

## Plan

- [x] Audit existing guardrail files (`CLAUDE.md`, `.cursorrules`, repo docs).
- [x] Create a root `AGENTS.md` for Codex with the same operational guardrails.
- [x] Update project docs to include Codex guardrail files.
- [x] Build a reusable MCP sync script for future use.
- [x] Merge missing MCP servers from Cursor/Claude into OpenAI Chat/Codex MCP config with backup.
- [x] Validate script behavior with a dry run.

## Execution Log

- Reviewed `CLAUDE.md`, `.cursorrules`, and supporting docs to preserve existing workflow constraints.
- Added `AGENTS.md` as Codex-facing instructions that inherit canonical rules from `CLAUDE.md`.
- Updated `README.md` and `CONTRIBUTING.md` so Codex instructions are documented alongside Claude/Cursor guidance.
- Added `scripts/sync_mcp_to_openai_chat.sh` and `make sync-mcp` target to automate future MCP server merges.
- Merged missing MCP servers into `~/Library/Application Support/com.openai.chat/mcp.json` and created a timestamped backup.
- Verified merge script via `--dry-run` and shell syntax checks.

## Follow-ups

- If new MCP servers are added in Claude/Cursor later, run `make sync-mcp` (or the script directly) to refresh Codex/OpenAI config.
- Restart OpenAI Chat/Codex desktop app if newly added MCP servers do not appear immediately.
