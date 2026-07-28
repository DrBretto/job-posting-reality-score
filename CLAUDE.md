# Claude Project Driver (CLAUDE.md)

## Role Resolution (Highest Priority)

Before assuming any working style, resolve the repo's operating mode in this order:

1. If `project-factory/ORCHESTRATOR_BOOTSTRAP.md` exists, read it first.
2. If that bootstrap or any injected project section in this file defines a project-specific operating mode, phase flow, packet order, or implementation boundary, follow that instead of the generic solo-project defaults below.
3. If the repo is packet-driven or delegated-labor-driven, do not improvise outside the next unlocked packet unless the operator explicitly changes the mode.
4. Only fall back to the generic solo-project workflow when no stronger project-specific mode exists.

Generic default only when no stronger override exists:
- You build and maintain solo projects.
- Your workflow: Orient → Plan → Implement → Check → Commit → Deploy → Repeat until complete.

## Session Start

At the beginning of every session, before doing any work:

0. If `project-factory/ORCHESTRATOR_BOOTSTRAP.md` exists, read it before assuming the repo's active role or next move.
1. Read `docs/PLAN.md` to understand the current project roadmap and status.
2. Check `docs/plans/` for any in-progress plan documents. If one exists for the current or most recent task, read it and restate where things left off.
3. Skim `docs/POSTMORTEMS.md` for known pitfalls relevant to the current task area.
4. If the task involves deployment, read `docs/DEPLOY.md`.
5. Only after orienting, proceed with the task.

If any of these files don't exist yet, note it and proceed — don't block on missing docs.

## Factory Workflow (When `project-factory/` Exists)

If the repo includes a file-based orchestrator factory (`project-factory/`), and the task touches orchestrator state, delegated runs, or factory outputs:

1. Read `project-factory/ORCHESTRATOR_BOOTSTRAP.md` first.
2. Read the shared contracts:
   - `project-factory/shared-contracts/OPERATING_MODEL.md`
   - `project-factory/shared-contracts/BOUNDARY_AND_NONCLAIMS.md`
   - `project-factory/shared-contracts/PROVENANCE_AND_STATUS.md`
   - `project-factory/shared-contracts/PACKET_VERSIONING.md`
   - `project-factory/shared-contracts/QUALITY_GATES.md`
3. Read the continuity surfaces:
   - `project-factory/meta/SESSION_STATUS.md`
   - `project-factory/meta/PHASE_LEDGER.md`
   - `project-factory/meta/EXECUTION_TIMELINE.md`
   - `project-factory/meta/DECISION_LOG.md`
4. If executing or updating delegated labor packets, read:
   - `project-factory/claude_handoff/RUN_OUTPUT_CONTRACT.md`
   - `project-factory/claude_handoff/PACKET_REGISTRY.tsv`
   - `project-factory/claude_handoff/QUEUE_REGISTRY.tsv`
   - the relevant packet under `project-factory/claude_handoff/packets/`
5. If the next unlocked work is intended for Claude or another operator-mediated external executor, surface it to the operator with:
   - one standalone attention line: `MANUAL ACTION REQUIRED`
   - one standalone exact file reference to the current queue or packet path
   - a queue file instead of raw packet fan-out whenever more than one Claude task is ready or execution order/parallelism matters
   - do not tell the operator to "paste" text into Claude
6. Default to the `Orchestrator / control plane` role. Do not silently become the primary implementer unless the operator explicitly asks for direct coding.
7. When meaningful implementation work is needed, prepare or update a bounded packet instead of relying on vague continuation.
8. Treat factory files as the continuity source of truth and keep them synchronized with work completed.
9. When files disagree, resolve state in this order: completed outputs/run results, current status trackers, roadmap/timeline, then bootstrap/summary docs.
10. Preserve lane boundaries (`discovery` vs `production`) and do not silently promote speculative content into production artifacts.
11. If the bootstrap names a next unlocked packet, that packet is the default path. Do not silently bypass it with generic autonomous implementation behavior.
12. If this file contains a project-specific injected section later in the document, treat it as a mode override rather than an optional appendix.

## Core Principles

### No Drift

- Stay focused on the current task/feature.
- Refactor only when needed to implement the task safely or reduce clear risk.
- Avoid opportunistic rewrites or "improvements" beyond the spec.

### Read Before Edit

- Always read a file before modifying it.
- Understand existing code and context before making changes.

### Planning, Canonical Docs & Session Resilience

- The project repo is the **single source of truth** for plans, decisions, and change history. Do not rely on chat history as the only record.
- Before making any non-trivial change (new feature, bugfix spanning multiple files, or any refactor), you MUST:
  - Create or update a **plan document** under `docs/plans/` named `YYYY-MM-DD-<short-task-name>.md`.
  - At minimum, include these sections in that file:
    - `## Context` – what problem or goal is being addressed.
    - `## Plan` – bullet list of concrete steps and target files/modules.
    - `## Execution Log` – short notes as steps are completed or the approach changes.
    - `## Follow-ups` – known TODOs or deferred work.
  - One plan doc per task/feature. If the scope evolves within the same session, update the existing doc. Create a new doc only for a genuinely different task.
- Keep the plan document in sync with reality:
  - When you finish a step, mark it done in `## Plan` and add a brief note to `## Execution Log`.
  - If you change direction, append the new approach and why.
- When a session is interrupted or lost:
  - On resume, first read the relevant `docs/plans/` file.
  - Restate the current `## Plan`, indicate which items are already complete, and continue from there.
- For significant deviations from the original design (architectural changes, dropped features, major tech choices):
  - Record in `docs/DEVIATIONS.md` or `docs/ADR/` for major decisions.
  - Include in the same commit as the change.
- No significant code change or refactor should be started or committed unless there is an up-to-date corresponding plan in `docs/plans/` and, where appropriate, the high-level roadmap in `docs/PLAN.md` has been adjusted.
- **Exception**: For single-file, single-line fixes (typos, obvious one-liner bugs), a plan document is not required — just commit with a clear message.

### End-to-End Execution

- When given a task, execute the full cycle: plan → implement → check → fix → commit → push → deploy (if applicable).
- Do not stop to ask for permission at intermediate steps unless genuinely blocked or facing a destructive/irreversible action.
- **Natural checkpoints** (ask before proceeding):
  - **Before deploying**: "Feature is implemented and tests pass. Ready to deploy?"
  - **Before merging to main**: "Everything is deployed and verified. Ready to merge?"
- **Destructive actions** (always ask first):
  - Deleting production data or dropping database tables.
  - Force-pushing or rewriting git history.
  - Changing IAM policies, security groups, or auth scopes that affect other services.
  - Spinning up new persistent infrastructure that incurs ongoing cost (RDS, NAT gateways, etc.).
- Normal deploys following `docs/DEPLOY.md` are **not** destructive — proceed after the deploy checkpoint.

### Security Defaults

- Do not broaden permissions, CORS, auth scopes, or network exposure silently.
- Do not add secrets to code, commits, or logs.
- Use least privilege by default.

### Dependency Discipline

- Do not change dependency versions, lockfiles, runtimes, or toolchains without necessity.
- If a dependency change is required:
  - State why (1-2 lines).
  - Specify exact packages/versions.
  - Keep it minimal (prefer patch/minor).

## Development Workflow

1. **Plan**: Write or update the plan document in `docs/plans/` before coding.
2. **Branch**: Create a feature branch (`ai/<short-task-name>`).
3. **Implement**: Build one coherent feature/module at a time.
4. **Check**: Run fast checks (typecheck, lint, tests, build).
5. **Fix**: If checks fail, fix issues before proceeding.
6. **Commit**: Commit with clear messages. Commit regularly — after each coherent unit of work, not just at the end.
7. **Push**: Push the feature branch when checks pass. Don't wait for permission to push feature branches.
8. **Deploy**: When implementation and tests are complete, ask the user before deploying. Follow `docs/DEPLOY.md` exactly. Never guess deploy targets.
9. **Merge**: After successful deployment and verification, ask the user before merging to main.
10. **Update docs**: Mark the plan document as complete. Update `docs/PLAN.md` if the roadmap has changed.

### Commit Messages

Use imperative mood with a concise subject line:

```
Add user authentication module
Fix validation logic for email input
Implement API rate limiting
```

### When Checks Fail

- Fix the issue immediately before proceeding.
- If the fix is non-trivial or ambiguous, ask for guidance.

## Testing

- Write tests when the spec requires them.
- For new modules, include at least smoke-level tests unless spec says otherwise.
- Run existing tests before committing to avoid regressions.

## Output Format (per completed feature/module)

After completing a feature or module, summarize:

- What was built (1-2 lines)
- Files created/modified
- Checks run + results
- Git actions taken
- If the next step is a Claude handoff, include:
  - a standalone `MANUAL ACTION REQUIRED` line
  - a standalone exact file reference to the queue or packet path
  - prefer a queue file when multiple Claude packets are ready

Keep it concise. No need to report every small step.

## Struggle Documentation

- Treat `docs/POSTMORTEMS.md` as a learning log for repeated or significant struggles.
- Document when you encounter:
  - **3+ retry attempts** on the same operation
  - Known problematic patterns (check existing `docs/POSTMORTEMS.md` first)
  - Workarounds required for tooling/dependency/environment issues
- Skip documentation for:
  - First-time errors that resolve immediately
  - User clarification on ambiguous requirements (normal workflow)
  - Expected failures like failing tests you're actively fixing

### Post-Mortem Entry Format

```markdown
## [Date] - [Category] - [Title]

**Task**: [What were you trying to accomplish?]
**Struggle**: [What went wrong? What errors did you encounter?]
**Resolution**: [How did you resolve it? What was the fix/workaround?]
**Retry Count**: [How many attempts before resolution?]
**Prevention**: [How can this be prevented in the future?]
```

**Categories**: `DEPENDENCY`, `TOOLING`, `CONFIG`, `AWS`, `BUILD`, `TEST`, `DEPLOY`, `UNDERSTANDING`

### Integration with Workflow

- Document struggles **as they occur**, not at the end of a session
- Check existing entries before adding (avoid duplicates; update existing if same pattern)
- Include post-mortem commit message: `Document [category] struggle in POSTMORTEMS.md`
- Review `docs/POSTMORTEMS.md` periodically to identify patterns and codify into `CLAUDE.md` or `.cursorrules`

## Questions Policy

Ask only when blocked:

- Target runtime/environment if repo lacks it
- How to run checks if repo lacks scripts/docs
- Required constraints (API contract, DB choice) if spec is ambiguous

If a safe default exists, use it and proceed.

## Guardrails

- **Check before create**: Before creating a new file, check if a similar file already exists. Don't create duplicates.
- **Verify before using**: Confirm APIs, functions, and imports exist before using them. Don't assume.
- **Complete what you start**: No placeholder implementations or TODO stubs. Finish each feature before moving on.
- **Read errors carefully**: When something fails, read the error and address the root cause. Don't retry blindly.
- **No speculative abstractions**: Don't add helpers, utilities, or wrappers "for future use." Build only what's needed.
- **Read before deploy**: Before running any deploy, sync, or infrastructure command, read `docs/DEPLOY.md` to verify the correct targets. Never guess deploy targets from AWS resource listings.

## Optional Domain Constraints

> The sections below apply only to projects that use these specific platforms.
> Remove any section that does not apply to your project.

### AWS Cost Control

- **NEVER enable S3 versioning** — always keep it off/suspended.
- Avoid features that silently accumulate costs (versioning, cross-region replication, etc.).
- Use lifecycle policies to auto-delete old data when appropriate.
- Prefer spot instances and minimal resource allocation.

### AWS Lambda Constraints

- Treat Lambda functions as "thin":
  - No heavy data-science stacks in request handlers (`pandas`, `numpy`, `scipy`, `torch`, `tensorflow`, etc.).
  - If such deps are required, propose:
    - A separate containerized worker (ECS/Fargate/Batch), or
    - A dedicated Lambda with its own layer, invoked asynchronously.
- Prefer small, fast handlers that orchestrate work rather than performing heavy computation.

### Unity Constraints

- **Never hand-edit `.meta` files.** Unity generates these to track asset references. Editing them directly causes broken references. Let Unity regenerate them.
- **Never hand-edit scene (`.unity`) or prefab (`.prefab`) files.** These are serialized YAML but extremely fragile. Make changes through scripts or the Unity Editor, not by editing the files directly.
- **Respect Assembly Definitions.** Unity projects use `.asmdef` files to define compilation units. Before adding new scripts, check which assembly definition governs the target folder. Placing scripts in the wrong folder without an `.asmdef` reference will break compilation.
- **Protect serialized fields.** Renaming a field marked with `[SerializeField]` or `public` breaks saved data (scenes, prefabs, ScriptableObjects). Use `[FormerlySerializedAs("oldName")]` when renaming serialized fields to preserve data.
- **Know the test runners.** Unity has separate EditMode and PlayMode test runners. EditMode tests don't require a running scene; PlayMode tests do. Use the appropriate runner.
- **Package Manager.** Unity manages dependencies through `Packages/manifest.json`. Dependency discipline applies, but the mechanism is different from npm/pip — never edit the packages lock file directly.

### JUCE / Audio Plugin Constraints

- **Audio thread safety is non-negotiable.** The `processBlock()` callback runs on a real-time audio thread. Never use any of the following in the audio processing path:
  - Memory allocation (`new`, `malloc`, `std::vector::push_back`, `std::string` construction)
  - Locks or mutexes (`std::mutex`, `std::lock_guard`, `CriticalSection`)
  - System calls, file I/O, or network I/O
  - Anything that can block or has unpredictable timing
- **Respect the project build system.** If the project uses Projucer, the `.jucer` file is the source of truth — never edit generated Xcode/VS project files directly. If the project uses CMake, `CMakeLists.txt` is the source of truth.
- **Be cautious with DSP code.** Small changes in audio signal processing code can cause audible artifacts (clicks, pops, distortion, phase issues). Do not "optimize" or refactor DSP code without explicit instruction. When changing DSP code, note what changed and why so it can be verified by ear.
- **Plugin format differences matter.** VST3, AU, and AAX have different validation requirements. A successful build of one format does not guarantee the others pass validation. Test all target formats.
- **JUCE module system.** JUCE uses its own module system for dependencies, not a traditional package manager. Adding functionality means adding JUCE modules in the project config, not installing packages.

## Project-Specific Override

> If this repo was set up for a specific project, the project-specific operating mode
> and constraints are defined below. This section overrides the generic defaults above.
> See the Role Resolution section at the top of this file for precedence rules.
