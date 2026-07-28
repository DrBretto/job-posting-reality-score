# DATA_MODEL_AND_HISTORY_SPEC — Job Posting Reality Score

Seat: ADHOC-DATA-ANALYTICS-ARCHITECT · Lens: history + truth model
Packet: PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727
Status: ROADMAP ONLY — no AWS resources, no application code. Design + Pydantic-shaped schemas only.

---

## 0. The invariant this whole spec exists to protect

> **A `disappeared` change-event may ONLY be emitted when it is diffed against a SUCCESSFUL
> snapshot of the same source.** A failed, partial, throttled, or empty-on-error fetch NEVER
> marks jobs removed. Source failure and "nothing changed" and "job actually removed" are three
> different states and must never collapse into one.

Every model below is shaped to make this invariant structurally enforced, not merely a hope in
business logic. The pivot is the **SourceSnapshot.status** field: the diff engine is *forbidden by
contract* from computing removals from any snapshot whose status is not `SUCCESS`.

---

## 1. Identity model

Two identity layers: the **source** (a company's board on one ATS) and the **job** (one posting).

### 1.1 Stable SOURCE identifier

A source is one `(provider, board_token)` pair. Deterministic, human-legible, stable forever.

```
source_id = "{provider}:{board_token}"
  provider   ∈ {greenhouse, lever, ashby}
  board_token = the provider's own board slug (Greenhouse board_token,
                Lever SITE, Ashby job-board name)

examples:
  greenhouse:stripe
  lever:leverdemo
  ashby:ramp
```

`source_id` is assigned by config (the operator adds a company), never derived from response
content, so it survives even a totally failed fetch. This is what lets a failed snapshot still be
*attributed* to the right source without touching any job.

### 1.2 Stable JOB identifier — per ATS, with content-hash fallback

Goal: a `job_id` that is (a) stable across days for the same real posting and (b) namespaced by
source so two providers can never collide.

```
job_id = "{source_id}#{provider_key}"
```

`provider_key` is chosen per ATS by the following verified capability (retrieved 2026-07-28):

| ATS | Native stable id? | provider_key strategy | id_kind |
|---|---|---|---|
| **Greenhouse** | YES — `id` + `internal_job_id`, both stable; `updated_at` present | `provider_key = str(id)`; also store `internal_job_id` | `NATIVE_ID` |
| **Lever** | YES — `id` is a stable UUID | `provider_key = id` (UUID) | `NATIVE_ID` |
| **Ashby** | NO documented id field in the public posting-api response | see fallback below | `URL_SLUG` or `CONTENT_HASH` |

**Ashby fallback strategy (ordered):**
1. **URL-slug id (preferred):** the `jobUrl` / `applyUrl` for an Ashby posting embeds the posting's
   UUID (e.g. `.../<board>/<uuid>`). Parse the trailing UUID → `provider_key = ashby_url_uuid`,
   `id_kind = URL_SLUG`. This is stable while the posting lives.
   *(UNVERIFIED that Ashby guarantees this UUID is permanent — flagged; see §9.)*
2. **Content-hash id (last resort):** if no parseable UUID, synthesize a stable key from immutable-ish
   identity fields: `provider_key = "ch_" + sha256(title | department | team | primary_location |
   employmentType)[:16]`, `id_kind = CONTENT_HASH`. Note this can merge two genuinely-distinct
   openings with identical title+team+location; such a job carries flag `IDENTITY_LOW_CONFIDENCE`
   and its removals are downgraded to `probable-repost` reasoning rather than hard `disappeared`.

`id_kind` is stored on every JobIdentity so downstream scoring/confidence can discount weaker ids.

### 1.3 Content hash of canonical fields (change detection, all ATS)

Independent of identity, every snapshot of a job computes a **content_hash** over the *canonical field
set* (§2). This is what detects "the posting changed" even where the ATS gives no `updated_at`
(Lever, Ashby). Field-scoped sub-hashes let us name *what* changed without re-diffing full text.

```
content_hash        = sha256( canonical_json(job) )               # whole-posting fingerprint
field_hashes = {
  "title_hash":      sha256(norm(title)),
  "location_hash":   sha256(norm(canonical_location)),
  "salary_hash":     sha256(norm(salary_struct)),
  "workmode_hash":   sha256(norm(remote_hybrid_language)),
  "body_hash":       sha256(norm(description_text)),
}
```

`canonical_json` = JSON with sorted keys, whitespace-collapsed strings, null-normalized, over the
canonical field set ONLY (raw/provider-noise excluded) so cosmetic re-serialization by the ATS does
not create false "changed" events.

---

## 2. Canonical field set

The normalized, provider-agnostic shape every job maps into. Raw provider payload is retained
separately (§3); canonical is the diff/score surface.

```
CanonicalJob:
  # identity
  source_id: str
  job_id: str
  id_kind: enum(NATIVE_ID | URL_SLUG | CONTENT_HASH)
  provider_native_id: str | null      # Greenhouse id / Lever UUID / Ashby url-uuid
  provider_internal_id: str | null    # Greenhouse internal_job_id
  requisition_id: str | null          # Greenhouse requisition_id (repost signal)

  # content (canonical)
  title: str
  department: str | null
  team: str | null
  canonical_location: str             # normalized (§4)
  raw_location: str | null
  remote_hybrid_language: enum(REMOTE | HYBRID | ONSITE | UNSPECIFIED)
  employment_type: enum(FULL_TIME | PART_TIME | CONTRACT | INTERN | TEMP | UNSPECIFIED)
  salary: SalaryStruct | null         # {min, max, currency, period, source: STATED|PARSED|NONE}
  description_text: str               # plaintext-normalized body
  posting_url: str
  apply_url: str | null

  # provider-supplied timing (only where the ATS actually gives it)
  provider_created_at: datetime | null   # Lever createdAt (ms epoch); Greenhouse none
  provider_updated_at: datetime | null   # Greenhouse updated_at; Lever/Ashby none
  provider_published_at: datetime | null # Ashby publishedAt

  # our derived timing (authoritative for "first seen")
  first_seen_at: datetime             # OUR first successful observation (never provider-claimed)
  last_seen_at: datetime              # OUR most recent successful observation

  # hashing
  content_hash: str
  field_hashes: dict[str,str]

  # meta
  schema_version: str                 # e.g. "1.0.0"
  ingested_snapshot_id: str           # SourceSnapshot that produced this canonical record
```

**Rule — dates are ours, not theirs.** `first_seen_at` is defined as the earliest SUCCESSFUL
snapshot in which we observed this `job_id`. Provider `created_at/published_at` are stored as
*evidence* but are NEVER the authority for "first seen" (a provider can backfill or lie). The LLM may
never invent either.

---

## 3. Raw-evidence retention & snapshots

### 3.1 SourceSnapshot — the fetch envelope (the invariant lives here)

Every scheduled fetch of one source produces exactly one SourceSnapshot, **whether it succeeded or
not.** This is the object the disappearance rule keys on.

```
SourceSnapshot:
  snapshot_id: str            # ulid, time-sortable
  source_id: str
  fetched_at: datetime
  status: enum(
     SUCCESS,                 # full, well-formed, complete response
     PARTIAL,                 # response received but truncated/paginated-incomplete/some-jobs-unparseable
     FETCH_FAILED,            # network/timeout/5xx/429/DNS — NO usable job list
     EMPTY_SUCCESS            # valid 200 with a genuinely empty job list (rare, real "board cleared")
  )
  http_status: int | null
  job_count_observed: int | null
  bytes: int | null
  raw_object_key: str         # S3 key of the immutable raw payload (below)
  request_receipt: SourceReceipt
  error_class: str | null     # timeout | http_5xx | http_429 | parse_error | dns | tls | schema_mismatch
  notes: str | null
```

**EMPTY_SUCCESS vs FETCH_FAILED is the sharpest line in the system.** An empty list is only trusted
as real if the HTTP layer cleanly returned 200 with a well-formed (empty) body AND the provider
schema validated. Any doubt → `PARTIAL` or `FETCH_FAILED`, never `EMPTY_SUCCESS`.

### 3.2 SourceReceipt — provenance stamp

```
SourceReceipt:
  provider: str
  endpoint_url: str           # exact URL called
  request_at: datetime
  response_at: datetime
  http_status: int | null
  etag: str | null
  content_length: int | null
  connector_version: str
  raw_sha256: str             # hash of the exact bytes stored
```

Every generated explanation downstream must be able to cite a `snapshot_id` + `raw_object_key` +
`raw_sha256`. No claim without a receipt.

### 3.3 Immutable raw payload

The exact response bytes (gzipped) are written once, WORM-style, to the immutable-raw tier (§7) and
never mutated. Retention via S3 **lifecycle policy** (operator hard-rule: NEVER S3 versioning). Raw
is the court-of-record for any dispute about what a source actually returned on a given day.

---

## 4. Normalization

Deterministic, versioned, no LLM. Normalizer version is stamped into every canonical record.

- **Location:** lowercase, strip punctuation, expand known abbreviations, split multi-locations into a
  sorted list, map to a canonical `{city, region, country, is_multi, is_remote_token}` struct;
  `canonical_location` = deterministic string render of that struct.
- **Remote/hybrid language:** map ATS enums + keyword scan of body → `{REMOTE|HYBRID|ONSITE|UNSPECIFIED}`.
  Ashby `workplaceType`/`isRemote` and Lever `workplaceType` map directly; Greenhouse has no enum so
  derive from location tokens + body keywords (rules table, versioned).
- **Salary:** prefer structured provider comp (Ashby `compensation`, Greenhouse metadata) → `STATED`;
  else deterministic regex parse of body → `PARSED`; else `NONE`. LLM never sets salary numbers.
- **Text:** strip HTML → plaintext, collapse whitespace, normalize unicode (NFKC). `body_hash` is over
  this normalized text so formatting-only edits don't fire `materially-changed`.

Normalizer changes are governed by schema versioning (§6): a normalizer version bump can change
hashes, so it triggers controlled reprocessing, not silent re-diffing.

---

## 5. Change-event taxonomy + state machine

### 5.1 The event types

Every daily diff of a source (only from a `SUCCESS` snapshot, see §5.3) emits zero or more
ChangeEvents per job. Full taxonomy:

| event | fires when | invariant guard |
|---|---|---|
| `first-seen` | job_id present now, absent in all prior successful snapshots | — |
| `no-material-change` | job_id present, `content_hash` unchanged | — |
| `materially-changed` | `content_hash` changed but no more-specific field event applies (e.g. body) | names changed field_hashes |
| `location-changed` | `location_hash` changed | subtype of material change |
| `salary-changed` | `salary_hash` changed | subtype |
| `remote-hybrid-language-changed` | `workmode_hash` changed | subtype |
| `disappeared` | job_id seen in the prior SUCCESSFUL snapshot, absent now, past grace | **REQUIRES current snapshot.status == SUCCESS** |
| `returned` | job_id previously `disappeared`, now present again | — |
| `probable-repost` | a new job_id closely matches a recently `disappeared` job_id (repost match, §5.4) | confidence-scored |
| `source-fetch-failed` | current snapshot.status == FETCH_FAILED | emitted at SOURCE level, ZERO job removals |
| `source-response-partial` | current snapshot.status == PARTIAL | job removals SUPPRESSED |

`source-fetch-failed` and `source-response-partial` are **source-scoped** events, not job-scoped.
They are how the quiet report says "the collectors did not run / ran incompletely" as distinct from
"nothing changed."

### 5.2 Job lifecycle state machine

```
                 first-seen
        (none) ─────────────► ACTIVE
                                │  ▲
        materially/location/    │  │ no-material-change (self-loop)
        salary/workmode-changed │  │
        (self-loop, stays ACTIVE)  │
                                │  │ returned
                 absent in      ▼  │
                 SUCCESS snap   PENDING_REMOVAL ──(present again within grace)──► ACTIVE
                 (grace clock)      │
                                    │ still absent after grace (in a SUCCESS snap)
                                    ▼
                                 DISAPPEARED ──(seen again later, SUCCESS snap)──► ACTIVE (emit `returned`)

     any state, if current snapshot.status ∈ {FETCH_FAILED, PARTIAL}:
        → state is FROZEN. No transition toward PENDING_REMOVAL/DISAPPEARED. Grace clock PAUSES.
        → emit source-scoped source-fetch-failed / source-response-partial only.
```

### 5.3 The successful-snapshot requirement (encoded)

The diff engine's contract:

```
def diff(prev_success: SourceSnapshot, current: SourceSnapshot):
    if current.status in (FETCH_FAILED, PARTIAL):
        emit source-scoped event only; FREEZE all job states; PAUSE grace clocks; return.
    # current.status ∈ {SUCCESS, EMPTY_SUCCESS} below
    # removals computed ONLY against prev_success (the most recent SUCCESS/EMPTY_SUCCESS snapshot),
    # never against a failed/partial one.
```

"Prior snapshot" for disappearance purposes ALWAYS means "most recent snapshot with
status ∈ {SUCCESS, EMPTY_SUCCESS}", skipping over any intervening failed/partial ones. A three-day
outage therefore produces three `source-fetch-failed` events and ZERO false `disappeared` events.

### 5.4 Disappearance GRACE rule

A single-day absence is not a removal (ATS pagination flake, transient de-listing). A job goes:

```
ACTIVE → PENDING_REMOVAL   on first absence in a SUCCESS snapshot
PENDING_REMOVAL → DISAPPEARED  only after it is absent in N consecutive SUCCESS snapshots
```

Default `grace_successful_snapshots = 2` (i.e. absent in 2 consecutive SUCCESS snapshots → declared
`disappeared`). **Grace is counted in SUCCESSFUL snapshots, not calendar days** — this is what makes
the grace clock immune to outages. `returned` inside grace cancels the pending removal silently
(reported as a churn signal, not a disappearance).

### 5.5 Repost-matching confidence

When a `first-seen` job appears shortly after a `disappeared` job in the same source, score a
repost match deterministically (no LLM):

```
repost_score = weighted match over:
  same requisition_id (Greenhouse)        → +0.5  (strong)
  same normalized title                    → +0.2
  same canonical_location                  → +0.15
  same department/team                     → +0.1
  body_hash similarity ≥ threshold         → +0.05
within reopen_window (default 30 days)
```

`repost_score ≥ 0.7` → emit `probable-repost` linking old_job_id ↔ new_job_id.
Below that → they stay independent (`first-seen` + `disappeared` unlinked). Confidence is stored;
the report says "likely the same role reposted (confidence X)", never "this is a fake churned job."

---

## 6. Schema versioning & reprocessing

- `schema_version` (semver) stamped on every canonical record AND every change-event.
- `normalizer_version` and `connector_version` stamped separately (a normalizer change can move
  hashes without a schema-shape change).
- **Reprocessing behavior:** raw payloads are immutable and complete, so any canonical/normalizer/
  scoring version can be **replayed from raw** to regenerate canonical + change-events without a new
  fetch. Reprocessing writes to a NEW normalized/change-event partition keyed by version; it never
  overwrites prior derived history (audit trail preserved; also honors "no S3 versioning" since we
  version via key prefix, not object versions).
- **Additive-first rule:** minor version = additive fields (old readers ignore). Major version =
  breaking shape or hash-definition change → requires a full replay-from-raw before the diff engine
  trusts cross-version continuity (else a job would falsely look `materially-changed` purely because
  the hash definition moved).

---

## 7. S3 layout / prefixes (five tiers)

Single bucket, tiered prefixes. Partitioned by `source_id` components + date for cheap Athena later.
No versioning; lifecycle policies handle retention.

```
s3://<bucket>/
  current/                                     # tier 1: latest known state, overwritten each run
    provider=<p>/board=<b>/current_jobs.json         # last successful canonical set (fast "what's live now")
    provider=<p>/board=<b>/_source_status.json       # last snapshot status (drives "did collectors run")

  raw/                                         # tier 2: immutable court-of-record, WORM + lifecycle
    provider=<p>/board=<b>/dt=YYYY-MM-DD/snapshot=<ulid>.json.gz
    provider=<p>/board=<b>/dt=YYYY-MM-DD/receipt=<ulid>.json

  normalized/                                  # tier 3: canonical jobs, versioned, replayable
    schema_v=<major>/provider=<p>/board=<b>/dt=YYYY-MM-DD/jobs.parquet   # (JSON at V1, see §8)

  events/                                      # tier 4: change-event log, append-only
    schema_v=<major>/provider=<p>/board=<b>/dt=YYYY-MM-DD/events.parquet # (JSON at V1)

  reports/                                     # tier 5: daily human report + scoring output
    dt=YYYY-MM-DD/daily_report.json
    dt=YYYY-MM-DD/daily_report.md
```

Partition keys `provider=`, `board=`, `dt=` are Hive-style so Athena partition projection (§8)
works with zero Glue crawler. `schema_v=` as a top prefix on derived tiers makes version-scoped
replay a clean key-prefix operation.

---

## 8. JSON → Parquet → Athena evolution + the exact trigger

**V1 = JSON everywhere.** At learning scale (1 provider, 3 companies, 1 run/day) the entire history
is a few MB. Querying it is a Lambda reading JSON, or `aws s3 cp` + `jq`. Athena/Parquet at this
scale is pure ceremony and burns money per-query for no benefit. Do NOT stand up Athena at V1.

**Parquet:** introduce Parquet for the `normalized/` and `events/` tiers when the data is (a) columnar-
queried repeatedly and (b) large enough that JSON scan cost matters. Parquet write is a thin
converter step (must run in a separate worker, NOT a fat Lambda — respects the no-pandas-in-handler
rule; use a lightweight Parquet writer or an async Fargate/Batch task if ever needed).

**The EXACT trigger at which Athena earns its place — ALL of:**
1. **Cross-day analytical questions become routine** — "hiring momentum over 90 days", "repost rate
   per company over a quarter" — i.e. the mature "historical intelligence" layer is actually being
   built, not hypothetical; AND
2. **≥ ~20 companies across ≥ 2 ATS providers with ≥ ~60 days of accumulated `events/` history**
   (roughly the "useful personal scale → expansion" boundary in shared context), so a full-history
   scan in a Lambda starts being slow/awkward; AND
3. A query pattern exists that a single Lambda pass over `current/` cannot answer cheaply (multi-
   partition aggregation).

Until all three hold, Athena is not created.

**When it earns its place — how (verified 2026-07-28):** define the table **manually via
`CREATE EXTERNAL TABLE` with partition projection** — NO Glue crawler (paid, banned), NO Glue job.
Partition projection (`projection.enabled='true'`) makes Athena compute partitions from the S3 path
template, so no `MSCK REPAIR`, no crawler, and Athena ignores any Glue catalog partition metadata.
Cost is Athena's per-TB scanned only (partition + Parquet columnar pruning keep scans tiny). Sketch:

```sql
CREATE EXTERNAL TABLE events (
  job_id string, source_id string, event_type string,
  content_hash string, ... )
PARTITIONED BY (schema_v string, provider string, board string, dt string)
STORED AS PARQUET
LOCATION 's3://<bucket>/events/'
TBLPROPERTIES (
  'projection.enabled'='true',
  'projection.provider.type'='enum','projection.provider.values'='greenhouse,lever,ashby',
  'projection.board.type'='injected',
  'projection.schema_v.type'='enum','projection.schema_v.values'='1',
  'projection.dt.type'='date','projection.dt.range'='2026-01-01,NOW','projection.dt.format'='yyyy-MM-dd',
  'storage.location.template'='s3://<bucket>/events/schema_v=${schema_v}/provider=${provider}/board=${board}/dt=${dt}/'
);
```
*(UNVERIFIED detail: `injected` projection for `board` requires every query to filter on `board`;
alternative is `enum` seeded from the config company list. Confirm against the Athena partition-
projection docs at table-creation time.)*

---

## 9. Assumptions, failure modes, decisions, acceptance tests

### Assumptions
- A1: The three public ATS endpoints stay unauthenticated & JSON (verified 2026-07-28; re-verify per run).
- A2: Company/board list is small and operator-curated (config-driven, like CFR `settings.yaml`).
- A3: One scheduled run/day is enough resolution for "what changed" at V1.
- A4: Ashby `jobUrl` embeds a stable posting UUID (**UNVERIFIED** — see D3).

### Failure modes
- F1: Provider silently changes schema → connector parse_error → snapshot `PARTIAL`/`FETCH_FAILED`,
  removals suppressed (invariant holds). Detected by schema validation, not by empty results.
- F2: ATS returns 200 + empty list on their own outage → mis-read as `EMPTY_SUCCESS` → mass false
  removal. **Mitigation:** treat a drop from N>0 to 0 jobs as suspect — require the empty body to
  validate AND cross-check prior count; a 100%-drop auto-downgrades `EMPTY_SUCCESS` → `PARTIAL`
  pending a second confirming SUCCESS snapshot (see D2).
- F3: Ashby id instability → churny false `disappeared`/`first-seen`. Mitigation: `IDENTITY_LOW_
  CONFIDENCE` flag + downgrade removals to `probable-repost` reasoning.
- F4: Normalizer version bump moves all hashes → every job looks `materially-changed`. Mitigation:
  version-gated replay-from-raw before cross-version diffing (§6).

### KEY DECISIONS (decision · default · owner · trigger)
- **D1 grace length** · default 2 consecutive SUCCESS snapshots · owner Analyst/operator ·
  trigger: revisit if false-disappearance rate observed > ~5% or if run cadence changes from daily.
- **D2 full-drop-to-zero handling** · default auto-downgrade `EMPTY_SUCCESS`→`PARTIAL` on 100% drop,
  require a 2nd confirming SUCCESS before trusting board-cleared · owner Data-model seat ·
  trigger: any single incident of mass false removal.
- **D3 Ashby stable-id** · default URL-slug UUID, else content-hash fallback · owner Connector seat +
  Data-model seat · trigger: verify Ashby UUID permanence before Ashby is onboarded (A4/UNVERIFIED).
- **D4 Athena adoption** · default NOT until all three §8 conditions hold · owner operator ·
  trigger: mature analytics layer + ~20 companies/2 providers/60 days history.
- **D5 repost threshold** · default `repost_score ≥ 0.7`, reopen_window 30 days · owner Scoring seat ·
  trigger: tune against observed labeled reposts.

### ACCEPTANCE TESTS (concrete)
- **T1 (THE invariant):** Feed prev=SUCCESS(10 jobs), current=FETCH_FAILED. Assert: zero `disappeared`
  events; exactly one `source-fetch-failed`; all 10 job states unchanged; grace clocks not advanced.
- **T2:** prev=SUCCESS(10), current=PARTIAL(4 jobs parsed). Assert: zero `disappeared`; one
  `source-response-partial`; states frozen.
- **T3 grace:** job absent in 1 SUCCESS snap → state PENDING_REMOVAL, no `disappeared`. Absent in a
  2nd consecutive SUCCESS snap → `disappeared`. Reappears at snap-2 → `returned`, no `disappeared`.
- **T4 outage-through-grace:** SUCCESS(has job) → FETCH_FAILED → FETCH_FAILED → SUCCESS(missing).
  Assert the two failures do NOT count toward grace; job is only PENDING_REMOVAL (1 SUCCESS absence).
- **T5 content hash:** same job, ATS re-serializes JSON key order / whitespace only → `content_hash`
  unchanged → `no-material-change`.
- **T6 field event:** only salary changes → `salary-changed` fires; `location_hash`/`body_hash` stable.
- **T7 repost:** disappeared Greenhouse job + new job same `requisition_id` within 30d → `probable-repost`
  with confidence ≥ 0.7 linking both ids.
- **T8 full-drop guard (F2/D2):** prev=SUCCESS(10), current=200 empty list → NOT 10 `disappeared`;
  downgraded to `PARTIAL`, awaits confirming SUCCESS.
- **T9 replay:** re-run normalizer v-next from stored raw → regenerates canonical+events into a new
  `schema_v=` prefix without mutating prior partitions.
- **T10 dates:** assert `first_seen_at` equals earliest SUCCESS observation, never a provider
  `created_at/published_at`, and no code path lets the LLM set it.

### OPEN QUESTIONS for other seats
- Connector seat: confirm Ashby UUID permanence (A4/D3) and Lever `createdAt` reliability (undocumented,
  community-confirmed only — see connector spec).
- Scheduling/orchestration seat: is the "most recent SUCCESS snapshot" pointer stored in `current/
  _source_status.json` or Step Functions state? Data-model assumes the former.
- Scoring seat: consumes `events/` + `field_hashes` + repost confidence — confirm the field-hash
  contract is sufficient input for the churn dimension.

### Sources (retrieved 2026-07-28)
- Greenhouse Job Board API — https://developers.greenhouse.io/job-board.html (no auth; `id`,
  `internal_job_id`, `updated_at`, `requisition_id`).
- Lever postings API — https://github.com/lever/postings-api (no auth; `id` UUID; `createdAt` ms
  epoch is community-confirmed but UNDOCUMENTED, issue #35; no `updatedAt`).
- Ashby public posting API — https://developers.ashbyhq.com/docs/public-job-posting-api (no auth;
  `publishedAt`; NO documented stable id → fallback required).
- Athena partition projection — https://docs.aws.amazon.com/athena/latest/ug/partition-projection.html
  (no crawler needed; Athena ignores Glue partition metadata when projection enabled).
