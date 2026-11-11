# DESIGN — open-market job discovery

Packet: `JPRS-L2-P01-open-market-discovery-v01`
Run: `20260924_open_market_discovery_v1`
Controlling product intent: `docs/plans/2026-09-24-open-market-job-discovery.md`

This is the single chosen approach, not a menu of rival plans. Provenance labels follow
`RUN_OUTPUT_CONTRACT.md`: `evidence` = observed this run, `inference` = reasoned from evidence,
`operator_preference` = from the central candidate policy.

---

## 1. Intent restatement

Unknown employers. All sectors. Every credible fit retained. One central candidate policy,
projected — never re-authored. No deployment in this packet.

The failure this overhaul exists to fix: JPRS polls 15 hand-picked Greenhouse boards. A useful
opening at a business nobody has named yet **cannot arrive**, because arrival requires an
operator to type that employer's board token into `config/companies.yaml` first. Adding boards
faster does not change the shape of that failure.

So the system needs a capability it does not have: **employer-independent discovery** — a query
about *work*, answered by sources that were never told which companies to look at.

---

## 2. The central architectural split

Today `source_id = provider:board_token` and the employer is a property of the *source*. The
report even carries a hardcoded 15-entry company-label map (`src/report/handler.py`
`_COMPANY_LABELS`). That identity — one source, one employer — is exactly what forecloses
open-market discovery.

The overhaul separates two capabilities that the current code conflates:

| | **Monitoring** (exists) | **Discovery** (new) |
|---|---|---|
| Question asked | "what is open at *this employer*?" | "who is hiring for *this work*?" |
| Keyed by | employer's ATS board token | a query over work performed |
| Employers per source | exactly one, known in advance | many, unknown in advance |
| Can surface an unnamed employer | no, structurally | yes — this is the point |
| Source kind | `ATS_BOARD` | `DISCOVERY_FEED`, `MANUAL_IMPORT` |

Consequence: **employer becomes a property of the job, not of the source.** `CanonicalJob` gains
an authoritative `employer_name`, and the hardcoded label map is deleted. Every downstream
surface (dedup, screening, report) keys on the job's own employer.

Discovery then *feeds* monitoring: an employer discovered today whose careers page resolves to a
supported ATS becomes a candidate monitored source tomorrow, so tomorrow's postings from that
employer are cheaper and faster to see. That is the growth loop the plan asks for, and it runs
under an explicit admission policy (§6) rather than by hand-editing YAML every morning.

---

## 3. Source/access/cost matrix

All access facts below are `evidence` — bounded read-only probes performed 2026-09-24 from this
repository; shapes, record counts and payload hashes are recorded in
`evidence/source_probe_provenance.json`. Raw payloads are deliberately not committed (several
providers restrict redistribution; see the Terms column).

| Source | Kind | Auth | Probe result | Breadth | Terms / limits | Cost | Decision |
|---|---|---|---|---|---|---|---|
| **Remotive** `remotive.com/api/remote-jobs` | discovery feed | **none** | 200, 19 records, all fields present | remote, tech-leaning, some non-software (e.g. a telecom BPO content role observed) | Attribution + link-back to the Remotive URL **required**; must not republish to third-party job sites; 24-hour delay; provider advises **max 4 requests/day** | $0 | **integrate** |
| **Remote OK** `remoteok.com/api` | discovery feed | **none** | 200, 100 records | remote, tech-leaning; record 0 is a legal notice, not a job | Attribution + follow link-back required; logo is a trademark, do not use | $0 | **integrate** |
| **Jobicy** `jobicy.com/api/v2/remote-jobs` | discovery feed | **none** | 200, 5 records at `count=5`; has `jobIndustry`, `jobLevel`, `jobGeo` | remote; carries an explicit industry field, useful for sector coverage measurement | Credit + direct link to source; apply buttons must go to the original job URL | $0 | **integrate** |
| **Himalayas** `himalayas.app/jobs/api` | discovery feed | **none** | 200, 5 records; richest structure — `minSalary`/`maxSalary`/`salaryPeriod`, `seniority`, `locationRestrictions`, cursor pagination | remote; published salary far more often than the others | attribution; cursor paging | $0 | **integrate** |
| **Adzuna** `api.adzuna.com/v1/api/jobs/us/search/{page}` | discovery feed | `app_id` + `app_key` | **400 without credentials** (expected); docs confirm both params are obligatory | **the breadth engine** — general US index across all industries, supports `where` (NH/MA/remote) and `what` work-phrase queries | free developer tier; recheck retention rights before storing raw | $0 on free tier | **implement, gate on credential** |
| **Arbeitnow** | discovery feed | none | 200, 250 records | location census of first 800: London 40, Berlin 30, Paris 25, Munich 11 — **overwhelmingly non-US** | — | $0 | **declined** — fails NH location eligibility; would burn budget producing rows the screener must reject |
| **Brave Search API** | web search | API key | not probed | broad web | $5/1,000 searches, $5 monthly credit, **card required at signup** | requires payment instrument | **declined** — paid signup is not authorized by this packet; recorded as researched, not purchased |
| **Greenhouse / Lever** boards | ATS monitoring | none | Greenhouse 200, 146 records on a live registry board | one employer each | public board API | $0 | **keep** — revalidated, still the follow-up collection path |
| **Ashby** `api.ashbyhq.com/posting-api/job-board/{board}` | ATS monitoring | none | **200 on 4 independent boards, 1,083 postings total** | one employer each | public posting API | $0 | **enable** — identity concern resolved, §4 |

**Chosen combination — deliberately small.** Four keyless discovery feeds that work *today*,
plus Adzuna as the breadth engine behind a credential gate, plus a manual import path, plus the
three ATS families for follow-up monitoring. Arbeitnow and Brave are researched and declined
with reasons. No abstraction framework larger than the implementation: one `DiscoveryConnector`
base with one small subclass per feed, reusing the existing `Connector` status-labeling contract.

**Honest coverage limitation** (`inference`): all four keyless feeds are remote-job boards. They
demonstrate real employer-independent discovery and they do surface employers absent from the
registry, but they are *not* a general index of ordinary local businesses. The plan's worked
scenario — a non-software business hiring an internal-AI engineer — is most likely to arrive
through Adzuna's general index, which is credential-gated. This packet therefore ships a working
discovery path and reports that specific breadth gate as **unpassed**, rather than quietly
redefining four remote boards as market coverage. That distinction is written into the report
surface itself, not just this document.

---

## 4. Ashby identity concern — resolved with evidence

`src/common/connectors.py` has carried `ASHBY_ENABLED = False` with the comment "UUID permanence
unverified (D2/U4)", and the connector derives identity by regex-scraping a UUID out of `jobUrl`,
falling back to a content hash flagged `identity_low_confidence`. The plan is explicit that
leaving the adapter disabled is not completion.

`evidence`, 2026-09-24, four independent live boards:

| Board | Postings | Every record has top-level `id` | `id` is a UUID | `jobUrl` ends with that same `id` |
|---|---|---|---|---|
| Ramp | 155 | yes | yes | yes |
| OpenAI | 828 | yes | yes | yes |
| Ashby | 70 | yes | yes | yes |
| Linear | 30 | yes | yes | yes |

1,083 postings, zero records lacking a native `id`. Persistence evidence: a Linear posting
carries `publishedAt` of 2021-04-27 and is still `isListed` under the same UUID, so the
identifier survives years of posting lifetime rather than being per-response.

Resolution: use `raw["id"]` as `provider_native_id` with `IdKind.NATIVE_ID`. The URL-slug scrape
demotes to a fallback, the content hash to a last resort, and `ASHBY_ENABLED` becomes `True`.
The fallback ladder stays tested, so a future provider change degrades honestly instead of
silently producing unstable ids.

Bonus fields the current mapper discards and the new one keeps: `compensation.compensationTierSummary`
(genuinely published salary — never inferred), `secondaryLocations` (location-eligibility variants,
which the dedup rule must not collapse), `employmentType`, `isRemote`, `workplaceType`, and
`address.postalAddress`.

---

## 5. Data flow

```
                    ┌─────────────────────────────────────────┐
  discovery  ──────▶│ DISCOVERY sources (employer-independent)│
  (new)             │  remotive · remoteok · jobicy ·         │
                    │  himalayas · adzuna* · manual import    │
                    └───────────────┬─────────────────────────┘
                                    │  many employers per source
                                    ▼
                    ┌─────────────────────────────────────────┐
  admission  ──────▶│ candidate-source queue → admission policy│──▶ monitored registry
  (new)             │  (public scope, host, cadence, terms)    │     (grows safely)
                    └───────────────┬─────────────────────────┘
                                    │
  monitoring ──────▶┌───────────────▼─────────────────────────┐
  (exists)          │ ATS boards: greenhouse · lever · ashby  │
                    └───────────────┬─────────────────────────┘
                                    ▼
        normalize → cross-source dedup (provenance preserved, nothing deleted)
                                    ▼
        differ: change events, freeze/recovery, history        (repaired)
                                    ▼
        candidate screening: central-policy projection         (new)
                                    ▼
        scoring: recall-first fit, no title-only hard zero      (repaired)
                                    ▼
        report: complete readable list + coverage/backlog       (repaired)
```

Discovery and monitoring write through the **same** snapshot/status/normalized contract, so one
immutable run manifest covers both and the existing `raw/ → normalized/ → status/ → current/ →
events/ → reports/` tiering, IAM prefix split, and freeze invariant all keep working. A discovery
feed is a source whose `source_id` is `provider:query_family` instead of `provider:board_token`;
nothing downstream needs a second pipeline.

### Fetch safety for arbitrary URLs

Discovery introduces URLs the operator never vetted, so the existing static `HOST_ALLOWLIST` is
no longer sufficient by itself. Unsupported-careers-page fetches go through a guard that rejects:
private / loopback / link-local / CGNAT / multicast / reserved address space (resolved, not just
parsed, so a hostname resolving inward is caught), non-HTTP(S) schemes, embedded credentials in
the URL, ports outside 80/443, cross-host and scheme-downgrading redirects, redirect chains past
a small bound, responses over a byte ceiling (streamed, so the ceiling actually binds), and
non-HTML/JSON content types. Job descriptions and search results are **untrusted data**: they are
never executed, never interpreted as instructions, and prompt-injection-shaped text inside a
description is stored and scored as text like any other.

---

## 6. Public-source admission policy

Observation and permission to collect are separate. Discovering an employer does **not** admit it.

A candidate source is recorded on observation with its evidence (which query found it, which job,
when). It becomes eligible for admission only when all of these hold:

1. **Public scope** — an official public job-board/posting API or a page publishing
   schema.org `JobPosting` data. Not an authenticated employer API, not a login-walled page.
2. **Host** — resolvable public host, passes the fetch guard in §5, robots-respecting path.
3. **Provenance** — the employer↔board mapping is derived from the employer's own careers URL,
   not guessed from a company name.
4. **Terms** — the provider's published terms permit programmatic read at our cadence, and
   permit whatever we retain (§8).
5. **Cadence and resource limits** — fits the per-source request budget and the total daily
   budget without displacing existing sources.
6. **Not operator-disabled** — an explicit disable is sticky and survives rediscovery. This is
   the rule that keeps the growth loop from re-admitting something the operator rejected.

Admission is proposed, recorded with its evidence, and applied to the registry surface; it never
mutates the active production registry mid-run (the plan's §5 requirement). Sources that fail
admission are not discarded — they stay in a verification queue with the reason, so a lead whose
ATS lacks a connector is still visible to the operator as a lead.

---

## 7. Candidate-policy projection

`APPLICATION_WORKFLOW.md` is authoritative and is **not edited** by this run. The system keeps
**one versioned projection** of it — source paths plus a content hash per source file plus the
reviewed policy mappings — and detects divergence rather than guessing. When a source file's hash
no longer matches the projection, the run says so in the report; it does not silently screen
against a stale policy, and it does not re-derive the policy from prose on the fly.

What the projection carries (all `operator_preference`, mapped from the five central sources):

- **Calibration** — practical senior engineering, roughly five to seven years competitive,
  applied AI an advantage. ~$150K is an *orientation*, not a gate. Judge scope in company
  context. Staff/architect titles are not blanket rejections. Adjacent learnable skills are not
  unmet specialization requirements.
- **Exclusions**, applied to the *actual role and process*, never to incidental text: real sales
  ownership (quota / commission / prospecting / closing), clearance and federal-suitability
  paths, frontend specialization, AI-conducted interviews, required recorded candidate video.
- **The misfire rules that matter more than the exclusions themselves** — benefits boilerplate
  mentioning commission is not a quota; a live human video call is not a recorded-video
  application; building sales tooling is not doing sales. And **unknown is a third state**: not
  confirmed eligible, not automatically excluded. An inaccessible or dynamic application form
  yields an explicit *pending process check*, never a claim that no video or AI interview is
  required.
- **Location** — must work from New Hampshire. No invented relocation, travel, or commuting.

**Privacy boundary.** Only job-related criteria reach any cloud search or ranking path. The
master resume, contact details, personal circumstances, and the reasons behind preferences are
never uploaded to a provider, never written into fixtures, logs, reports, or commits. The
projection stores *screening criteria*, not a candidate dossier.

**Production must not assume the sibling repository exists.** Lambda has no `../Infotropy Book`.
The projection is therefore a build-time artifact committed to this repository in
privacy-minimized form, refreshed by an explicit local command that reads the sibling sources and
rewrites the projection with new hashes. Refresh is an operator action with a visible diff, not a
silent import.

**History is read, never written.** `submitted`, `rejected`, `skipped`, `prepared`, and `new` are
five distinct states. A resume file or a prepared folder is `prepared` and nothing stronger —
JPRS cannot invent a submission. Useful previously prepared items surface in their own report
section instead of being re-announced as new every morning.

---

## 8. Scheduling, budgets and retention

Discovery runs on the existing daily rhythm; no new schedule is introduced and the current
collect/assemble schedules are preserved. Per-source request budgets respect each provider's
stated guidance — Remotive's own notice advises at most four requests per day, so its budget is
one request per run.

Query work that does not fit the budget is **deferred, not dropped**: the backlog is persisted
and resumable, under-covered query families rotate to the front on the next run, and the report
shows saturation, pagination limits, skipped query families, and remaining backlog explicitly. A
display cap never erases a candidate.

Retention follows the strictest applicable provider condition. Where redistribution is not
permitted, the system keeps the minimum needed to deduplicate and to link back — identifiers,
canonical URL, timestamps, hashes — and does not commit raw provider payloads to the repository.

---

## 9. Repairs carried by this design

Four defects the plan names, with the actual mechanism in each case:

1. **Title spelling defect.** `_TITLE_SIGNALS` matches `full[- ]stack`, which requires a
   separator, so the live `FullStack` title scores 0.00 while `Full Stack` scores 0.38. Title
   matching gains a normalization step (camel-case boundary split, separator folding) so
   `FullStack`, `Full-Stack`, `full stack` and `Fullstack` are one token. Live corroboration: a
   Linear posting observed this run is titled "Senior / Staff **Fullstack** Engineer".

2. **Title-only hard zero.** `blocked_title_lane = not title_signals` forces `total = 0.0`
   whenever no title pattern matches — a novel or ordinary title is erased regardless of what
   the work actually is. The plan requires work-based recall. The hard zero is removed and
   replaced by a work-evidence path: an ordinary technical title with strong description-level
   work signals stays eligible at reduced confidence. Genuine exclusions keep zeroing, because
   those are verified about the role, not guesses about a title.

3. **Frozen-department baseline latch.** The silent-subset guard fires when a prior-present
   department segment vanishes, suppresses removals, and withholds the count baseline update —
   so a department that genuinely closed can never recover, and the warning repeats forever
   with a reason that says "low count" when the actual condition is "segment absent". Fix:
   the segment guard becomes *corroboration-bounded*. It suppresses removals while the evidence
   is ambiguous, tracks the streak, and once the same segment is still absent across N
   independent healthy SUCCESS snapshots, it reclassifies to confirmed closure and lets the
   ordinary grace clock run. The mass-drop and cumulative-bleed guards keep suppressing
   indefinitely — those protect against real truncation and are not relaxed. Warnings state the
   condition actually observed, and the four conditions stay distinguishable: confirmed closure,
   possible feed loss, stale baseline, fetch failure.

4. **Misleading health and hidden overflow.** `compute_run_health` computes `material` and then
   returns `VERIFIED_QUIET` on both branches of its own conditional — the variable is dead, and
   fifteen successful configured fetches read as an all-clear. Health splits into the plan's four
   axes: collection health (did monitored sources succeed), discovery coverage (what was actually
   searched, what is queued, what was inaccessible), freshness, and interpretation health. No
   axis is allowed to phrase itself as market coverage. The 20-row display cap stops hiding
   candidates in JSON: the digest keeps its concise top section and the same document carries the
   complete readable list, every retained credible role with a direct link and a reason.

---

## 10. Test strategy

- **Fixtures validate code; a live rehearsal validates access.** They are labeled separately and
  never merged into one claim.
- **Held-out discovery.** The acceptance case forbids a seeded employer name in the query or in
  fixture configuration. Tests assert the discovery query text contains no employer name and that
  the discovered employer is absent from `config/companies.yaml`, then follow that job through
  parsing, screening, scoring, dedup and into the complete report.
- **Regression-first on the four repairs**, each with a test that fails against current `HEAD`:
  the `FullStack` scoring case, the novel-title recall case, the segment-closure recovery case,
  and the overflow-visibility case.
- **Recall and precision from concrete sampled cases.** False positives: PLC-only industrial
  automation, frontend polish, AI research requiring a specialist record, pre-sales, clearance.
  Positive counterexamples use the same ambiguous vocabulary in ordinary engineering contexts, so
  the tests prove discrimination rather than keyword presence.
- **Coverage comparison on one evaluation set**, old footprint versus new: distinct employers,
  industries, source types, previously unseen employers, unverified leads, duplicates, viable
  results, and remaining limitations. A higher raw job count is explicitly not the success
  criterion and is reported separately from eligible recall.
- **Honesty guard.** If the live rehearsal produces no strong fit, that is reported as the
  result. No unsuitable live role is forced to pass to satisfy a positive test.
