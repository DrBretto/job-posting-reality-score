# 2026-02-17 - Centralized Template Bootstrap

## Context

Replace manual copy-based project setup with a centralized bootstrap flow that can be invoked quickly in future projects, ideally by natural language in Codex without repeatedly providing template URLs/paths.

## Plan

- [x] Add a repo bootstrap script that can initialize a target directory from this template.
- [x] Add an install script that creates a global shell command with the template path preconfigured.
- [x] Add documentation for one-command bootstrap usage in new projects.
- [x] Create/install a global Codex skill that maps natural-language requests to the bootstrap workflow.
- [x] Validate script behavior and skill file validity.

## Execution Log

- Initialized plan document.
- Added `scripts/bootstrap_project_from_template.sh` for safe template-to-target bootstrapping.
- Added `scripts/install_global_bootstrap_command.sh` and `make install-bootstrap` to install global `solo-new`.
- Added bundled Codex skill files under `codex-skills/solo-template-bootstrap/`.
- Added `scripts/install_codex_bootstrap_skill.sh` and `make install-codex-skill` to install skill globally.
- Installed global command (`~/.local/bin/solo-new`) and validated bootstrap into temp directories.
- Installed global skill at `~/.codex/skills/solo-template-bootstrap` and validated skill bootstrap script.
- Attempted official skill validator; blocked by missing `PyYAML` dependency in local Python runtime.

## Follow-ups

- If template layout changes significantly, update bootstrap exclusions and placeholder replacement logic.
- Periodically verify global command path (`~/.local/bin`) is still in shell PATH.
- If strict validation is desired, install `PyYAML` for the Python runtime used by skill-creator scripts, then run `quick_validate.py`.
