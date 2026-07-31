# V1 application code — change-detection + scoring + report

## Context
Build the real V1 Python application (phases P6 change-detection + scoring + report),
replacing the P2/P3 scratch collector handlers. Implements the DATA_MODEL, SCORING,
SOURCE_CONNECTOR, and RELIABILITY specs plus PANEL_DISSENT conditions M1/M2/M3 (M4/M5 are IaC).

## Plan
- `src/common/models.py` — Pydantic v2 models + enums (schema_v).
- `src/common/s3layout.py` — 5-tier key builders. M4 prefix split: collector owns
  `status/`+`raw/`+`normalized/`; differ owns `current/`+`events/`. No versioning.
- `src/common/normalize.py` — deterministic normalizer + canonical hashing.
- `src/common/connectors.py` — Greenhouse/Lever/Ashby; fetch→raw+receipt→status→CanonicalJob.
- `src/enumerate/handler.py` — M1 completeness backbone: registry → RUN_OPEN manifest → SQS fan-out.
- `src/collector/handler.py` — SQS-triggered; raw+receipt+normalized+status per message.
- `src/differ/handler.py` — change-detection brain + disappearance invariant + M3 checks.
- `src/scoring/scoring.py` — 6 deterministic dimensions, UNKNOWN first-class, weakest-link confidence.
- `src/report/handler.py` — deterministic md+json renderer; run-health header; never-fake guard; M2 slot-fill.
- `src/llm/narrator.py` — Bedrock narrator, feature-flagged OFF, post-check.
- `src/llm/bedrock_client.py` — self-contained reuse of job-searcher wrapper pattern.
- `src/cli.py` — local connector/differ/report replay CLI.
- `config/companies.yaml` — 3 Greenhouse companies.
- `tests/` — golden-fixture pytest suite (T1/T4/T8/M3 x2/scoring/evidence/UNKNOWN/never-fake/status).
- `pyproject.toml` (py3.13, pydantic/boto3/pyyaml/pytest), `README.md`.

## Execution Log
- Read all 5 specs + bedrock client + existing scratch handlers. Design settled.
- Python 3.13 chosen for venv (3.14 is default local, spec targets 3.13).
- Built all modules; removed scratch collector handlers (handler_one/handler_sqs/handler_sqs_v2).
- Differ core is a pure function `diff_source`; freeze-on-non-success enforces the invariant.
- M3 guards: single-step mass-drop + cumulative window-max trend + per-department silent-subset.
- Scoring: 6 dims, UNKNOWN when <2 successful observations for time-based dims; weakest-link min.
- Report: word-boundary never-fake guard scans BOTH markdown and JSON (catches notes smuggling).
- DONE: 40 pytest passing (T1, partial-freeze, T3 grace, T4 outage-through-grace, T8 mass-drop,
  M3 cumulative, M3 silent-subset, content-hash, salary field-event, repost, cold-start; connector
  status labeling + id mapping + Ashby gating; scoring determinism/evidence/UNKNOWN/weakest-link;
  report health states + never-fake guard; M1 manifest/incomplete/fan-out; M2 narrator-off + post-check).
- CLI smoke-tested against a local Greenhouse fixture.

## Follow-ups
- Ashby stays feature-flagged OFF (UUID permanence unverified, D2/U4).
- Narrator off in V1 (M2/P8 gate).
- M4 IAM prefix enforcement + M5 budget action are IaC-track, not app code.
