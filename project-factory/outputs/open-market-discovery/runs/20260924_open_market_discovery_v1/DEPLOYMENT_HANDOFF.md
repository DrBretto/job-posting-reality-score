# DEPLOYMENT_HANDOFF — open-market job discovery

> Orchestrator review, September 24: this historical handoff is not cleared for use. Read
> `ORCHESTRATOR_REVIEW.md` for reproduced runtime, pagination, screening and rollback defects.
> P02 repairs and a new review precede any deployment authorization; instructions below record
> the executor's original proposal, not a currently accepted release procedure.

Packet: `JPRS-L2-P01-open-market-discovery-v01` · Run: `20260924_open_market_discovery_v1`

**Nothing in this run touched AWS.** No deploy, no SSM write, no IAM change, no spend, no email, no
commit, no branch, no push. Everything below is an instruction for a separately approved action.

---

## 1. Approval boundary

| Action | Authorized by this packet? |
|---|---|
| Local code, tests, docs, config | yes — done |
| Public read-only source verification | yes — done |
| Read-only inspection of known AWS resources | yes — not needed, no AWS state was read |
| `sam deploy` | **no — needs your explicit approval** |
| SSM parameter creation or edit | **no — needs your explicit approval** |
| Creating an Adzuna account / any signup | **no — needs you** |
| Enabling careers-URL resolution | **no — needs your explicit approval** |
| git commit / branch / push | **no — needs your explicit approval** |

Current branch `codex/real-job-radar` carries an **uncommitted working tree**. Nothing was staged.

---

## 2. What changes in AWS

### New resources

| Resource | Purpose |
|---|---|
| `jprs-discovery` Lambda | the open-market discovery pass; 120s timeout, 512MB |
| `/aws/lambda/jprs-discovery` log group | 30-day retention, matching the others |
| `jprs-discovery-daily` EventBridge schedule | `cron(5 7 * * ? *)` America/New_York |
| `jprs-scheduler-discovery-role` | invoke-only role for that schedule |
| `jprs-A8-discovery-errors` alarm | discovery failing silently would quietly reduce the system to a fixed watchlist while every other signal still looked healthy |

### Changed resources

| Resource | Change |
|---|---|
| `jprs-report` Lambda | code update; IAM gains `s3:GetObject` on `discovery/*` and `s3:ListBucket` on the `discovery/*` prefix |
| `jprs-collector`, `jprs-differ`, `jprs-enumerate` | code update only; **no IAM change** |

### Preserved — confirm on the change set

- `jprs-collect-daily` stays `cron(0 7 * * ? *)`.
- `jprs-assemble-daily` stays `cron(0 9 * * ? *)`.
- The S3 bucket, its versioning-off state, SQS queues, DLQ, and alarms A1–A7 are untouched.
- No change to the permissions boundary.

### IAM diff, in words

The only new grants are to the new discovery role:

```
+ jprs-discovery  s3:PutObject   arn:aws:s3:::<bucket>/discovery/*
+ jprs-discovery  s3:PutObject   arn:aws:s3:::<bucket>/{raw,normalized,status}/*
+ jprs-discovery  s3:GetObject   arn:aws:s3:::<bucket>/{discovery,runs,status}/*
+ jprs-discovery  ssm:GetParameter(s|sByPath)  arn:aws:ssm:<region>:<acct>:parameter/jprs/secrets*
+ jprs-discovery  cloudwatch:PutMetricData     (namespace JPRS only)
+ jprs-report     s3:GetObject   arn:aws:s3:::<bucket>/discovery/*
+ jprs-report     s3:ListBucket  prefix discovery/*
```

Discovery deliberately does **not** get `current/*` or `events/*`. Those stay differ-owned, so the
M4 prefix split still holds and the live-job set is outside discovery's blast radius.

---

## 3. Prerequisites, in order

### 3.1 Required before deploy — nothing

The four keyless discovery sources need no credentials. Deploying as-is gives working open-market
discovery on day one.

### 3.2 Optional, and the single highest-value follow-up — the Adzuna credential

This is the source that provides general, all-industry, New-Hampshire-filterable breadth, and it is
the most likely path to the plan's worked scenario (an ordinary local business hiring an engineer for
internal AI work). Without it, discovery covers four remote-job boards only.

1. Register at `developer.adzuna.com` for a **free** developer tier (no card, unlike Brave).
2. Store the credentials as SSM **SecureString** parameters — not CloudFormation parameters, because
   a secret passed through CloudFormation is retained in change sets and console history:
   ```
   /jprs/secrets/ADZUNA_APP_ID    (SecureString)
   /jprs/secrets/ADZUNA_APP_KEY   (SecureString)
   ```
3. No redeploy is needed. The discovery Lambda reads that path with decryption at invoke time; until
   the parameters exist, Adzuna stays gated and the report names it as the reason coverage is
   partial.

### 3.3 Optional — careers-URL resolution (source growth)

Discovery currently cannot admit any new monitored source, because the keyless feeds publish
aggregator apply links and none of their payloads contain an employer board URL (measured; see
`VALIDATION.md` §5). Enabling the bounded resolver closes that loop.

Set `ResolveCareersUrls=true` at deploy time. Every hop is re-validated against the SSRF address
rules; cross-host hops are permitted *only* here, because arriving at a different host is the entire
point of resolving an apply link. Its live path is **unverified from this machine** (the sandbox
blocks DNS), so treat the first production run as the verification.

---

## 4. Deploy

```bash
cd /Users/drbretto/Desktop/Projects/job-posting-reality-score

# 1. confirm local state
git status
.venv/bin/pytest -q -p no:cacheprovider          # expect 168 passed
sam validate --lint --template-file infra/template.yaml
sam build --template-file infra/template.yaml

# 2. deploy, reviewing the change set before confirming
sam deploy --config-file infra/samconfig.toml
```

Review the change set for exactly the resources in §2. **Reject it if it proposes any change to the
collect or assemble schedule, the bucket, or the permissions boundary.**

`sam build` note: if it fails with `Operation not permitted: .aws-sam/build/*/.claude/commands`,
that is a stale build directory from a previous run, not a template problem. Build into a clean
directory (`--build-dir`) or remove `.aws-sam/build` first.

---

## 5. Post-deploy acceptance checks

1. **Discovery runs.** Lambda → `jprs-discovery` → Test with `{}`. Expect
   `discovery_succeeded` listing all four keyless providers and `jobs_discovered > 0`.
   *This is the check that closes the unpassed `fetch_raw` gate from `VALIDATION.md` §3* — only
   Remotive was exercised through that code path locally, because this machine's egress proxy
   truncated the other three.
2. **Coverage receipt exists.** S3 → `discovery/run=<date>/coverage.json`. Confirm
   `discovery_succeeded`, `query_families_covered`, and `credential_gated` naming Adzuna if its
   credential is absent.
3. **Report renders the new surfaces.** Run the assembler, then open
   `reports/dt=<date>/daily_report.md`. Confirm: four health axes, a "Coverage and backlog"
   section, a "Complete candidate list" whose count matches `matching_job_count`, and the source
   attribution block (required by Remotive, Remote OK and Jobicy terms).
4. **The existing path is unharmed.** Confirm 15/15 boards still collected and that the digest
   arrived, with `digest_delivery.json` beside the report.
5. **Nothing was auto-admitted.** S3 → `discovery/run=<date>/proposed_registry.json`. It should be
   `[]` unless careers-URL resolution is enabled. Registry rows are *proposed*; applying them is
   always your action.
6. **Ashby.** Ashby is now enabled but no Ashby board is in the registry yet, so nothing changes
   until you add one.

---

## 6. Expected load and cost

| Item | Per day |
|---|---|
| Discovery requests | 5 (Remotive 1, Remote OK 1, Jobicy 1, Himalayas 2) |
| Discovery requests with Adzuna | up to 25 |
| Board requests | 15, unchanged |
| New Lambda invocations | 1/day, ~10–30s |
| New S3 objects | ~5 raw + 5 normalized + 5 status + 4 discovery = ~19/day |

**Cost: $0 additional in practice.** One short Lambda invocation and a few dozen small S3 objects per
day sit inside the same free-tier usage the stack already runs in. The `<$5/month` AWS target is
preserved. Adzuna's developer tier is free. Brave was researched and **declined** because signup
requires a payment instrument, which this packet does not authorize.

Provider rate posture: Remotive's own notice advises at most four requests per day; we make one.

---

## 7. Data and retention

- Retention follows the strictest applicable provider condition. Where redistribution is not
  permitted, only what is needed to deduplicate and link back is kept — identifiers, canonical URL,
  timestamps, hashes.
- Raw discovery payloads are written to `raw/` in the private bucket exactly as board payloads
  already are. They are never committed to the repository and never republished.
- Attribution is rendered in every report, satisfying Remotive, Remote OK and Jobicy terms.
- `config/candidate_policy.json` holds source hashes and screening criteria only — no resume, no
  contact details, no personal circumstances. `config/application_history.json` holds employer,
  role, requisition URL, status and an evidence pointer. A test asserts the absence of personal data.

---

## 8. Existing-data reconciliation

- `SCHEMA_VERSION` moves 1.0.0 → **1.1.0: additive only**. Same major version, so the `schema_v=1`
  S3 prefix is unchanged and **no replay is required**. Records written under 1.0.0 load with the
  new fields at their defaults.
- `DiffState` gains `segment_absence_streak`, `suspect_streak`, `suspect_kind`, `suspect_since`,
  `suppressed_count_history`, all defaulted. Existing `_diff_state.json` objects load unchanged.
- First run after deploy: sources currently latched by the silent-subset guard begin their
  corroboration count at zero and will take two further healthy snapshots to release. That is the
  intended conservative behavior, not a stall.
- `scoring_profile_version` moves 1.1.0 → **1.2.0**. Scores are not comparable across that boundary;
  the version is stamped on every scorecard so a later comparison can tell.

---

## 9. Rollback

The change is additive, which makes rollback cheap.

**Fast partial rollback — disable discovery, keep everything else:**
```bash
aws scheduler update-schedule --name jprs-discovery-daily --state DISABLED   # (needs approval)
```
The daily radar continues exactly as before; the report shows discovery coverage `NOT-RUN`.

**Full rollback — redeploy the previous revision:**
```bash
git checkout e549a73 -- src/ infra/ config/
sam build --template-file infra/template.yaml
sam deploy --config-file infra/samconfig.toml
```
CloudFormation removes `jprs-discovery`, its schedule, role, log group and alarm A8, and reverts the
report role's `discovery/*` grants.

**Data left behind is inert.** The `discovery/` prefix is not read by the pre-change report, and the
additive `CanonicalJob` / `DiffState` fields are ignored by the old code. Nothing needs deleting, and
no removal event can be produced by a rollback.

---

## 10. Open items requiring your decision

1. **Adzuna credential** (§3.2) — the single highest-value follow-up; unlocks general industry
   breadth and New Hampshire filtering.
2. **Careers-URL resolution** (§3.3) — required for the source-growth loop to admit anything.
3. **Lambda packaging** — `.samignore` is not honored by SAM's Python builder, so every function
   ships the whole repository (18 MB, including `tests/`, `docs/`, `project-factory/` and
   `.claude/`). Pre-existing, affects all five functions, and fixing it properly means changing the
   build method. Not touched here because it would alter packaging for the entire stack.
