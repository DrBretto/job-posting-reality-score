# SOURCE_CONNECTOR_AND_COMPLIANCE_SPEC — Job Posting Reality Score

Seat: ADHOC-DATA-ANALYTICS-ARCHITECT · Lens: per-ATS connector contract + compliance posture
Packet: PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727
Status: ROADMAP ONLY. Sanctioned PUBLIC ATS APIs only — NO scraping, NO auth bypass, NO LinkedIn,
NO contact harvesting, NO auto-apply, NO message sending.

All endpoint facts below verified against primary sources 2026-07-28 (URLs in §6).

---

## 1. The connector contract (all ATS implement this shape)

Every connector is a pure function `fetch(source) -> SourceSnapshot` that:

1. Calls exactly ONE documented public endpoint over HTTPS, unauthenticated.
2. Sets a truthful, identifying `User-Agent` (see §5) — no spoofing, no rotation to evade.
3. Returns a `SourceSnapshot` (see Data-model spec §3) with a definite `status`:
   `SUCCESS | EMPTY_SUCCESS | PARTIAL | FETCH_FAILED`.
4. Writes the exact response bytes to the immutable `raw/` tier + a `SourceReceipt` BEFORE any
   parsing — so evidence exists even if parsing later fails.
5. Maps provider fields → the CanonicalJob field set (§3–4 of Data-model spec).
6. **NEVER** decides disappearance. A connector only reports what it fetched; the diff engine (never
   the connector, never the LLM) decides removals, and only from a SUCCESS snapshot.

**Status assignment rules (uniform across ATS):**

```
transport error / timeout / DNS / TLS / 5xx / 429      -> FETCH_FAILED (error_class set)
200 + body fails provider schema validation             -> PARTIAL  (parse_error)
200 + pagination incomplete (fewer pages than declared) -> PARTIAL
200 + well-formed + N>0 jobs                             -> SUCCESS
200 + well-formed + 0 jobs                               -> EMPTY_SUCCESS, BUT: if prior snapshot had
                                                           N>0, auto-downgrade to PARTIAL pending a
                                                           2nd confirming empty SUCCESS (full-drop guard)
```

The full-drop guard is THE connector-level defense of the invariant: a provider outage that returns
"200 empty" cannot, by itself, wipe the whole board.

---

## 2. Per-ATS connector specs

### 2.1 Greenhouse — VERIFIED, strongest identity

- **List endpoint:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
- **Single job:** `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{id}`
- **Auth:** NONE. "Job Board data is publicly available; authentication is not required for GET." (verified)
- **Stable id:** YES — `id` (job post) + `internal_job_id` (the job). Also `requisition_id`,
  and `updated_at` (last-update timestamp — enables true change timing, unique among the three).
- **`?content=true`** returns `content` (description) + `departments` + `offices`. Required for body
  hashing; without it, description is absent.
- **Field → canonical map:** `id`→provider_native_id (`id_kind=NATIVE_ID`, `job_id=source_id#id`);
  `internal_job_id`→provider_internal_id; `requisition_id`→requisition_id (repost signal);
  `title`→title; `location.name`→raw_location→normalize; `content`→description_text;
  `updated_at`→provider_updated_at; `offices`/`departments`→department/team; `absolute_url`→posting_url.
- **Partial handling:** Greenhouse returns all jobs in one response (no cursor pagination on the board
  jobs list); a truncated/malformed body → PARTIAL. Schema-validate the `jobs[]` array + required keys.
- **Rate/terms:** no published numeric rate limit for board GETs (UNVERIFIED specific limit). Posture:
  1 request/source/day is trivially within any reasonable public-API courtesy limit; honor 429/503
  with backoff → FETCH_FAILED if unresolved.

### 2.2 Lever — VERIFIED, stable id, weak timing

- **List endpoint:** `GET https://api.lever.co/v0/postings/{site}?mode=json`
  (EU tenants: `api.eu.lever.co`; pagination via `?skip=X&limit=Y`).
- **Single posting:** `GET https://api.lever.co/v0/postings/{site}/{posting-id}?mode=json`
- **Auth:** NONE for GET postings. (API key only for the POST/apply endpoint, which we do NOT use.) (verified)
- **Stable id:** YES — `id` is a stable UUID (e.g. `5ac21346-8e0c-...`). `job_id=source_id#uuid`,
  `id_kind=NATIVE_ID`.
- **Timing caveat:** `createdAt` (ms-epoch) IS returned in practice but is **UNDOCUMENTED** (lever/
  postings-api issue #35) — store as `provider_created_at` evidence only, never as `first_seen_at`
  authority. **No `updatedAt`** at all → change detection MUST rely on our `content_hash`, not a
  provider timestamp.
- **Field → canonical map:** `id`→provider_native_id; `text`→title; `categories.location`→raw_location;
  `categories.team`→team; `categories.department`→department; `categories.commitment`→employment_type;
  `workplaceType`→remote_hybrid_language; `descriptionPlain`→description_text; `hostedUrl`→posting_url;
  `applyUrl`→apply_url; `createdAt`→provider_created_at (evidence only). Salary: parse from body (`PARSED`)
  unless a structured comp field is present.
- **Partial handling:** paginated (`skip`/`limit`); an incomplete page walk (got fewer than a full
  final page's continuation) → PARTIAL. Validate each element has `id` + `text`.
- **Rate/terms:** documented 429 limit is on the *POST apply* path (>2 req/s) which we never call.
  No published GET rate limit (UNVERIFIED). Posture: 1 daily GET (few paginated calls) — negligible.

### 2.3 Ashby — VERIFIED endpoint, NO native id (fallback required)

- **List endpoint:** `GET https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}?includeCompensation=true`
- **Single posting:** none — the public posting-api is list-only, no per-id GET, no server-side filter.
- **Auth:** NONE. Public API for all currently-published postings. (verified)
- **Stable id:** **NO documented id field** in the public posting-api response. → fallback per
  Data-model spec §1.2:
  1. Parse the posting UUID from `jobUrl`/`applyUrl` (`.../<board>/<uuid>`) → `id_kind=URL_SLUG`.
     **UNVERIFIED** that Ashby guarantees this UUID's permanence — must confirm before onboarding Ashby.
  2. Else content-hash id (`id_kind=CONTENT_HASH`, flag `IDENTITY_LOW_CONFIDENCE`).
- **Field → canonical map:** `title`→title; `location`/`address.postalAddress`→raw_location;
  `secondaryLocations`→multi-location; `department`/`team`→department/team; `isRemote`/`workplaceType`
  →remote_hybrid_language; `employmentType`→employment_type; `descriptionPlain`/`descriptionHtml`→
  description_text; `publishedAt`→provider_published_at (evidence only, not `first_seen_at`);
  `compensation`→salary (`STATED`, only when `includeCompensation=true`); `jobUrl`→posting_url;
  `applyUrl`→apply_url; `isListed`→used to filter unlisted postings.
- **Partial handling:** single JSON response, list-only, no pagination; malformed body → PARTIAL.
  Note: "where data is missing in Ashby it is missing in this response" — treat missing optional
  fields as null, NOT as a parse failure.
- **Rate/terms:** none published for the public posting-api (UNVERIFIED). Posture: 1 daily GET.

---

## 3. Stable-id strategy summary

| ATS | verified endpoint | auth | native stable id | strategy | change-timing source |
|---|---|---|---|---|---|
| Greenhouse | YES | none | YES (`id`,`internal_job_id`) | `NATIVE_ID` | provider `updated_at` + our hash |
| Lever | YES | none | YES (`id` UUID) | `NATIVE_ID` | our `content_hash` (no `updatedAt`) |
| Ashby | YES | none | NO | `URL_SLUG` (UNVERIFIED perm.) → else `CONTENT_HASH` | our `content_hash` |

---

## 4. Partial-response handling (the compliance-side of the invariant)

The connector's ONLY job on trouble is to label the snapshot honestly; it never guesses at job state:

- Any doubt about completeness → `PARTIAL`, never `SUCCESS`. PARTIAL snapshots suppress ALL removals
  downstream (Data-model §5.3).
- Transport failure → `FETCH_FAILED`, emits a source-scoped `source-fetch-failed`, zero job effects.
- Full-drop-to-zero → `EMPTY_SUCCESS` auto-downgraded to `PARTIAL` pending confirmation (§1 guard).
- Every snapshot — including failures — writes a `SourceReceipt` (endpoint URL, http status, timing,
  raw sha256, connector_version) so "the collectors did not run" is provable, not inferred.

---

## 5. Terms / robots / compliance posture

- **Sanctioned public APIs only.** All three endpoints are the providers' own documented public
  job-board APIs, explicitly intended for third parties to render/consume published postings on
  external career pages. This is API consumption, not scraping.
- **No auth bypass, no evasion.** Unauthenticated because the provider offers these unauthenticated;
  we never defeat a login, paywall, captcha, or rate limiter. No UA rotation to dodge limits.
- **Honest identification.** Truthful `User-Agent` identifying the tool + contact (no personal
  contact info exposed per hard constraints — use a project/tool identifier). Respect `429`/`503` +
  `Retry-After` with backoff; on unresolved throttle → `FETCH_FAILED` (never hammer).
- **robots.txt:** these are JSON API hosts, not crawled HTML sites; robots is oriented at crawlers.
  Posture: still fetch politely at 1 req/source/day, honor server throttle signals, cache via ETag
  where offered. (UNVERIFIED whether each API host publishes API-specific terms — check each
  provider's API terms page before scaling company count; flagged.)
- **Scope discipline:** fetch ONLY published job-posting data. NO candidate data, NO contact
  harvesting, NO application submission, NO LinkedIn, NO message sending — all explicitly out of
  scope by packet hard constraints.
- **Data minimization + retention:** store only public posting fields + our derived history; retention
  via S3 lifecycle policy (NOT versioning). No PII beyond what the public posting itself contains.
- **Per-provider terms are subject to change:** connector carries `connector_version`; a provider
  schema/terms change is a finding to surface, handled as PARTIAL/FETCH_FAILED, never worked around.

---

## 6. Assumptions · failure modes · decisions · acceptance tests · sources

### Assumptions
- A1: The three endpoints remain unauthenticated + JSON (verified 2026-07-28; connector re-checks
  schema every run and fails safe to PARTIAL on drift).
- A2: Company/board tokens are operator-curated in config (like CFR `settings.yaml`).
- A3: 1 request/source/day is within every provider's courtesy limits (no published GET limit found).

### Failure modes
- F1: Provider adds auth / removes public access → FETCH_FAILED, surfaced as a finding; NEVER attempt
  auth bypass.
- F2: Ashby UUID not permanent → identity churn → `IDENTITY_LOW_CONFIDENCE`, removals downgraded to
  `probable-repost` (Data-model §1.2/§5.5).
- F3: Provider schema change → parse_error → PARTIAL → removals suppressed (invariant safe).
- F4: 200-empty on provider outage → full-drop guard downgrades to PARTIAL (§1).

### KEY DECISIONS (decision · default · owner · trigger)
- **D1 first ATS for V1** · default **Greenhouse** (strongest identity + `updated_at`) · owner operator ·
  trigger: shared-context V1 = 1 provider + 3 companies → start where identity is easiest.
- **D2 Ashby onboarding gate** · default DO NOT onboard Ashby until URL-slug UUID permanence is verified
  · owner Connector + Data-model seats · trigger: before adding any Ashby company.
- **D3 User-Agent identity** · default truthful tool identifier, no personal contact exposed · owner
  operator · trigger: none unless a provider requires a registered UA.
- **D4 request cadence** · default 1/source/day, ETag-cached, backoff on 429/503 · owner Scheduling seat ·
  trigger: raising company count toward expansion scale.
- **D5 provider terms recheck** · default re-read each provider's API terms before scaling past useful
  scale (~10–20 companies) · owner operator · trigger: company-count expansion.

### ACCEPTANCE TESTS
- **T1 auth-none:** each connector fetches its provider's public endpoint with NO credentials and
  parses a well-formed response (contract test against recorded fixtures, not live in CI).
- **T2 id mapping:** Greenhouse fixture → `id_kind=NATIVE_ID` with `id`+`internal_job_id`; Lever → UUID
  NATIVE_ID; Ashby → URL_SLUG when jobUrl has a UUID, else CONTENT_HASH + `IDENTITY_LOW_CONFIDENCE`.
- **T3 failure labeling:** simulated timeout→FETCH_FAILED; malformed 200→PARTIAL; empty-after-nonempty→
  PARTIAL (full-drop guard); clean empty-after-empty→EMPTY_SUCCESS.
- **T4 receipt-before-parse:** a fixture that fails parsing still produced a `raw/` object + SourceReceipt.
- **T5 no-removal-from-connector:** assert connectors emit SourceSnapshots only and never any
  disappearance/removal decision (that lives solely in the diff engine).
- **T6 field completeness:** canonical map covers every required CanonicalJob field per provider;
  missing optional Ashby fields → null, not PARTIAL.

### OPEN QUESTIONS for other seats
- Data-model seat: confirmed SourceSnapshot.status enum + full-drop guard are the shared contract (yes).
- Scheduling/orchestration seat: retry/backoff on FETCH_FAILED — retried within the same daily run
  (bounded) or deferred to next day? Connector assumes bounded in-run retry then FETCH_FAILED.
- Operator: which 3 companies for V1, and confirm all are on Greenhouse (per D1).

### Sources (retrieved 2026-07-28)
- Greenhouse Job Board API — https://developers.greenhouse.io/job-board.html
- Lever postings API — https://github.com/lever/postings-api (+ issue #35 on undocumented `createdAt`)
- Ashby public job posting API — https://developers.ashbyhq.com/docs/public-job-posting-api
