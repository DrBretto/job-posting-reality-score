> **Qualified by later review.** A second orchestrator review reproduced three remaining blockers
> that this document's verdicts did not catch: the real HTTP boundary still lost Adzuna credentials
> (§2's PASS rested on a test that replaced the broken function), screening still suppressed a later
> mandatory duty after an earlier negation (§4), and source-safe rollback is not data-compatible
> rollback (§5). See `ORCHESTRATOR_REVIEW.md` here and
> `../20260924_runtime_boundary_and_fresh_first_v1/VALIDATION.md`.
>
> Left unedited apart from this banner.

# VALIDATION — open-market discovery release repair

Packet: `JPRS-L2-P02-discovery-release-repair-v01`
Run: `20260924_open_market_release_repair_v1`
Date: 2026-09-24
Source of the defects: `../20260924_open_market_discovery_v1/ORCHESTRATOR_REVIEW.md`

Provenance labels: `evidence` = observed this run, `inference` = reasoned from evidence,
`operator_preference` = from the central candidate policy.

**The review was right on all four findings.** R1 and R4 were the serious ones: R1 meant the Adzuna
credential path could never have worked, and R4's documented full rollback would have destroyed the
uncommitted implementation. Each was reproduced independently before any repair.

---

## 1. Method

Reproduce → failing test → repair → re-verify. Nothing was repaired before it could be demonstrated.

| Artifact | Contents |
|---|---|
| `evidence/defect_reproduction_before_repair.txt` | R1–R4 reproduced with no network, no AWS, no secrets |
| `evidence/tests_before_repair.txt` | the new suite failing: **23 failed, 13 passed, 5 skipped** |
| `evidence/rollback_validation.txt` | the CLI rejecting the P01 command, and two accepted forms |
| `evidence/himalayas_live_pagination.txt` | live cursor walk against the real provider |
| `evidence/exclusion_audit.json` | every P01 exclusion re-screened on identical bytes |
| `evidence/exclusion_audit_downstream.json` | what the released exclusions actually do downstream |
| `evidence/after_repair_verification.txt` | tests, SAM validate/build, policy check |
| `rehearsal/combined_repaired/` | the repaired rehearsal report + coverage receipt |

Commands and results (`evidence/after_repair_verification.txt`):

```
.venv/bin/pytest -q -p no:cacheprovider                      -> 209 passed
.venv/bin/pytest -q tests/test_release_repair.py             -> 41 passed
sam validate --lint --template-file infra/template.yaml      -> valid SAM Template
sam build --template-file infra/template.yaml --build-dir …  -> Build Succeeded
.venv/bin/python -m src.cli policy-check                     -> projection matches all sources
```

Test count moved 168 → **209**: 41 added in `tests/test_release_repair.py`. One pre-existing test
changed contract (§7).

---

## 2. R1 — the Adzuna runtime

### Reproduced

Three independent defects, not one (`evidence/defect_reproduction_before_repair.txt`):

| | Observed before repair |
|---|---|
| **R1a** default path | `providers or keyless_discovery_providers()` — with fake credentials supplied in `env`, attempted `['himalayas','jobicy','remoteok','remotive']`, `credential_gated: []`. Adzuna was neither queried **nor named**. |
| **R1b** credential plumbing | `endpoint()` read `os.environ` while the Lambda passed SSM values as `env`. Built URL: `…?app_id=&app_key=&…` — blank, with credentials present. |
| **R1c** location coverage | 20 Adzuna requests generated, `where=` present in **zero**. The NH-targeted search promised in the P01 design was never wired. |

Why P01's own test missed it: it passed `providers=["adzuna"]` explicitly, so it exercised a path
production never takes and asserted on the connector rather than the handler.

### Repaired

- **Default is every *enabled* provider**, so a credential-gated source is reached and its gate
  reported. Defaulting to fewer sources is exactly how a gate becomes invisible. An explicit
  `enabled: false` in `config/discovery_sources.yaml` is still honored — intentional disablement is a
  decision; absent config is not, so an unreadable config falls back to the full registry.
- **`AdzunaConnector.with_env(env)`** returns a *new* instance bound to the resolved credentials, so
  a per-run secret never mutates the shared registry singleton. `endpoint()` reads `self.env`.
- **Location scopes** `(None, "remote", "New Hampshire", "Boston, Massachusetts")`. `None` is first
  and mandatory: the review said "Do not solve this by limiting all searches to NH", so nationwide
  and remote coverage is preserved and the state/metro scopes supplement it.
- **Credential redaction** (`redact_url` in `src/common/connectors.py`). A `SourceReceipt` is written
  to `raw/` for every fetch, so an unredacted signed URL would have persisted the secret in the
  evidence store — the very artifact an operator forwards when debugging. Parameter *names* are kept
  because knowing `app_id` was sent is diagnostically useful; values become `REDACTED`.

### Verified at the handler boundary, with mocked AWS and captured transport

`tests/test_release_repair.py`, using `moto` for S3 + SSM SecureString and a capture in place of the
live fetcher:

| Test | Asserts |
|---|---|
| `test_r1_default_handler_path_reaches_authenticated_adzuna_requests` | default `handler({})` queries Adzuna and every URL carries the SSM-resolved `app_id`/`app_key` |
| `test_r1_missing_credentials_remain_a_visible_gate_on_the_default_path` | no credential → Adzuna named in `credential_gated` in the result AND in the stored coverage receipt, and never requested |
| `test_r1_location_coverage_includes_us_remote_and_state_scoped_searches` | both `where=`-scoped and unscoped requests exist; "hampshire" and "remote" both present |
| `test_r1_credentials_never_appear_in_stored_artifacts` | scans **every object** in the mock bucket for the credential values; must be empty |
| `test_r1_intentional_provider_disablement_is_respected` | `enabled: false` → not attempted, not gated, not requested |
| `test_r1_connector_uses_injected_env_not_process_environment` | the unit-level root cause, plus that the registry instance is unmutated |

**Verdict: PASS locally.** The live gate stays unpassed — no real credential exists, so no
authenticated search has ever returned results. A credential alone does not close it (§6).

---

## 3. R2 — honest pagination

### Reproduced

`HimalayasConnector` inherited `BulkFeedConnector` and requested `?limit=100`. Given a synthetic
response announcing `nextCursor` and `totalCount: 500`, the run made **1 request**, captured 20 jobs,
recorded **0 backlog items**, **0 saturated families**, and coverage read complete.

Provider contract, rechecked 2026-09-24 at `https://himalayas.app/api`:

> "limit: the number of jobs to retrieve (max 20)"
> "cursor: your position in the feed. Leave it off the first request, then pass back the nextCursor
> value from each response. This is the preferred way to paginate."
> "offset: … Deprecated, and it will be removed in a future release. Use cursor instead."

So `limit=100` was silently capped at 20 and the rest of the feed was unreachable.

### Repaired

- New `PaginatedFeedConnector` with `endpoint(cursor)` / `next_cursor(payload)`. Himalayas uses it
  with `page_size=20` — the documented maximum — and a 5-page-per-run budget.
- The discovery stage walks the cursor, then **persists where it stopped** in
  `DiscoveryState.source_cursors[provider]`, and resumes there next run.
- A failed or rate-limited page **keeps its cursor** so the next run retries that exact page. A
  skipped page is a lost employer.
- A repeated cursor stops the walk and is recorded as inaccessible, but does **not** mark the feed
  exhausted — stopping early is not finishing, and coverage stays PARTIAL.
- Backlog entries became `BacklogItem` records instead of positional tuples, because the work now has
  four dimensions (family, phrase, page, location scope) and a tuple silently changes meaning when a
  dimension is added.
- The same loss mode was checked on the query feed: a full Adzuna page marks the family saturated and
  queues page + 1 (`test_r2_adzuna_full_page_queues_its_next_page`). Failed queries return to the
  backlog rather than vanishing.

### Live verification (`evidence/himalayas_live_pagination.txt`)

`evidence`, public read-only, 2026-09-24:

```
page 1: jobs=20  new employers=10  nextCursor=yes
page 2: jobs=20  new employers=18  nextCursor=yes
page 3: jobs=20  new employers=18  nextCursor=yes
page 4: jobs=20  new employers=14  nextCursor=yes
page 5: jobs=20  new employers=16  nextCursor=yes
TOTAL across 5 pages: 76 distinct employers
```

In the repaired rehearsal against those real bytes: **96 Himalayas postings across 74 employers**,
versus **20 postings / ~19 employers** under P01. A live `nextCursor` remained after page 5, so the
cursor was saved, one backlog item recorded, and coverage reported PARTIAL.

**Verdict: PASS.**

---

## 4. R3 — screening polarity and whose work a sentence describes

### Reproduced

All four excluded before repair, none stating a forbidden duty of the candidate:

| Input | Wrong exclusion |
|---|---|
| `No security clearance is required.` | clearance-government |
| `We do not require a recorded video.` | recorded-video |
| `Build tools for the sales team to research prospects.` | sales-ownership |
| `…output reaches members or prospects.` (Future, real captured posting) | sales-ownership |

### Repaired at the root, not by adding exceptions

Two distinct root causes, fixed separately:

**Polarity.** New `clause_around` + `polarity` read the *clause* containing the match — not the whole
sentence, so `Python is required, no clearance is needed` cannot let the first half negate the second.
Polarity returns `required` / `negated` / `optional`, and every rule branch (clearance, video,
AI interview, frontend depth, sales) now consults it. `optional` is distinguished from `negated`
because "a clearance is a plus" is not a requirement but is still worth a human glance.

**Whose duty.** `describes_a_software_artifact` detects a software frame in the clause
("build/maintain/… tools|platform|dashboard…", or "tools that/for/used by…"), and
`describes_own_duty` detects a candidate-duty frame ("you will", "your responsibilities"). Sales
vocabulary inside a software frame is about the product, not the duty.

`_SALES_OWNERSHIP_RE` was also tightened: **bare `prospects` was removed.** It is a noun for the
people a product reaches, and it alone caused two of the four misfires. `prospecting`, `prospect for`
and `generate/source prospects` — activities — remain.

**Ambiguity now routes to review.** Sales-adjacent language in a duty frame with no software frame
and no ownership phrase yields `PENDING_CHECK`, not a verdict
(`test_r3_ambiguous_scope_is_retained_for_review_not_discarded`).

**HTML entities.** `norm_text` now runs `html.unescape` **first**, and `screen_job` decodes
defensively too. `doesn&#39;t require` had been read as `require`. This is a root-level fix: entity
decoding is load-bearing for polarity, not cosmetic.

### Paired tests, both directions

23 R3 tests. Every negated/optional/tooling case is paired with the genuine exclusion it must not
erase: real quota/pipeline/closing ownership, a real TS/SCI or Public Trust requirement, and real
recorded-video and one-way-video processes all still exclude.

### Audit of the captured exclusions (`evidence/exclusion_audit.json`)

All **364** postings P01 excluded, re-screened by ruleset 1.1.0 against the *same captured bytes*:

| | count |
|---|---:|
| dispositions changed | **34** |
| released — `sales-ownership` | 30 |
| released — `location-eligibility` | 4 |
| still excluded — sales-ownership | 109 |
| still excluded — location-eligibility | 250 |
| still excluded — clearance-government | 11 |
| still excluded — frontend-specialist | 8 |
| still excluded — recorded-video | 2 |

**A released exclusion is not an endorsement.** It means the stated reason for removing the posting
does not hold. `evidence/exclusion_audit_downstream.json` carries the number that actually matters:

> Of the 34 released rows, **2 reach the candidate list** after ordinary fit scoring; **32 are still
> rejected there** — they were non-engineering roles (operations coordinator, legal counsel, product
> marketing) that fit scoring rejects independently of screening.

The two recovered:

| Employer | Title | fit | screen |
|---|---|---:|---|
| Nimble Gravity | Senior Architect, Anthropic Enablement | 0.36 | PENDING_CHECK |
| Future | Full-Stack Growth Engineer | 0.32 | ELIGIBLE |

Future's Full-Stack Growth Engineer is the exact posting the review cited. Neither is an approved
application; both are candidates for the downstream research step.

**Verdict: PASS.**

---

## 5. R4 — deployment and rollback readiness

### Reproduced (`evidence/rollback_validation.txt`)

The P01 command, validated only, no AWS operation:

```
$ aws scheduler update-schedule --name jprs-discovery-daily --state DISABLED \
      --generate-cli-skeleton output
aws: error: the following arguments are required: --flexible-time-window, --schedule-expression, --target
```

`UpdateSchedule` is a **full replace**, so a bare `--state DISABLED` would drop the schedule's other
fields even if the CLI accepted it.

The P01 full rollback, `git checkout e549a73 -- src/ infra/ config/`, would have **overwritten the
uncommitted P01 and P02 implementation** — which exists in no commit — with no copy anywhere.

The `$0 additional in practice` cost claim asserted free-tier eligibility that was never checked.

### Repaired

- **Partial disable**: the field-preserving `get-schedule` → edit `State` → `update-schedule
  --cli-input-json` round-trip, validated to exit 0 with `--generate-cli-skeleton output`. A
  CloudFormation alternative is given to avoid drift. It is labelled a *partial* disable and states
  that it **does not revert** the screening/report code.
- **Full rollback**: `git worktree add /tmp/jprs-rollback e549a73`, build and deploy from there. The
  working tree is never checked out, reset, stashed or staged. The exact deployed revision is named.
- **Cost**: bounded from primary sources with assumptions stated. The CloudWatch alarm price came
  from AWS's Price List API (`CW:AlarmMonitorUsage`, **$0.10 per standard-resolution alarm-metric per
  month**, us-east-1). Total new cost ≈ **$0.10–0.15/month, dominated by the alarm**. The free-tier
  claim is withdrawn; S3's line is explicitly marked as an assumption not sourced from the primary
  API this run.
- **Gates table** distinguishing resolver success, a proposed registry row, and actual monitoring —
  the three things the review said must not be conflated. No claim that one switch closes a gate.

Five tests assert these properties of the handoff document itself, so a future edit that reintroduces
the invalid command or the destructive checkout fails the suite.

**Verdict: PASS.**

---

## 6. Gates that remain unpassed

Stated as gates, not as formalities.

| Gate | Why it is still open |
|---|---|
| **Adzuna general-industry coverage** | No real credential exists. R1 makes the path *work*; the gate closes only when an authenticated search returns results in production and the receipt shows Adzuna under `discovery_succeeded`. A credential alone does not close it. |
| **Production fetch transport, 3 of 4 feeds** | This machine's egress proxy truncates them (`IncompleteRead`, and `BadStatusLine: CONNECT` on retry). Parsing/mapping/screening are verified on real live bytes; the `fetch_raw` path is not. Post-deploy check 1. |
| **Careers-URL resolution live path** | Off by default; the guard's DNS resolution is blocked in this sandbox. |
| **Discovery → monitoring loop** | Not implemented by design. It writes *proposed* registry rows; applying them is an operator action. |
| **Independent review of screening** | Not obtained (§7). |

Bounded claims corrected from P01, per the review:

- The Ashby UUID observation is a **single point-in-time reading**: a posting published 2021-04-27 is
  currently listed under a UUID. That does **not** demonstrate the identifier was unchanged
  throughout. P01's phrasing overstated it; the connector's fallback ladder stays tested precisely
  because permanence is assumed, not proven.
- Repeated successful downloads do not prove every partial-feed failure mode is excluded.
- The P01 coverage comparison isolates *source footprint* under the new code; it is not a controlled
  comparison of old versus new scoring.

---

## 7. Review shape, honestly disclosed

The packet authorizes independent reviewer contexts "if available" and forbids simulating them.

**No independent reviewer context was run for this repair.** One implementation context produced it,
so §2–§5 are self-review with separate passes. No agents or votes are invented.

The genuinely independent input this repair rests on is the **orchestrator review itself** — a context
that did not write the P01 code and found four defects that context had missed, including two serious
ones. That is the strongest evidence in this run that independent review works here, and it is an
argument for obtaining one on the repaired screening rules before deployment: a screening misfire
silently discards an opportunity, and the failure is invisible in the output.

### Contract changes, explicitly justified

| Change | Justification |
|---|---|
| `allocate(backlog_first=…)` takes `BacklogItem`, not tuples; `tests/test_discovery.py` updated | the work gained a location-scope dimension; a positional tuple silently changes meaning when a dimension is added, which is how deferred work goes missing |
| `SCREENING_RULESET_VERSION` 1.0.0 → 1.1.0 | verdicts are not comparable across the polarity repair; stamped on every result |
| `SourceReceipt.endpoint_url` is now redacted | a stored receipt must not carry a credential |
| Report gains a below-threshold count | see §8 |

---

## 8. Reconciled counts, and one gap the policy comparison exposed

`policy-check` flagged that `APPLICATION_WORKFLOW.md` had changed again. Compared semantically before
refreshing, as the packet requires: **no exclusion was added, removed or altered.** The five hard
rejections and the two "do not reject" guards are unchanged. The additions are workflow scope, and two
of them constrain JPRS rather than gate it:

> "JPRS discovers openings broadly, supplies posting provenance and available factual employer
> information… It need not infer culture from keywords."
> "Research can raise or lower a candidate's priority; the initial JPRS score is not a final
> rejection gate."

No company-vibe scoring was added, and no new hard gate was inferred from research instructions.

That comparison did expose a real gap: postings scoring below the fit floor appeared in **no** readable
section — only in the JSON — which is the same "hidden in JSON" pattern P01 was criticized for, and it
sits against the workflow's "preserve promising overflow… rather than silently discarding". The report
now states the count explicitly and says it is not a verdict.

Repaired rehearsal, `rehearsal/combined_repaired/`, against live bytes:

| | P01 combined | P02 repaired |
|---|---:|---:|
| postings considered | 747 | **821** |
| Himalayas postings / employers | 20 / ~19 | **96 / 74** |
| discovery employers (none in registry) | 162 | **221** |
| retained credible | 43 | 44 |
| new strong / needs a check | 14 / 22 | 16 / 21 |
| policy exclusions | 364 | 374 |
| below fit threshold | *unstated* | **403, now stated** |
| discovery coverage axis | PARTIAL | PARTIAL |
| Adzuna | absent from the receipt | **named as credential-gated** |

The retained count barely moved (43 → 44) while the footprint grew substantially. That is the expected
shape: pagination adds reach, and screening/scoring still decide. Raw counts are not the result.

---

## 9. Acceptance rows

| Row | Verdict | Evidence |
|---|---|---|
| **R1** default handler + mocked SSM exercises authenticated Adzuna; missing credentials visible; intentional exclusions respected; location coverage verified; no credential leak | **PASS** (live gate still open) | §2, 6 tests incl. a full-bucket credential scan |
| **R2** unseeded employer beyond page one reaches the report; deferred/failed work survives and resumes; finite budgets give honest partial coverage | **PASS** | §3, 8 tests + live 5-page walk; 96/74 vs 20/19 |
| **R3** negated/optional requirements and work done for a sales team do not create false exclusions; real duties still excluded; ambiguous retained for review; captured audit accompanies the suite | **PASS** | §4, 23 tests + 364-posting audit |
| **R4** locally validated rollback preserves state and work; names remaining approvals, live gates, source-growth limits and defensible cost | **PASS** | §5, CLI validation transcript + Price List API |
| Existing tests green or contract changes justified; SAM validates/builds; report complete and readable; source-policy changes reconciled | **PASS** | §1, §7, §8 |
| Whole-object: can useful unknown-employer openings reach Brett without overfitted screening? | **PASS, with the gates in §6 open** | 221 registry-absent employers reached the system; 44 retained with links and reasons; 34 wrong exclusions released, of which only 2 were real opportunities — the audit is what keeps that honest |
