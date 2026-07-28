---
name: solo-template-bootstrap
description: Bootstrap a new workspace from drbretto's local solo template. Use when asked to create/start/init a new project from your template or to apply the standard solo-template guardrails without repeatedly supplying a URL.
---

# Solo Template Bootstrap

## Workflow

1. Resolve target directory.
- Default to current workspace root.
- Use user-provided path if given.
2. Resolve template directory.
- Use `SOLO_TEMPLATE_DIR` if set.
- Otherwise use `/Users/drbretto/Desktop/Projects/solo-template`.
3. Perform safety checks.
- If target is non-empty, require explicit overwrite/merge intent (`--force`).
4. Execute bootstrap.
- Run `scripts/bootstrap.sh --template <template> --target <target> [--force]` from this skill directory.
5. Verify result.
- Confirm `CLAUDE.md`, `.cursorrules`, `AGENTS.md`, and `README.md` exist in target.
6. Optional setup.
- If requested, run `make setup` in target.
