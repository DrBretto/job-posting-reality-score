# Job Posting Reality Score

Job Posting Reality Score (JPRS) is Brett's low-cost AWS job-search radar. It collects public job
boards every day, preserves posting history, reports meaningful changes, and ranks current openings
against Brett's strongest lane: agentic and applied AI engineering, backend/platform work, AWS,
automation, and developer tooling.

The product answers two practical questions:

> Which current roles deserve attention today?

> What changed on the boards we care about?

It reports observed behavior and confidence-bounded scores. It does not automate applications,
collect personal contact details, or make claims about a company's intent.

## Current State

- The `jprs-v1` stack is deployed and running in `us-east-1`.
- Daily collection and assembly have been verified end to end.
- Production watches 15 live-validated Greenhouse boards selected for Brett's lane.
- Deterministic fit scoring is connected to the daily report with readable titles, locations, and
  direct links; authoritative first-seen dates persist across runs.
- The August 2 controlled run collected 15/15 targets and scored 519 postings, surfacing 41 useful
  matches. The queues and DLQ finished empty.
- SES delivery is verified: the first digest was sent and a same-day retry was suppressed by its
  delivery marker.
- Bedrock narration remains off. Scoring and reporting are deterministic.

Start with [START_HERE.md](START_HERE.md). The active implementation record is
[docs/plans/2026-08-02-real-job-radar.md](docs/plans/2026-08-02-real-job-radar.md).

## Daily Flow

```text
EventBridge Scheduler
  -> enumerate Lambda
  -> RUN_OPEN manifest
  -> SQS + DLQ
  -> collector Lambda
  -> raw / normalized / status S3 records

EventBridge Scheduler
  -> Step Functions
  -> differ Lambda
  -> current jobs + change events
  -> report Lambda
  -> Markdown + JSON in S3
  -> SES digest
```

The collector cannot overwrite `current/`. Failed or partial fetches freeze job state, so a source
failure cannot turn into a mass disappearance. Raw snapshots use unique keys and S3 versioning stays
off.

## Target Registry

`config/companies.yaml` is the local source of truth. The live registry covers 15 companies with
current agentic AI, applied AI, platform, backend, or developer-tooling openings. The deployed
enumerator reads the production copy from SSM parameter `/jprs/companies`.

Render the exact SSM JSON without editing it by hand:

```bash
.venv/bin/python -m src.cli registry --compact
```

Updating the YAML does not update AWS. Follow the checkpoint sequence in
[START_HERE.md](START_HERE.md) so collection and assembly never read different registries.

## Fit Ranking

The fit scorer is transparent and versioned. It considers:

- Role title: agentic/applied AI, ML, research engineering, backend, platform, automation, data,
  software engineering, and developer experience.
- Technical evidence: agents, MCP, LLMs, evals, retrieval, Python, AWS/serverless, orchestration,
  TypeScript/Node, APIs, and data pipelines.
- Eligibility: remote US and NH/MA-compatible work are favored; clearly foreign-only and nonlocal
  onsite/hybrid roles are excluded.
- Seniority: staff/principal and management titles are downweighted rather than hidden outright.
- Posting evidence: freshness, observed changes, repost churn, and source confidence remain separate
  inspectable dimensions.

Every non-UNKNOWN score retains evidence references. Complete events and scorecards remain in JSON
even when the email is capped to the most useful roles.

## Project Boundaries

- Public ATS and company-career sources only.
- No authenticated scraping, automated applications, or personal-contact harvesting.
- No NAT Gateway, EC2, RDS, OpenSearch, EKS, Kinesis, paid Glue jobs, or always-on compute.
- S3 versioning remains off.
- AWS changes require an explicit operator checkpoint. Local implementation and tests may proceed
  directly.
- Never commit account identifiers, private ARNs, access keys, notification addresses, or secrets.

## Development

```bash
python3.13 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pytest -p no:cacheprovider
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml
```

The test suite is offline and uses synthetic fixtures plus mocked AWS services. Live board checks are
an explicit operator action, not part of normal tests.

## References

- [Operator guide](START_HERE.md)
- [Current plan](docs/plans/2026-08-02-real-job-radar.md)
- [Project plan](docs/PLAN.md)
- [Deployment guide](infra/DEPLOY.md)
- [Committee roadmap](docs/roadmap/committee-v1/JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md)
- [Reliability runbook](docs/roadmap/committee-v1/RELIABILITY_RUNBOOK.md)
