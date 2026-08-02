# Real-target job radar usefulness pass

## Context

The original JPRS pipeline was healthy, but its production registry still contained the three build
targets (`stripe`, `figma`, and `gitlab`). The live report also leaves the deterministic scoring
module disconnected, renders job IDs instead of useful application links, and does not send the SES
digest described by the stack. Replacing only the registry would therefore produce more relevant
raw history without giving Brett a usable daily decision surface.

This pass turns the working infrastructure into the intended personal job-search radar while
preserving the evidence-first and no-automated-application boundaries.

## Plan

- [x] Replace the sample registry with a validated set of public Greenhouse boards selected for
      agentic AI, applied AI, backend/platform, developer-tooling, and practical remote roles.
- [x] Make Brett-fit scoring role-aware, boundary-safe, and location-aware; remove substring matches
      such as `ai` inside unrelated words.
- [x] Assemble scorecards from the current S3 job set and render a capped, readable list of active
      matches with company, title, location, score evidence, and application link.
- [x] Limit newly observed output to relevant matches while retaining complete events in JSON.
- [x] Send the deterministic Markdown report through the already-configured SES sender/recipient.
- [x] Add unit and integration coverage for registry validation, fit ranking, report assembly,
      readable links, capping, and email delivery.
- [x] Synchronize the operator/status documents with the deployed state and the new daily workflow.
- [x] Run the full test/check suite plus SAM validation/build; fix all failures.
- [x] Stop before changing `/jprs/companies` or deploying the stack and ask for the required AWS
      deployment approval.
- [x] Deploy the code and IAM update, replace the registry between runs, and execute a controlled
      15-source production collection.
- [x] Verify ranked production output and repair report timeout, delivery-marker IAM, and stale
      same-day sentinel counting issues exposed by the controlled run.
- [x] Confirm the one-time SES identity verification and record a successful delivery marker.

## Execution Log

- 2026-08-02: Verified the live stack and `/jprs/companies`; production still watches Stripe,
  Figma, and GitLab.
- 2026-08-02: Read the latest live report. Collection and assembly are complete, but scorecards are
  empty, Markdown contains no active matches, and the report handler contains no SES send call.
- 2026-08-02: Validated candidate boards against the public Greenhouse API and selected a smaller,
  job-search-specific registry instead of broad prestige-company boards.
- 2026-08-02: Live-validated all 15 selected boards: 15 SUCCESS responses, 519 current postings,
  and 41 matches after title, geography, pre-sales, and clearance filters.
- 2026-08-02: Connected current jobs and diff state to scoring, preserved authoritative first-seen
  timestamps, added readable linked output, and wired idempotent SES delivery.
- 2026-08-02: Removed a tracked AWS error-output artifact containing a private account identifier and
  replaced it with a regression test plus non-private operator guidance.
- 2026-08-02: Local gate passed: 62 tests, repository checks, source and built SAM lint validation,
  `git diff --check`, registry rendering, and SAM build.
- 2026-08-02: Deployed the usefulness pass after inspecting non-replacement CloudFormation change
  sets; replaced the live registry only while the pipeline and both queues were idle.
- 2026-08-02: Controlled collection completed 15/15. The ranked report contains 519 scorecards and
  41 useful matches with readable titles, locations, and direct application links.
- 2026-08-02: Production rehearsal found and fixed the report's 30-second runtime limit, optional
  delivery-marker permission check, and stale same-day sentinel count. The suite now passes 65 tests.
- 2026-08-02: Verified the SES identity, sent the first digest, confirmed the delivery marker, and
  proved an immediate retry returns `already-sent` without sending twice.

## Follow-ups

- The live usefulness pass is complete; continue accumulating history and application outcomes.
- Ashby stays disabled until its identity-permanence gate is resolved; unsupported Breezy and
  Trakstar targets remain outside automated collection.
- Historical outcome learning remains a later feature; this pass ranks current public evidence.
