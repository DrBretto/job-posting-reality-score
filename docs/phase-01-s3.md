# Phase 1 — S3 immutable snapshot store

One bucket, five prefixes (tiers). No folders in S3 — prefixes are just key naming. **No versioning.**
Immutability comes from **unique, write-once keys**: every snapshot gets a brand-new key, so nothing is
ever overwritten in the tiers that must be immutable.

## Bucket
`jprs-prod-<your-unique-suffix>` (S3 names are globally unique + lowercase). One bucket for everything.

## Key scheme (the five tiers)

| Tier (prefix) | Example key | Immutable? | What it is |
|---|---|---|---|
| `raw/` | `raw/provider=greenhouse/board=<token>/dt=2026-07-31/snapshot=<ulid>.json.gz` | **YES** (court of record) | Exact bytes fetched from the ATS, gzipped. Plus a `receipt=<ulid>.json` per fetch. Never mutated, never deleted early. Everything else can be rebuilt from this. |
| `current/` | `current/provider=greenhouse/board=<token>/current_jobs.json` + `_source_status.json` | no (overwritten) | The latest known live set + last-snapshot status. Small. This is the only tier we intentionally overwrite. |
| `normalized/` | `normalized/schema_v=1/provider=.../board=.../dt=.../jobs.json` | YES (per day) | Canonical job records parsed from raw. Replayable from raw, so it can expire sooner. |
| `events/` | `events/schema_v=1/provider=.../board=.../dt=.../events.json` | YES (append-only) | The change log (first-seen / changed / disappeared / …). **The product's permanent memory** — never expires. |
| `reports/` | `reports/dt=2026-07-31/daily_report.json` + `.md` | YES (per day) | The daily "what changed" digest. |

`provider=/board=/dt=` are **partition-style keys** so that later (P10) Athena can query them with zero
paid Glue crawler.

## Lifecycle (`aws/lifecycle/jprs-lifecycle.json`)
- `raw/` → cools to Standard-IA at 90 days, expires at 400 days (~13 months of raw at learning scale).
- `normalized/` → expires 90 days (rebuildable from raw).
- `reports/` → expires 180 days (tiny).
- `events/` and `current/` → **no expiry** (memory + latest state).
- Abort incomplete multipart uploads after 7 days (all prefixes).

**INSPECT-FIRST — be able to point at:** (a) which rule would delete data and when; (b) the fact that
there is **no versioning rule** anywhere — if you saw one, that would break the "immutability by unique
key, not versions" design and it should be rejected.

## Bucket hardening (this phase)
- Block Public Access: **all 4 flags ON** (account already clean per Access Analyzer).
- Default encryption: **SSE-S3 (SSE-S3 / AES256)** + Bucket Key ON (free, cuts KMS-style overhead).
- Object Ownership: **ACLs disabled (Bucket owner enforced)**.
- Versioning: **OFF** (stays off — operator hard rule; use lifecycle for retention, never versions).
- Bucket policy: `aws/policies/jprs-bucket-policy.json` (deny non-TLS + deny un-encrypted PutObject).

## The intentional failure (the P1 refresher)
Upload a tiny file to some key, then upload a *different* file to the **exact same key**. Open it — the
second silently replaced the first, and there is **no version history to recover the first**. That is
exactly why every snapshot must get a unique key (the `<ulid>` / `dt=` in the raw key). If two collector
runs ever wrote the same key, one snapshot would vanish with no trace.
