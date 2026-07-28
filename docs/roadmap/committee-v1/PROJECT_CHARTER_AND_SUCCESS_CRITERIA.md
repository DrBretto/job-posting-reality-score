# Project Charter & Success Criteria — Job Posting Reality Score

> The charter for the operator. What this product is for, what it may and may not claim, and how we
> know it is working. Companion to `JOB_POSTING_REALITY_SCORE_MASTER_ROADMAP.md`.

## 1. The user and the daily decision served

**User:** Brett — an experienced engineer running a focused job search against a curated list of target
companies, working a "apply within ~72 hours of a posting going live" cadence.

**The daily decision it improves:** *"Where do I spend today's finite application effort?"* Each
morning Brett should be able to open one report and know, without refreshing job boards, which new
high-fit roles appeared at his target companies, which postings changed, and which disappeared — each
tied to stored evidence — so he applies to fresh, well-fit roles first.

**The dual telos (both matter equally):** the build also rebuilds Brett's hands-on AWS recall through
manual console work with deliberate failure injection (it directly targets the SQS/DLQ path he blanked
on in an interview). A phase is not "done" until it delivers value AND he can explain the concept
without notes. Neither telos is subordinate.

## 2. V1 / V1.5 / Mature boundaries

| Increment | What it is | Built by | Actual-need gate |
|---|---|---|---|
| **V1 — Job Radar** | Daily report of new (with first-seen) / disappeared / materially-changed postings across selected companies, each traceable to stored snapshots; a trustworthy "nothing changed" that is distinct from "collectors didn't run." | P0–P7 | Already met — Brett needs day-of-posting awareness at target companies. |
| **V1.5 — Bedrock digest** | The same deterministic report, narrated as a 30-second plain-English summary. | P8 | Build ONLY if the V1 report is trusted AND the raw report is high-friction enough that Brett skips it. If he reads V1 happily, skip. |
| **V1.75 — IaC reconstruction** | The whole stack expressed as SAM/CDK; deploy/tear-down in one command; the recall proof. | P9 | Build ONLY after V1 has run reliably by hand long enough that each resource has been broken and explained. |
| **Mature — Historical intelligence** | Accumulated first-seen dates, repost patterns, change frequency, hiring momentum, role-fit, and (later) application outcomes → an expected-return read on where effort likely pays off. | P10 | Build ONLY when enough history has accumulated (weeks–months) AND there is a real analytical question V1 can't answer. |

Adding companies/providers is **config, not architecture**. Count is an output, not a target — if V1
+ V1.5 deliver durable value and Brett never needs the mature tier, that is success, not an unfinished
project.

## 3. Explicit non-goals

- **Not** a lie detector. It never claims a job is fake, real, fraudulent, a "ghost job," or a scam.
- **Not** a scraper. Sourcing is **sanctioned public ATS GET APIs only** (Greenhouse, Lever, Ashby).
  No authenticated scraping, no LinkedIn scraping, no contact/PII harvesting, no auto-apply, no message
  or notification sending to any third party.
- **Not** an always-on platform. No NAT/EC2/RDS/OpenSearch/Fargate/paid-Glue; no provisioned infra
  without explicit operator approval.
- **Not** a beginner AWS tutorial or a from-scratch course — a production-memory refresher for an
  experienced engineer.
- **Not** an LLM-authored fact store. The LLM narrates; it never sets a date, decides disappearance,
  or computes a score.
- **Not** a multi-user product. One recipient (Brett), one daily digest.

## 4. Measurable usefulness criteria

The product is useful when, in Brett's real search:

1. **Timeliness:** a genuinely new high-fit posting at a tracked company appears in the next morning's
   report (within one daily cycle of going live).
2. **Traceability:** every "new / disappeared / changed" claim links to the specific stored snapshot(s)
   that justify it — a reviewer can click from "freshness: LOW" to the exact first-seen snapshot.
3. **Trustworthy quiet:** a "nothing changed today" is believed *because* the report separately
   confirms the collectors ran (VERIFIED-QUIET), and Brett has never been shown a false "everything
   vanished" from a source outage.
4. **Decision lift:** the report changes what Brett does that day at least some mornings — he applies
   to a surfaced fresh role, or deprioritizes a high-churn one, on the strength of the evidence.
5. **Cost stays honest:** modeled and observed spend stays < $5/mo; teardown returns to ~$0.

## 5. Data-freshness & source-health signals (surfaced on every report)

- **Run-health header:** `VERIFIED-QUIET` (every expected source produced a SUCCESS snapshot, no
  material change) / `INCOMPLETE` (≥1 expected source lacks a SUCCESS snapshot — **named**) / `NO-RUN`
  (no manifest — surfaced by alarm A2, not the report).
- **Per-company status:** `CHANGED` / `NO-CHANGE` / `NOT-COLLECTED` — `NOT-COLLECTED` is never shown as
  "removed."
- **Completeness ratio:** expected-sources vs succeeded-sources, always in the header.
- **Source-health:** a `SUSPECT` flag when a source's count drops to zero or >60% vs the prior SUCCESS
  (removals suppressed, A6 fires); per-source successful-snapshot status for the day.
- **Record confidence:** `source_data_confidence` downgrades a record built on weak identity
  (`id_kind = CONTENT_HASH`) or a gappy snapshot history, so a shaky record can't masquerade as a
  confident signal.

## 6. What "reality" may and may NOT claim

**"Reality Score" names how much a posting's *behavior in the record* looks like an actively-hiring
role — it is NOT a verdict on the employer's honesty.**

| MAY claim (behavior + confidence) | MAY NOT claim |
|---|---|
| "Reposted 4× in 90 days; live 210 days without edits (confidence 0.8)." | "This job is fake." |
| "Edited 3× in the last 30 days; first seen 12 days ago." | "This is a real, active job." |
| "Live 300+ days, no observed changes; low hiring-activity evidence." | "Ghost posting." |
| "Likely the same role reposted (confidence 0.7)." | "This is a fake churned/evergreen posting." |
| "Source X did not run today; states frozen." | "All of company X's jobs disappeared." |

Every surfaced claim is a **record observation with confidence**, backed by `evidence_refs`. Banned
vocabulary (`fake, real, ghost, fraudulent, scam, lying`) is rejected by the report renderer. The
composite dimension is titled **"application priority,"** never "reality verdict." Dates are ours
(`first_seen_at` = our earliest SUCCESS observation), never provider-claimed, never LLM-invented.

## 7. The minimum report that improves the next application decision

Even at its smallest, a useful daily report contains:

1. A **run-health header** (VERIFIED-QUIET / INCOMPLETE(named) / changes-listed) + completeness ratio.
2. **New postings** since the last run, each with its **first-seen date** and the snapshot reference.
3. **Disappeared** postings (only those past grace, only from SUCCESS snapshots), never conflated with
   source failure.
4. **Materially-changed** postings, naming the changed field (title/location/salary/work-mode/body).
5. Per surfaced job, the **application_priority** band + the inspectable dimension scorecard with
   `evidence_refs` (so Brett can see *why* it ranks where it does), with `UNKNOWN` shown honestly where
   evidence is insufficient.
6. An explicit list of **NOT-COLLECTED** companies (with the failing source named), so a quiet day is
   never a blind day.

That is enough to answer "which fresh, well-fit role do I apply to first today, and which high-churn
one do I skip?" — which is the whole point.
