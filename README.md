# Job Posting Reality Score

Job Posting Reality Score (JPRS) is a low-cost AWS project that preserves public job-posting history
and reports what actually changed. Its first purpose is practical: improve Brett's job search while
rebuilding hands-on fluency with the AWS services that commonly appear in engineering interviews.

The first useful product is:

> Save selected public job postings every day and tell me what changed.

The longer-term product uses that history to identify fresh openings, repeated reposts, requirement
changes, hiring momentum, and the posting characteristics associated with useful application outcomes.
It reports observed behavior and evidence; it does not label jobs or companies "real" or "fake."

## Current State

- Committee roadmap: complete and copied into this repository.
- Current phase: **P0 — account guardrails**.
- AWS resources created by this repository so far: **none**.
- Operating mode: Brett builds AWS resources manually in the console; AI prepares code, policies,
  tests, checklists, and explanations for inspection.
- Region: `us-east-1`.
- V1: P0 through P7.

**Operator entrypoint:** [START_HERE.md](START_HERE.md)

That single guide contains the current status, manual/AI division of work, complete P0 console
instructions, values to enter, progress-report template, done gate, future phase map, and restart
instructions. The other documents are supporting references rather than required navigation.

## Architecture

The planned V1 flow is:

`EventBridge Scheduler -> enumerate Lambda -> SQS/DLQ -> collector Lambda -> immutable S3`

A second scheduled workflow uses Step Functions to compare snapshots, write evidence-backed change
events and reports, and send a daily digest. Bedrock is optional and stays off until P8.

The starter architecture is serverless, single-account, and single-region. It intentionally excludes
NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue jobs/crawlers, provisioned Lambda
concurrency, and other always-on services.

## Project Rules

- Public ATS and company-career sources only.
- No automated applications, contact harvesting, or authenticated scraping.
- S3 versioning stays off. Raw history uses unique write-once keys and lifecycle expiration.
- Every execution role receives the shared permissions boundary plus a narrower role policy.
- Every Lambda log group gets finite retention.
- The target operating cost is below `$5/month`; `$10` is the emergency ceiling.
- Manual console work remains manual through P8. IaC reconstruction begins at P9.

## Roadmap

- [Master roadmap](docs/roadmap/committee-v1/JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md)
- [Manual AWS workbook](docs/roadmap/committee-v1/AWS_MANUAL_BUILD_WORKBOOK.md)
- [Reference architecture](docs/roadmap/committee-v1/REFERENCE_ARCHITECTURE.md)
- [Security and threat model](docs/roadmap/committee-v1/SECURITY_AND_THREAT_MODEL.md)
- [Panel dissent and required conditions](docs/roadmap/committee-v1/PANEL_DISSENT.md)
- [Local execution plan](docs/PLAN.md)

## Status Language

`READY` means the local instructions and artifacts exist. `COMPLETE` means the AWS result was
manually built and verified. A document being present never proves that its AWS phase is complete.

## V1 Application Code (`src/`)

The real V1 application (change-detection + scoring + report) lives under `src/`. Lambdas are thin
(stdlib + `pydantic`/`boto3`/`pyyaml` only — no pandas/numpy) so each deploys as a plain zip.

```
src/
  common/models.py      Pydantic models + enums (SourceSnapshot, CanonicalJob, ChangeEvent,
                        DimensionScorecard, EvidenceRef ...), versioned schema_v
  common/s3layout.py    5-tier key builders. M4 prefix split: collector owns status/+raw/+
                        normalized/; differ owns current/+events/. No S3 versioning.
  common/normalize.py   deterministic normalizer + canonical/field hashing (no LLM)
  common/connectors.py  Greenhouse / Lever / Ashby; fetch -> raw+receipt BEFORE parse -> status
                        label -> CanonicalJob. Host-allowlist, identifying UA. Ashby flag OFF.
  enumerate/handler.py  M1 completeness backbone: registry -> RUN_OPEN manifest -> SQS fan-out
  collector/handler.py  SQS-triggered; raw+receipt+normalized+status+SUCCESS sentinel per message
  differ/handler.py     change-detection brain: disappearance invariant, grace, mass-drop guard,
                        M3 cumulative-bleed + silent-subset guards. Writes events/+current/
  scoring/scoring.py    6 deterministic dimensions, UNKNOWN first-class, weakest-link confidence
  report/handler.py     deterministic md+json renderer; run-health header; never-fake vocab guard
  llm/narrator.py       optional Bedrock narrator, FEATURE-FLAGGED OFF, slot-fill + post-check (M2)
  llm/bedrock_client.py self-contained Bedrock wrapper (dry-run default)
  cli.py                offline dev CLI (connect / diff / report)
config/companies.yaml   operator-curated registry (3 Greenhouse companies for V1)
```

### Lambda handler entry points (module.function — for the IaC track)

| Lambda | Entry point |
|---|---|
| enumerate (dispatcher) | `src.enumerate.handler.handler` |
| collector (SQS)        | `src.collector.handler.handler` |
| differ                 | `src.differ.handler.handler` |
| report assembler       | `src.report.handler.handler` |
| narrator (gated OFF)   | `src.llm.narrator.narrate` |

### Develop / test

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest                     # golden-fixture suite (offline; never hits a live ATS)
python -m src.cli connect --provider greenhouse --board-token acme \
    --fixture tests/fixtures/greenhouse_acme.json
```

The honesty invariant, the M1/M2/M3 conditions, and connector status-labeling are all covered by the
`tests/` golden fixtures. Tests use synthetic/captured fixtures only — no live network.
