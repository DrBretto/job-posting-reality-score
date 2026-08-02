# Job Posting Reality Score - Build Log

Region: `us-east-1` | Cost target: `< $5/month` | S3 versioning: `OFF`

## Phase Status

| Phase | Result | Status |
|---|---|---|
| P0 | Account and region guardrails | COMPLETE |
| P1 | Private S3 store | COMPLETE |
| P2 | Collector Lambda and least-privilege role | COMPLETE |
| P3 | SQS, DLQ, retries, poison-message inspection, and redrive | COMPLETE |
| P4 | EventBridge scheduled collection | COMPLETE |
| P5 | Step Functions fan-out with isolated failures | COMPLETE |
| P6 | Differ, disappearance invariant, and cumulative mass-drop guards | COMPLETE |
| P7 | Deterministic daily Markdown/JSON report and observability | DEPLOYED AND VERIFIED |
| P8 | Optional Bedrock narration | OFF / DEFERRED |
| P9 | SAM stack | DEPLOYED |
| P10 | Parquet and Athena | DEFERRED |

## Verified Live Baseline

- The `jprs-v1` stack collects and assembles on a daily schedule.
- The live registry has 15 targets and has produced complete manifests, sentinels, current records,
  events, and ranked reports.
- The DLQ was empty at the last inspection.
- Bedrock is not on the daily path.
- The optional budget-lockdown resources were removed by operator decision; the stack remains
  serverless with finite log retention and no always-on compute.

## 2026-08-02 - Personal Radar Usefulness Pass

- Verified the old three-target pipeline before changing code; its report had complete collection
  but no scorecards or actionable links.
- Confirmed that the report assembler hardcoded an empty scorecard list and that the report handler
  never invoked SES despite having sender/recipient configuration.
- Replaced the local registry with 15 public Greenhouse boards selected for agentic/applied AI,
  backend/platform, automation, developer tooling, remote US, and NH/MA-compatible work.
- Live-validated all 15 board tokens. They returned 519 current postings; 41 cleared the useful-fit
  threshold after foreign-only roles were filtered.
- Rebuilt Brett-fit scoring around role titles, boundary-safe phrases, technical evidence,
  geography, and seniority. Removed raw substring matching such as `ai` inside unrelated words.
- Connected `current_jobs.json` and diff state to scoring and restored authoritative observation
  dates from state.
- Added capped, readable company/title/location/link results while retaining complete events and
  scorecards in JSON.
- Added SES delivery with a per-date delivery marker and made AccessDenied fail loudly instead of
  silently producing an empty report.
- Added `python -m src.cli registry --compact` to render the exact SSM payload.
- Deployed the Lambda package and report-role update, then replaced `/jprs/companies` between runs.
- Controlled production collection completed 15/15 with empty work and dead-letter queues.
- Controlled assembly scored 519 current postings and surfaced 41 useful matches with readable
  direct links.
- Production verification exposed and fixed a 30-second report timeout, an optional-marker IAM
  check, and stale same-day sentinels inflating the displayed source count.
- Completed the one-time SES identity verification. The first digest returned `sent`, created its
  delivery marker, and an immediate retry returned `already-sent` without a duplicate email.

## Active Operation

Validation is complete: 65 tests, repository checks, source and built-template SAM lint, live
15-board validation, registry rendering, SAM build, and controlled production collection all pass.

Use the daily digest for one to three focused applications while history accumulates. Review target
health periodically and change the registry only between runs.
