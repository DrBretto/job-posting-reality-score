# START HERE

## Startup Order

Before doing anything in this repo, follow this exact sequence:

1. **Read `project-factory/ORCHESTRATOR_BOOTSTRAP.md`** — if it exists. This is the mode-resolution authority. It tells you what the repo is, what phase it's in, and what the next unlocked task is.

2. **Read `project-factory/meta/SESSION_STATUS.md`** — if it exists. This tells you what happened last time and what to do now.

3. **Identify the next unlocked packet** — named in the bootstrap or session status. If a packet is staged, that packet is your default path. Do not bypass it with general autonomous implementation.

4. **If no project-factory exists or the bootstrap is generic/empty**, fall back to the generic solo-project workflow in `CLAUDE.md`: Orient → Plan → Implement → Check → Commit → Deploy.

## Mode Resolution

This repo may operate in one of two modes:

- **Packet-driven mode** — if `project-factory/ORCHESTRATOR_BOOTSTRAP.md` names a specific phase flow, packet order, or delegated-labor sequence. Follow that. Do not improvise outside the current packet.

- **Generic solo-project mode** — if no project-factory exists or the bootstrap contains only the default scaffold. Follow `CLAUDE.md` and `docs/PLAN.md`.

If a project-specific section was injected into `CLAUDE.md`, treat it as a mode override, not an optional appendix.

## Key Principle

When the project-factory names a next unlocked packet, that packet is the work. Do not silently skip it in favor of broad autonomous implementation.
