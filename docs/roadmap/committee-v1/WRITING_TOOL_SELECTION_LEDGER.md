# Writing-Tool Selection Ledger — JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md

Per `book-factory/control_plane_standards/READER_FACING_WRITING_TOOL_DISCOVERY_STANDARD_V1_20260603.md`.

**Target artifact:** `JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md` (the operator-facing canonical guide).
**Tier: LIGHT.** It is substantive functional prose an experienced engineer reads phase-by-phase —
not a receipt/TSV (so not NONE), and not a book/essay/public explainer (so not FULL). A 3–6 row
ledger + one reader-state target line is the standard's LIGHT requirement.

**Discovery method:** queried the structured resource `governance://writing-tools/canonical-for-scope/host_voice_prose`
(attested) — the closest applicable scope for prose in this repo. Union of applicable tags considered:
`host_voice_prose`, `any_long_form`, `cross_project`. Every candidate below was body-read at
`governance://writing-tools/<tool_id>` before a decision (no keyword-only matches — the WT-0052 guard).

**Reader-state target line:** an experienced engineer with decayed hands-on AWS recall opens this,
knows exactly which phase he is on, and can execute the next phase by hand without re-planning in
chat — propulsive, zero AI-glaze, zero beginner padding.

## Ledger

| tool_id | name | decision | reason | read_attestation |
|---|---|---|---|---|
| WT-0015 | AI-Cadence Detection | **activated** | Watchlist scan for characteristic AI phrasing/rhythm/structural monotony genuinely applies to ANY prose incl. a technical roadmap; scope tag `cross_project`; advisory gate. | body-read `governance://writing-tools/WT-0015` (hash 3840233b…), attested 2026-07-28 |
| WT-0023 | Truth-Anchor Grounding | **rejected_with_reason** | Body-read revealed its mechanism is *literary experiential grounding beneath abstraction* (sensory detail, Lifeblood-Auditor >800-word abstraction flag) — a host-voice-prose device. The roadmap's "anchor every claim to a verified fact" need is served by the SOURCE_REGISTER discipline, not this tool. Activating on name-overlap alone would be a WT-0052-class false match. | body-read `governance://writing-tools/WT-0023` (hash 3c81d04a…), attested 2026-07-28 |
| WT-0050 | The Corniness Boundary — Six Corny Moves | **rejected_with_reason** | Body-read shows `applicability_scope_gate: binding` and an explicit exclusion: *"Does NOT apply to technical_paper or methods_document. Activation outside scope raises a scope-violation finding (CAB-005 hard-gate)."* The master roadmap IS a methods document — activating it would itself raise a CAB-005 scope violation. Correctly NOT activated. | body-read `governance://writing-tools/WT-0050` (hash eb4c3006…), attested 2026-07-28 |
| (literary set) | WT-0004 felt-concept, WT-0008 undertow, WT-0010 earned-strangeness, WT-0011 objects-as-epistemology, WT-0024 emotional-color, WT-0006 prose-metabolism, personas WT-0025–34 | **deferred** | Host-voice / book-form literary prescription + persona tools. Out of domain for a technical operator roadmap; deferred rather than forced. | not body-read (deferred, not activated) |
| (book-lifecycle set) | WT-0043–0047 activation declarations, WT-0075 11-criterion quality gate, WT-0049 coherence-trap | **rejected_with_reason** | Book-form PROCESS compulsions scoped to manuscript lifecycle; an internal engineering roadmap is not a book chapter, so the declaration ceremony does not bind. WT-0049 (followable-and-worth-following) noted as a background sanity read, not run as a book-scope gate. | not body-read (rejected on scope, not activated) |

## Application receipt — WT-0015 (the one activated tool)

Scanned the full master roadmap for AI-cadence tics: mechanical tricolons, the "it's not just X, it's Y"
frame, hollow connective transitions (Moreover/Furthermore/In conclusion), and rhythmic monotony.
Findings: prose already varies sentence posture (short imperatives beside longer spec sentences),
uses no hollow transitions, and never congratulates the reader or names its own mechanism. The one
recurring construction — the appositive "X — the Y" label — is functional technical labeling at phase
granularity, not glaze, and reads as intended. **Outcome: no rewrite required; the artifact passes the
watchlist scan.** Detection ≠ deletion (per the tool body); the tool owns the call and the call is "clean."

## Honest note

After body-reading, only one of the queried tools legitimately activates on a methods-class document.
That is the discovery process working as designed: two candidates that would have matched on name/theme
(Truth-Anchor Grounding, Corniness Boundary) were rejected precisely because their bodies place them
out of scope — and one of those rejections (WT-0050) avoided a live CAB-005 scope-violation finding.
