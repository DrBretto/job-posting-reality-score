# SCORING_AND_EVIDENCE_SPEC — Job Posting Reality Score

Seat: ADHOC-DATA-ANALYTICS-ARCHITECT · Lens: transparent scoring + evidence model
Packet: PKT-CAREER-JOB-POSTING-REALITY-SCORE-ROADMAP-COMMITTEE-V1-20260727
Status: ROADMAP ONLY.

---

## 0. The two hard rules that shape everything

1. **Never claim a posting is fake/real.** The system expresses observable *behavior* + *confidence*,
   never an accusation of fraud. "Reality Score" names how much the posting's *behavior in the record*
   looks like an actively-hiring role — it is NOT a lie-detector verdict.
2. **The LLM is a narrator, never the authority.** An LLM MAY summarize/explain evidence in prose. It
   MAY NOT invent dates, decide whether a job disappeared, compute any score, or set any field that
   feeds a score. Every generated sentence cites specific stored evidence (snapshot_id / event_id /
   field_hash). Scores are 100% deterministic Python over stored change-events + canonical fields.

---

## 1. Separately inspectable dimensions (NOT one opaque number)

Each job carries a **DimensionScorecard**: independent, individually explainable sub-scores. There is
NO single hidden blend that can't be decomposed. A composite is *offered* only as a convenience view
and is always shown alongside its parts.

| # | dimension | measures (from stored evidence) | primary inputs |
|---|---|---|---|
| 1 | **brett_fit** | role↔Brett match (skills/level/domain) | canonical fields; reuses CFR-style scoring vocab |
| 2 | **freshness** | how recently first-seen / last-changed | `first_seen_at`, last `materially-changed` event |
| 3 | **hiring_activity_evidence** | signs of an active, tended req | `updated_at` cadence, edits over time, still-live duration |
| 4 | **repost_churn_pattern** | repost/re-list behavior | `probable-repost` links, disappear/return cycles |
| 5 | **source_data_confidence** | how trustworthy the record itself is | `id_kind`, snapshot statuses, partial/failed history |
| 6 | **application_priority** | derived rank = where effort likely pays | deterministic function of 1–5 |
| 7 | **observed_application_outcome** *(later)* | what actually happened after applying | operator-entered outcome events |

Each dimension emits `{score, band, confidence, evidence_refs[], version}`. `band` ∈
{HIGH, MEDIUM, LOW, UNKNOWN} so the operator reads a label, not just a float. `UNKNOWN` is a
first-class value — a dimension with insufficient evidence says so, it does not default to a middle
number.

### Dimension detail

- **brett_fit** — deterministic keyword/level/domain rules over canonical `title`, `department`,
  `description_text` (reuse the CFR heuristic-score pattern; LLM may *explain* fit but the score is
  rule-based). Weights/keywords live in a versioned `fit_ruleset`.
- **freshness** — `days_since_first_seen`, `days_since_last_material_change`. A req first-seen 400
  days ago that never changes scores LOW freshness (stale). Purely date arithmetic over stored events.
- **hiring_activity_evidence** — countable behaviors ONLY: number of `materially-changed` events,
  presence of `updated_at` movement (Greenhouse), continuous-live duration. Never "this looks
  legit" — always "N edits in M days; last edit D days ago."
- **repost_churn_pattern** — from `probable-repost` links + disappear/return cycles. High churn is
  reported neutrally: "reposted 3× in 90 days (confidence 0.8)" — an *observation*, explicitly NOT
  "this is a fake evergreen posting."
- **source_data_confidence** — downgraded when `id_kind = CONTENT_HASH` (weak identity), when the
  source's recent snapshots include PARTIAL/FETCH_FAILED (record has gaps), or when few successful
  observations exist. This is what stops a shaky record from masquerading as a confident signal.
- **application_priority** — deterministic combiner (below). This is the only dimension meant to be
  a ranking; it is still fully decomposable to its inputs.
- **observed_application_outcome** — later. Operator logs `applied / responded / interview / offer /
  rejected / ghosted` as outcome events; feeds a future calibration of the other dimensions. Never
  retconned by the LLM.

---

## 2. Deterministic weights, thresholds, exclusions, confidence

All numeric, all versioned in a single `scoring_profile` object; nothing hard-coded in prose.

```
scoring_profile v1.0.0:
  application_priority weights:
    brett_fit:                 0.40
    hiring_activity_evidence:  0.25
    freshness:                 0.20
    repost_churn_pattern:     -0.10   # churn DECREASES priority, does not brand the job fake
    source_data_confidence:    0.05   # low confidence gently deprioritizes
  bands:
    HIGH   >= 0.70
    MEDIUM 0.40–0.69
    LOW    < 0.40
    UNKNOWN: emitted when required evidence missing (overrides numeric band)
  exclusions (hard, pre-score):
    - job state == DISAPPEARED           -> excluded from active priority list (kept in history)
    - source_data_confidence == UNKNOWN  -> job shown but flagged "insufficient record"
    - brett_fit below floor (default 0.2)-> excluded from surfaced list (still stored)
  confidence:
    each dimension confidence ∈ [0,1] from evidence sufficiency
    (e.g. freshness confidence low if only 1 successful observation exists)
    composite confidence = min(dimension confidences feeding it)  # weakest-link, not average
```

Weakest-link composite confidence is deliberate: a priority score built on a low-confidence record
inherits that low confidence rather than averaging it away.

**Determinism guarantee:** given the same stored events + same `scoring_profile` version, the
scores are byte-reproducible. No wall-clock nondeterminism except `today` for freshness, which is
passed in explicitly (and pinned in fixtures) so tests are reproducible.

---

## 3. Evidence-linkage rule (the anti-hallucination spine)

> **No score field and no generated sentence may exist without a pointer to the stored evidence that
> produced it.**

Every dimension score carries `evidence_refs: list[EvidenceRef]`:

```
EvidenceRef:
  kind: enum(SNAPSHOT | CHANGE_EVENT | CANONICAL_FIELD | OUTCOME_EVENT)
  ref_id: str          # snapshot_id / event_id / job_id#field / outcome_id
  as_of: datetime
```

The daily report renders, per surfaced job, the scorecard + the evidence_refs behind each band. A
reviewer can click from "freshness: LOW" to the exact `first_seen_at` snapshot that justifies it.

---

## 4. The LLM boundary (explicit allow/deny)

**LLM MAY:**
- Write a plain-English summary of a job's scorecard *given* the already-computed scores + evidence_refs.
- Paraphrase the change history ("first seen June 3; salary band edited June 20") strictly from
  supplied ChangeEvents.
- Explain *why the deterministic rule* assigned a band, citing the rule + the evidence.

**LLM MAY NOT:**
- Invent or adjust ANY date (`first_seen_at`, change dates, disappearance) — dates come only from
  stored snapshots/events.
- Decide whether a job disappeared, is a repost, is active, or is real/fake — those are deterministic
  state-machine / rule outputs.
- Produce or alter any numeric score, band, or confidence.
- Be cited as evidence. LLM text is presentation; it is never an `EvidenceRef.kind`.

**Enforcement:** the LLM is called with a structured payload (scores + evidence + change events) and
its output is validated to contain no dates/numbers not present in the input (deterministic post-check:
extract dates/numbers from LLM output, assert each appears in the supplied evidence set, else reject
and fall back to a templated non-LLM summary). This mirrors the operator's standing rule that the LLM
is never the silent factual authority.

Reuses the CFR portable **Bedrock client wrapper** (`run_small`/`run_large`, dry-run stubs,
throttle/retry) for the summary call — cheap model (`claude-3-haiku`) is sufficient for narration.

---

## 5. The never-say-fake rule (output vocabulary)

Banned output vocabulary anywhere in reports/UI: *fake, fraudulent, ghost job, real, fabricated,
lying, scam*. Approved framing is behavioral + confidence-bounded:

| DON'T say | DO say |
|---|---|
| "This job is fake" | "Reposted 4× in 90 days; live 210 days without edits (confidence 0.8)." |
| "Real, active job" | "Edited 3× in the last 30 days; first seen 12 days ago." |
| "Ghost posting" | "Live 300+ days, no observed changes; low hiring-activity evidence." |

The composite is titled "application priority," never "reality verdict." Every surfaced claim is a
*record observation with confidence*, never a judgment about the employer's honesty.

---

## 6. Versioning + fixture-test approach

- **Versioning:** `scoring_profile` (weights/thresholds/exclusions), `fit_ruleset`, and each
  dimension scorer carry independent semver, stamped onto every emitted scorecard. A weight change =
  new `scoring_profile` version; old scorecards keep their version so historical scores are
  explainable ("scored under profile 1.0.0"). Re-scoring replays from stored events (no re-fetch).
- **Fixture tests (deterministic, no live network, no live LLM):**
  - Golden fixtures = frozen sets of ChangeEvents + canonical fields + pinned `today` → asserted
    scorecards (exact scores, bands, confidence, evidence_refs).
  - One fixture per dimension edge: stale-req LOW freshness; high-churn negative priority; content-
    hash-id → low source confidence; single-observation → low confidence UNKNOWN band; disappeared →
    excluded from priority list.
  - LLM-boundary fixture: feed a scorecard, run the narration with a stubbed/dry-run LLM, assert the
    post-check rejects any injected date/number not in evidence and falls back to template.
  - Regression lock: changing `scoring_profile` MUST update golden fixtures in the same change
    (surfaces silent weight drift).

---

## 7. Assumptions · failure modes · decisions · acceptance tests

### Assumptions
- A1: Scoring consumes ONLY the Data-model seat's stored `events/` + canonical fields + `field_hashes`
  + repost confidence — no independent fetching.
- A2: `today` is injected, never read from wall-clock inside scorers (reproducibility).
- A3: Bedrock cheap model available in us-east-1 (operator baseline) for narration; dry-run stub
  otherwise.

### Failure modes
- F1: LLM sneaks an unsupported date/number → caught by §4 post-check → template fallback.
- F2: A dimension has no evidence → must emit `UNKNOWN`, never a default middle score (else false
  confidence). Enforced by fixture.
- F3: Weight change silently shifts rankings → caught by golden-fixture regression lock (§6).
- F4: Churn penalty misread as fraud accusation → §5 vocabulary ban + report template guard.

### KEY DECISIONS (decision · default · owner · trigger)
- **D1 dimension weights** · default profile v1.0.0 (§2) · owner Scoring seat + operator ·
  trigger: recalibrate once `observed_application_outcome` data exists.
- **D2 brett_fit floor** · default 0.2 exclusion · owner operator · trigger: too many/few surfaced jobs.
- **D3 composite confidence = weakest-link (min)** · default min · owner Scoring seat ·
  trigger: revisit if min is too punishing in practice.
- **D4 LLM narration model** · default `claude-3-haiku` cheap + dry-run stub · owner operator ·
  trigger: if narration quality insufficient, escalate to strong model (cost-gated).
- **D5 outcome dimension** · default deferred to mature phase · owner operator ·
  trigger: after V1 daily report is trusted and applications are being logged.

### ACCEPTANCE TESTS
- **T1 decomposability:** every surfaced job exposes all 6 (7 later) dimension scores + evidence_refs;
  no composite is shown without its parts.
- **T2 determinism:** same events + same profile version + pinned `today` → byte-identical scorecards
  across two runs.
- **T3 evidence linkage:** assert every non-UNKNOWN dimension score has ≥1 EvidenceRef; a scorecard
  with a bare score and no ref fails the test.
- **T4 LLM boundary:** narration output containing a date/number absent from supplied evidence is
  rejected and replaced by the deterministic template.
- **T5 never-fake:** report renderer rejects any banned vocabulary token (fake/real/ghost/scam/...).
- **T6 UNKNOWN honesty:** a job with a single successful observation yields freshness/hiring
  confidence LOW and band UNKNOWN where required, not a middle default.
- **T7 exclusion:** a DISAPPEARED job is absent from the active priority list but present in history.
- **T8 versioned replay:** re-score stored events under profile v-next writes new scorecards tagged
  v-next without mutating v1.0.0 scorecards.

### OPEN QUESTIONS for other seats
- Data-model seat: confirmed the `field_hashes` + `probable-repost` confidence contract is the exact
  scoring input (it is, per that spec §1.3/§5.5).
- Report/notification seat: the daily report must render scorecard + evidence_refs and enforce the
  never-fake vocabulary guard — is that in the report seat's scope or shared?
- Operator: initial `fit_ruleset` seed — reuse CFR heuristic weights, or fresh for job-level (vs
  company-level) fit?
