# Repo Reuse & Migration Decision — CFR (`job-searcher`) → Job Posting Reality Score

> Module-by-module disposition of the existing Company Fit Radar (CFR, `/Users/drbretto/Desktop/
> Projects/job-searcher/`) and the topology decision. Roadmap only — no code moved here. Verified
> against the CFR tree, `src/pipeline.py`, `src/models.py`, `src/config.py`, and the shared-context
> facts. See ADR-01 in `ARCHITECTURE_DECISION_REGISTER.tsv`.

## What CFR actually is (verified)

CFR is a **one-time, offline, LOCAL batch tool**: it ingests thousands of *companies* (web search +
list scraping), hard-filters + Bedrock-scores them for personal fit, and writes per-company Markdown
dossiers. It is **NOT scheduled, has NO immutable posting history, NO change detection, NO daily ops,
NO tests, and is NOT deployed to AWS** (only AWS touch = Bedrock LLM calls). Its domain
(company matchmaking) is orthogonal to job-posting collection. `pipeline.py` is an in-process
sequential runner (`ingest→filter→score→select→enrich→contacts→dossiers`) driving a Rich console;
`models.py` is entirely company-oriented (Company / ScoredCompany / EnrichedCompany / Contact — no
job/snapshot/diff shapes); `config.py` is a yaml-backed typed `Settings` singleton.

## Disposition legend

`reuse-unchanged` — lift as-is. `adapt-behind-interface` — keep the pattern, wrap/reshape for the new
domain. `extract-as-reference` — the shape informs the new design; the code itself is rebuilt.
`archive-supersede` — leave in CFR; the new system builds a different thing. `rebuild` — new code, no
CFR carry.

## Module-by-module

| CFR module / asset | Disposition | Rationale |
|---|---|---|
| **Pipeline shape** (`src/pipeline.py` — staged ingest→…→dossiers, sequential, in-process, Rich console) | **extract-as-reference** | The clean staged decomposition is good design input for the phase/SFN structure, but the in-process sequential runner is exactly the "one-time/offline/local" assumption that must NOT enter a scheduled AWS system. The orchestration is replaced by EventBridge + SQS + Step Functions. Take the *shape*, rebuild the *runner*. |
| **Config pattern** (`src/config.py` + `config/settings.yaml` — yaml, typed `Settings`, singleton, defaults) | **adapt-behind-interface** | Config-driven, operator-curated sourcing is directly the JPRS pattern (the company/board registry is config, like CFR's `settings.yaml`). Adapt: the runtime config for Lambdas moves to **SSM Parameter Store** (board tokens, company slugs, User-Agent — all public); keep a yaml file for local-dev/fixtures. The typed-accessor discipline carries; the local-path properties (`data_dir`, `dossiers_dir`) are dropped (S3 tiers replace them). |
| **Pydantic domain models** (`src/models.py` — Company/ScoredCompany/HeuristicScores/LLMScreeningScores/EnrichedCompany/Contact) | **archive-supersede** | Company-domain models don't fit a job-posting/snapshot/diff system. **Rebuild** new models per the data seat: `SourceSnapshot`, `SourceReceipt`, `CanonicalJob`, `ChangeEvent`, `DimensionScorecard`, `EvidenceRef`. The Pydantic *conventions* (enums, `Field(default_factory=…)`, typed sub-models) carry; the shapes do not. Note `Contact` is deliberately not carried — contact harvesting is a hard-forbidden non-goal. |
| **Bedrock client wrapper** (`src/llm/bedrock_client.py` — `run_small`/`run_large`, `preflight`, retry/throttle, typed errors, dry-run stubs, boto3 `bedrock-runtime.invoke_model`, Anthropic messages format, model-id + token config) | **reuse-unchanged** | The one clearly portable asset. Directly reusable for the P8 narrator: dry-run stubs suit local/CI testing; retry/throttle + max_tokens caps are the cost-control the guardrails require; it already logs model IDs/attempts (not bodies) — the log-hygiene the security seat wants. Used only at P8, feature-flagged OFF in V1, inside the isolated `jprs-llm`/`llm-role` Lambda. |
| **Scoring** (`src/scoring/scoring_rules.py`, `scoring_runner.py` — heuristic rules + cheap-LLM screening; `HeuristicScores`/`LLMScreeningScores`) | **adapt-behind-interface** (heuristic pattern) / **archive-supersede** (LLM-screening) | The **deterministic heuristic-scoring pattern** and CFR's fit vocabulary are good input for the `brett_fit` dimension — reuse the pattern as a versioned `fit_ruleset`. But CFR scores *company* fit; JPRS scores *job* fit, and JPRS scoring is **deterministic-only** (LLM narrates, never scores). So the LLM-screening pass (`LLMScreeningScores`) is superseded, not carried. Rebuild scorers to emit the 6-dimension `DimensionScorecard` with `evidence_refs` + UNKNOWN-first-class. |
| **Ingest** (`src/ingest/` — `sources_web_search.py`, `sources_list_scraper.py`, `sources_base.py`) | **archive-supersede** | CFR ingests *companies* via web search + list scraping. JPRS ingests *postings* via sanctioned ATS GET APIs. The connector contract is entirely new (fail-safe SourceSnapshot status, receipt-before-parse, host-allowlist). Do NOT carry the scraping approach — it is adjacent to the forbidden path. Rebuild connectors per `SOURCE_CONNECTOR_AND_COMPLIANCE_SPEC.md`. |
| **Enrich** (`src/enrich/enrich_runner.py` — web-content enrichment of companies) | **archive-supersede** | Web-content enrichment of companies has no JPRS analog and is scraping-adjacent. Not carried. |
| **Contacts** (`src/contacts/contact_runner.py`, `Contact` model) | **archive-supersede** (hard) | Contact harvesting is an **explicit forbidden non-goal** of JPRS. Do NOT carry, adapt, or reference for outreach. Archive in CFR only. |
| **Dossiers** (`src/dossiers/dossier_templates.py`, `dossier_runner.py` — Markdown per-company output) | **extract-as-reference** | The Markdown-report-generation pattern (templated, human-readable output) informs the daily report renderer, but JPRS content is entirely different and adds the never-fake vocabulary guard + evidence_refs rendering + run-health header. Take the templating *approach*, rebuild the content. |
| **CLI** (`src/cli.py`) | **extract-as-reference** | A local CLI entry-point is useful for local-dev/replay-from-raw commands, but the production trigger is EventBridge, not a CLI. Rebuild a thin local CLI for fixtures/replay only. |
| **Repo scaffolding** (`pyproject.toml`, `Makefile`, `.env.example`, `scripts/check.sh`, ADR template, `docs/` conventions) | **extract-as-reference** | The project hygiene conventions (ADR dir, plan docs, check script) are good to mirror in the new repo, but JPRS adds what CFR lacks: **tests** (CFR has none) and IaC (P9). Reuse the conventions, not the files. |

## Topology decision: extend vs fork vs NEW repo

**Default recommendation: a NEW repository named `job-posting-reality-score`.**

Weighed against the criteria:

- **History.** CFR carries no test history and a large body of company-matchmaking + scraping +
  contacts code that JPRS actively excludes. A fork drags all of it (and its git history) into a system
  whose non-goals include most of it. A new repo starts clean.
- **Testability.** CFR has **NO tests**. JPRS is test-first by design (golden fixtures for the diff
  engine, scorers, connector labeling, LLM-boundary, never-fake guard; unit tests gating the P9 CI).
  Building that discipline on top of an untested codebase means inheriting the exact absence we're
  correcting. A new repo lets the test suite be foundational.
- **The one-time/offline/local risk.** The single biggest hazard is carrying CFR's *implicit
  assumptions* — sequential in-process runner, local `data_dir` paths, "run it once by hand" — into a
  **scheduled, idempotent, at-least-once AWS system** where duplicate delivery, source failure, and
  immutability are first-class. A fork makes those assumptions the path of least resistance. A new repo
  forces each to be a deliberate decision.
- **Naming + future public presentation.** "job-searcher / Company Fit Radar" is the wrong name and the
  wrong framing for a job-posting-behavior radar that will be an interview-defensible portfolio artifact
  (and possibly public, PII-redacted). A clean repo named for what it is presents correctly.
- **Domain orthogonality.** Company matchmaking vs job-posting collection share almost nothing at the
  data-model level; the genuinely shared surface is the Bedrock wrapper + the config pattern, both of
  which extract cleanly without a fork.

**Why not extend `job-searcher` in place:** it would entangle two orthogonal domains, inherit the
no-tests debt, and normalize the offline/local assumptions — the exact drift the system must avoid.

**Why not fork:** a fork keeps CFR's history and dead code (ingest scraping, enrich, contacts) for no
benefit; the reusable surface is small enough to extract by hand.

**Migration mechanics:** the first downstream packet (`PKT-JPRS-CFR-REPO-MIGRATION`, recommended in
`COMMITTEE_VERDICT.md`) stands up the new repo, lifts `bedrock_client.py` unchanged, adapts the config
pattern to SSM + local yaml, rebuilds the domain models, and mirrors the repo hygiene conventions — with
a test suite from commit one. CFR stays intact and untouched as the reference source.
