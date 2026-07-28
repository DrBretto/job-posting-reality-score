# Shared Committee Context — Job Posting Reality Score Roadmap Committee

> Every specialist seat reads this file first. It is the common product/learning context.
> Your lens-specific question is in your own prompt. Packet:
> `PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727`.

## The product (two layers)

**Job Posting Reality Score** is a low-cost AWS serverless system that:

- **Job radar (V1):** collects selected company job boards on a schedule, preserves immutable
  posting snapshots, and reports what materially changed each day. First useful product =
  "save job postings every day and tell Brett what changed."
- **Historical intelligence (mature):** uses first-seen dates, change history, repost patterns,
  hiring momentum, role fit, and application outcomes to estimate where Brett's job-search
  effort has the highest expected return. "Use job-history evidence to identify where hiring
  activity appears strongest and where effort is most likely to pay off."

## The dual telos (BOTH matter equally)

1. **Rebuild practical AWS recall through MANUAL console work.** Brett is an experienced
   engineer (production AWS at Amazon/Bedrock/SQS/Fargate; HotelPlanner data pipelines) whose
   hands-on recall has decayed from heavy AI use — he blanked on the SQS dead-letter-queue path
   in an interview despite using it extensively. The build is guided reconstruction with
   deliberate failure injection, NOT a beginner tutorial and NOT a from-scratch AWS course.
2. **Deliver real daily job-search value** without overclaiming that posting behavior proves a
   job is fake or real.

**Fixed division of labor:** AI prepares code, IAM policies, schemas, tests, fixtures,
state-machine definitions, SQL, and docs IN ADVANCE. Brett MANUALLY performs AWS resource
creation, wiring, deployment, and verification in the console — that manual act is what
rebuilds recall. Ownership vocabulary for matrices/backlogs: `BRETT_MANUAL_AWS` /
`AI_IMPLEMENTATION` / `SHARED_VERIFY`.

## Suggested learning surface (KINDS-of, NOT a mandate)

EventBridge Scheduler, Step Functions, Lambda, SQS + dead-letter queue, S3, CloudWatch,
optional Bedrock, later Parquet + Athena. Each service must EARN a real operational OR
educational role or be excluded. Do not add a service to make a diagram look impressive. You
may merge, split, reject, or replace any suggested service where evidence supports a better
design — but justify it.

## The existing repo — VERIFIED FACTS (do not assume it collects postings)

`/Users/drbretto/Desktop/Projects/job-searcher/` is **Company Fit Radar (CFR)**: a one-time,
offline, LOCAL batch tool that ingests thousands of *companies*, hard-filters + Bedrock-scores
them for personal fit, and writes per-company Markdown dossiers. It is **NOT** scheduled, has
**NO** immutable posting history, **NO** change detection, **NO** daily ops, **NO tests**, and
is **NOT deployed to AWS** (only AWS touch = Bedrock LLM calls). Its domain (company
matchmaking) is orthogonal to job-posting collection. Portable/reusable pieces:

- Clean staged pipeline shape (`src/pipeline.py`: ingest→filter→score→select→enrich→contacts→dossiers).
- Config-driven sourcing (`config/settings.yaml`).
- Pydantic domain models (`src/models.py`: Company/ScoredCompany/etc. — company-oriented, no job/snapshot/diff models).
- A clean, portable **Bedrock client wrapper** (`src/llm/bedrock_client.py`): `run_small`/`run_large`,
  `preflight`, retry/throttle, typed errors, dry-run stubs, boto3 `bedrock-runtime.invoke_model`,
  Anthropic messages format. This is directly reusable.

**Validated by the operator's environment (from settings.yaml / CFR CLAUDE.md):** region
`us-east-1`; Bedrock cheap model `anthropic.claude-3-haiku-20240307-v1:0`; strong model
`anthropic.claude-3-5-sonnet-20240620-v1:0`. (Treat these as the operator's known-good baseline;
verify current availability where it matters.)

**Operator's standing AWS hard rules (from CFR CLAUDE.md — carry these):** NEVER enable S3
versioning (use lifecycle policies for retention instead); keep Lambdas thin (no pandas/numpy/
torch in request handlers — push heavy work to a separate async worker if ever needed); never
broaden IAM/CORS/auth silently; least privilege by default; no secrets in code/commits/logs;
avoid silently cost-accumulating features; ask before persistent always-on infra (RDS, NAT).

## Hard constraints (bind every seat)

- This committee produces a ROADMAP ONLY. Do NOT create/modify AWS resources, write application
  implementation code, deploy, scrape, apply to jobs, contact anyone, or send notifications.
- Do NOT expose AWS account IDs, credentials, private financial urgency, or personal contact info.
- Not a beginner AWS textbook — production-memory refresher for an experienced engineer.
- Starter pass must NOT deploy the whole environment via CLI/SAM/CDK/Terraform/CloudFormation.
  Infrastructure-as-code belongs to a LATER reconstruction phase, after Brett has manually
  created/wired/observed/explained the core resources.
- AI may summarize/explain evidence but may NOT invent dates, decide whether a posting
  disappeared, or become the silent factual scoring authority. Every generated explanation
  points back to specific stored evidence. LLM output is NEVER evidence that a posting is real/
  fake/active/deceptive.
- Distinguish observable posting BEHAVIOR from any accusation that a job is fake/fraudulent.
- **Cost:** starter architecture targets **< $5/month** under modeled normal usage. NO NAT
  Gateway, EC2, RDS, OpenSearch, Kubernetes, paid Glue job, or paid Glue crawler in starter
  scope. No always-on/provisioned resources without explicit approval.
- Sourcing uses SANCTIONED PUBLIC ATS APIs only (Greenhouse, Lever, Ashby). NO authenticated
  scraping, NO LinkedIn scraping, NO contact harvesting, NO auto-apply, NO message sending.
- A quiet report must distinguish "nothing changed" from "the collectors did not run."
- Source failure must NEVER masquerade as mass job disappearance.

## What every seat must return (not bare recommendations)

For your lens: **assumptions**, **failure modes**, **decisions** (each with a DEFAULT, an OWNER,
and a decision/escalation TRIGGER — no "ask AI later" P0 decisions), and **acceptance tests**
(concrete, checkable). Verify current official facts (AWS pricing/quotas/APIs; Greenhouse/Lever/
Ashby public API docs) against PRIMARY sources where your lens depends on them; record source
URL + retrieval date + region assumption + any uncertainty. Remembered pricing and third-party
tutorials are NOT authoritative — mark anything you could not verify as UNVERIFIED.

## Three cost/scale reference points (for anyone modeling scale)

- Learning/V1: 1 ATS provider + 3 companies, 1 daily run.
- Useful personal scale: 3 ATS providers + 10–20 companies.
- Expansion: ~100 companies + historical analytics.
