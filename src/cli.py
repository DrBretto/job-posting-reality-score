"""Thin local CLI for dev/test only (NOT a Lambda entry point).

Subcommands:
  connect        — run a connector against a local fixture file (no network)
  diff           — run the differ over two local snapshot-day fixtures (replay-from-raw semantics)
  report         — render a report locally from an events+scorecards fixture
  registry       — render config/companies.yaml as the JSON payload stored in SSM
  discover       — run the discovery stage and render the full candidate report
  policy-refresh — rebuild the candidate-policy projection from the sibling sources
  policy-check   — report divergence between the committed projection and the live sources
  history-scan   — drift-check the reviewed application-history projection against the folders
  history-refresh— rebuild that projection from the submission logs and the reviewed entries
  import-urls    — import operator-supplied posting URLs through the fetch guard
  coverage-diff  — compare the old monitored footprint against the new discovery footprint

Every path is offline by default. `discover` and `import-urls` reach the network ONLY with an
explicit `--live` flag, and then only to the public read-only endpoints on the connector allowlist.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.common.connectors import FetchResult, get_connector
from src.common.models import CanonicalJob, SourceSnapshot
from src.differ.handler import DiffState, diff_source
from src.enumerate.handler import load_registry_from_yaml
from src.report.handler import ReportInput, render_report


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_result_from_bytes(raw: bytes, url: str = "local://fixture", http_status: int = 200) -> FetchResult:
    now = _now()
    return FetchResult(
        raw_bytes=raw, http_status=http_status, error_class=None,
        endpoint_url=url, request_at=now, response_at=now,
    )


def cmd_connect(args) -> int:
    connector = get_connector(args.provider)
    raw = Path(args.fixture).read_bytes()
    fr = _fetch_result_from_bytes(raw)
    snapshot, jobs = connector.build_snapshot(args.board_token, fr, prior_job_count=args.prior_count)
    print(f"status={snapshot.status.value} jobs={len(jobs)}")
    print(json.dumps({
        "snapshot": snapshot.model_dump(mode="json"),
        "jobs": [j.model_dump(mode="json") for j in jobs],
    }, indent=2, default=str))
    return 0


def cmd_diff(args) -> int:
    prev = json.loads(Path(args.prev).read_text())
    curr = json.loads(Path(args.curr).read_text())
    state = None
    if args.state and Path(args.state).exists():
        state = DiffState.model_validate(json.loads(Path(args.state).read_text()))

    def _load(day) -> tuple[SourceSnapshot, list[CanonicalJob]]:
        snap = SourceSnapshot.model_validate(day["snapshot"])
        jobs = [CanonicalJob.model_validate(j) for j in day.get("jobs", [])]
        return snap, jobs

    # replay prev then curr so the state accumulates as it would across two days
    today = datetime.fromisoformat(args.today) if args.today else _now()
    snap_p, jobs_p = _load(prev)
    r1 = diff_source(state, snap_p, jobs_p, run_id=prev.get("run_id", "day1"), today=today)
    snap_c, jobs_c = _load(curr)
    r2 = diff_source(r1.state, snap_c, jobs_c, run_id=curr.get("run_id", "day2"), today=today)
    print(json.dumps({
        "day1_events": [e.model_dump(mode="json") for e in r1.events],
        "day2_events": [e.model_dump(mode="json") for e in r2.events],
        "day2_frozen": r2.frozen,
        "day2_suspect": r2.suspect,
        "day2_suspect_reason": r2.suspect_reason,
    }, indent=2, default=str))
    if args.state:
        Path(args.state).write_text(json.dumps(r2.state.model_dump(mode="json"), default=str))
    return 0


def cmd_report(args) -> int:
    data = json.loads(Path(args.fixture).read_text())
    from src.common.models import ChangeEvent, DimensionScorecard

    inp = ReportInput(
        run_id=data["run_id"], dt=data["dt"],
        expected_sources=data.get("expected_sources", []),
        succeeded_sources=data.get("succeeded_sources", []),
        manifest_present=data.get("manifest_present", True),
        events=[ChangeEvent.model_validate(e) for e in data.get("events", [])],
        scorecards=[DimensionScorecard.model_validate(c) for c in data.get("scorecards", [])],
        jobs=[CanonicalJob.model_validate(job) for job in data.get("jobs", [])],
        source_labels=data.get("source_labels", {}),
    )
    markdown, _report_json = render_report(inp)
    print(markdown)
    return 0


def cmd_registry(args) -> int:
    entries = load_registry_from_yaml(args.config)
    payload = {"companies": [entry.model_dump(mode="json") for entry in entries]}
    print(json.dumps(
        payload,
        indent=None if args.compact else 2,
        separators=(",", ":") if args.compact else None,
    ))
    return 0


# --------------------------------------------------------------------------------------------------
# open-market discovery commands
# --------------------------------------------------------------------------------------------------
def _known_employers(config_path: str = "config/companies.yaml") -> set[str]:
    try:
        entries = load_registry_from_yaml(config_path)
    except (OSError, ValueError):
        return set()
    return {e.employer_name or e.company_slug for e in entries}


def _load_previous_local_report(path) -> tuple[datetime | None, frozenset[str], str | None]:
    """Read a previous local report so "new since the last round" means the same thing offline.

    Returns (its generation time, the job ids it showed, its run id). Missing or unreadable is a cold
    start, stated as such rather than guessed around.
    """
    if path is None:
        return None, frozenset(), None
    target = Path(path)
    if target.is_dir():
        target = target / "daily_report.json"
    if not target.is_file():
        return None, frozenset(), None
    try:
        prior = json.loads(target.read_text())
    except (OSError, ValueError):
        return None, frozenset(), None
    stamp = prior.get("report_generated_at") or (prior.get("timing") or {}).get("run_started_at")
    when = None
    if stamp:
        try:
            when = datetime.fromisoformat(stamp)
        except ValueError:
            when = None
    ids = frozenset(
        row.get("job_id") for row in prior.get("complete_candidate_list", []) if row.get("job_id")
    )
    return when, ids, prior.get("run_id")


def _assemble_local_report(jobs, *, run_id, dt, coverage=None, dedup=None, sources=None,
                           run_started_at=None, previous_report=None):
    """Screen, score, dedup and render exactly as production does, from an in-memory job list.

    `run_started_at` and `previous_report` carry the same freshness boundary the Lambda path reads out
    of S3. Without them this local path reproduced the very defect the S3 path was repaired for: it
    built a ReportInput with no timing, so every age was measured against the END of the calendar day
    and nothing could ever be labelled a new arrival.
    """
    from src.candidate.history import load_history
    from src.candidate.ownership import assess_all
    from src.candidate.policy import check_divergence, load_projection
    from src.candidate.screening import screen_all
    from src.common.dedup import deduplicate
    from src.report.handler import (
        CoverageInput,
        ReportInput,
        _history_projection_state,
        render_report,
    )
    from src.scoring.scoring import ScoreContext, score_job

    jobs, dedup_report = deduplicate(jobs)
    previous_at, previous_ids, previous_run_id = _load_previous_local_report(previous_report)
    started = run_started_at or _now()
    scored_as_of = started
    cards = [score_job(ScoreContext(job=j), today=scored_as_of) for j in jobs]
    screens = screen_all(jobs)
    # Same assessment the Lambda path runs. Omitting it here would leave the broad-ownership
    # retention path dead on exactly the surface a local round is inspected from, so a `discover`
    # run would report a different candidate set than the deployed one on identical input.
    ownership = assess_all(jobs)

    history = load_history()
    history_status = {}
    if history is not None:
        for job in jobs:
            entry = history.lookup(
                employer_name=job.employer_name, title=job.title,
                url=job.apply_url or job.posting_url,
            )
            if entry is not None:
                history_status[job.job_id] = (
                    entry.status, entry.conflict_detail if entry.status_conflict else None
                )

    projection = load_projection()
    if projection is None:
        note = "no committed policy projection found; run `policy-refresh`"
    else:
        note = (
            f"projection {projection.projection_version} built {projection.built_at.date()} — "
            f"{check_divergence(projection).summary()}"
        )
    cov = coverage or CoverageInput()
    cov.policy_projection_note = note
    # Same projection state the Lambda path reports. Omitting it here would make a local round say
    # nothing about a stale history while the deployed one says so — the identical divergence the
    # ownership assessment above is wired in to avoid.
    cov.history_projection = _history_projection_state(history, dt)

    source_ids = sorted(sources or {j.source_id for j in jobs})
    inp = ReportInput(
        run_id=run_id, dt=dt,
        expected_sources=source_ids, succeeded_sources=source_ids,
        jobs=jobs, scorecards=cards, screen_results=screens,
        ownership_results=ownership,
        history_status=history_status, coverage=cov,
        dedup=dedup or dedup_report.to_json(),
        run_started_at=started,
        previous_run_at=previous_at,
        previously_reported_ids=previous_ids if previous_run_id or previous_ids else None,
        timing={
            "run_started_at": started.isoformat(),
            "previous_run_at": previous_at.isoformat() if previous_at else None,
            "previous_run_id": previous_run_id,
            "basis": "local_cli_invocation",
            "cold_start_run": previous_at is None and not previous_ids,
            "previously_reported_count": len(previous_ids),
            "boundary": "reported-ids" if previous_ids else (
                "timestamp" if previous_at else "cold-start"),
        },
    )
    return inp, render_report(inp)


def cmd_discover(args) -> int:
    """Run the discovery stage, then screen/score/dedup and render the full candidate report."""
    started_at = _now()   # the real start of this round, captured before any fetch
    from src.report.handler import CoverageInput
    from src.common.connectors import FetchResult
    from src.discovery.connectors import get_discovery_connector
    from src.discovery.handler import run_discovery

    run_id = args.run_id or _now().strftime("%Y-%m-%d")
    dt = args.dt or run_id
    providers = [p.strip() for p in args.providers.split(",") if p.strip()] if args.providers else None

    if args.live:
        def fetcher(provider, token, url):
            return get_discovery_connector(provider).fetch_raw(token)
        mode = "LIVE (public read-only endpoints)"
    else:
        if not args.fixture_dir:
            print("offline mode needs --fixture-dir (or pass --live)", file=sys.stderr)
            return 2
        fixtures = Path(args.fixture_dir)

        def fetcher(provider, token, url):
            path = fixtures / f"{provider}.json"
            if not path.is_file():
                raise FileNotFoundError(f"no fixture for {provider} at {path}")
            now = _now()
            return FetchResult(
                raw_bytes=path.read_bytes(), http_status=200, error_class=None,
                endpoint_url=str(path), request_at=now, response_at=now,
            )
        mode = f"OFFLINE fixtures from {fixtures}"

    outcome = run_discovery(
        run_id=run_id, now=_now(), fetcher=fetcher, providers=providers,
        known_employers=_known_employers(args.config), monitored_count=args.monitored_count,
    )
    doc = outcome.coverage_doc()
    coverage = CoverageInput(
        discovery_attempted=doc["discovery_attempted"],
        discovery_succeeded=doc["discovery_succeeded"],
        query_families_total=doc["query_families_total"],
        query_families_covered=doc["query_families_covered"],
        query_families_saturated=doc["query_families_saturated"],
        query_families_deferred=doc["query_families_deferred"],
        query_families_never_run=doc["query_families_never_run"],
        backlog_items=doc["backlog_items"],
        backlog_reason=doc.get("backlog_reason"),
        budgets=doc["budgets"],
        credential_gated=doc["credential_gated"],
        inaccessible=doc["inaccessible"],
        attributions=doc["attributions"],
        admission_summary=doc["admission_summary"],
        previously_unseen_employers=sorted(
            {j.employer_name for j in outcome.jobs if j.employer_name}
            - _known_employers(args.config)
        ),
    )

    print(f"# discovery mode: {mode}", file=sys.stderr)
    # A previous report in the output directory is this round's previous observation boundary. Read
    # BEFORE the new one overwrites it.
    previous = getattr(args, "previous_report", None) or (args.out if args.out else None)
    _inp, (markdown, report_json) = _assemble_local_report(
        outcome.jobs, run_id=run_id, dt=dt, coverage=coverage,
        sources={j.source_id for j in outcome.jobs} or set(doc["discovery_attempted"]),
        run_started_at=started_at, previous_report=previous,
    )
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "daily_report.md").write_text(markdown)
        (out / "daily_report.json").write_text(json.dumps(report_json, indent=2, default=str))
        (out / "discovery_coverage.json").write_text(json.dumps(doc, indent=2, default=str))
        print(f"wrote {out}/daily_report.md, daily_report.json, discovery_coverage.json",
              file=sys.stderr)
    else:
        print(markdown)
    return 0


def cmd_policy_refresh(args) -> int:
    from src.candidate.policy import build_projection, save_projection

    projection, missing = build_projection(args.repo_root)
    if missing:
        print("MISSING policy sources (projection NOT written):", file=sys.stderr)
        for item in missing:
            print(f"  - {item}", file=sys.stderr)
        print(
            "A projection built from a subset of the policy is not the policy. Fix the paths or "
            "confirm the source moved, then re-run.", file=sys.stderr,
        )
        return 1
    save_projection(projection, args.out)
    print(f"wrote {args.out} from {len(projection.sources)} policy sources")
    for ref in projection.sources:
        print(f"  {ref.key:16s} {ref.sha256[:16]}  {ref.path}")
    return 0


def cmd_policy_check(args) -> int:
    from src.candidate.policy import check_divergence, load_projection

    projection = load_projection(args.projection)
    if projection is None:
        print(f"no projection at {args.projection}; run `policy-refresh`", file=sys.stderr)
        return 1
    divergence = check_divergence(projection, args.repo_root)
    print(divergence.summary())
    return 1 if divergence.diverged else 0


def cmd_history_scan(args) -> int:
    """Drift-check: which application folders are absent from the reviewed projection?"""
    from src.candidate.history import build_history, load_history

    reviewed = load_history(args.projection)
    scanned, warnings = build_history(args.root)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    reviewed_keys = {(e.employer_key, e.title_key) for e in (reviewed.entries if reviewed else [])}
    reviewed_urls = {e.posting_url_key for e in (reviewed.entries if reviewed else [])
                     if e.posting_url_key}
    new_rows = [
        e for e in scanned.entries
        if (e.employer_key, e.title_key) not in reviewed_keys
        and (e.posting_url_key or "") not in reviewed_urls
    ]
    print(f"reviewed entries: {len(reviewed.entries) if reviewed else 0}")
    print(f"folders scanned:  {len(scanned.entries)}")
    print(f"not in the reviewed projection: {len(new_rows)}")
    for entry in new_rows:
        print(f"  - {entry.employer_name} | {entry.role_title or '(role not in folder name)'} "
              f"| scanner read: {entry.status.value} | {entry.folder}")
    if new_rows:
        print(
            "\nThese need an operator/agent read before they can affect deduplication. A scan is "
            "capped at PREPARED and can never conclude a submission on its own."
        )
    return 0


def cmd_history_refresh(args) -> int:
    """Rebuild the application-history projection from evidence. Repeatable, and read-only at source.

    Dry by default: it prints exactly what would change and writes nothing until `--write`. A
    refresh that silently rewrote the file the report depends on would be the same class of
    invisible move the projection exists to prevent.
    """
    from src.candidate.history import refresh_history, save_history

    history, changes = refresh_history(
        projection_path=args.projection,
        inbox_root=args.root,
        submission_log_root=args.submission_logs,
    )
    print(f"submission logs read:  {len(changes['submission_logs_read'])}")
    print(f"evidence cutoff:       {changes['cutoff'] or '(none found)'}")
    print(f"entries:               {changes['entries_before']} -> {changes['entries_after']}")
    print(f"status upgrades:       {len(changes['status_changed'])}")
    for line in changes["status_changed"]:
        print(f"  - {line}")
    print(f"new entries:           {len(changes['added'])}")
    for line in changes["added"]:
        print(f"  + {line}")
    print(f"held, not settled:     {changes['unresolved']}")
    for record in history.unresolved:
        print(f"  ? {record.employer_name} | {record.role_title} | {record.reason}")
    # Folders the projection does not know about. Reported, never merged: a scanner row is capped at
    # PREPARED, and the report moves anything that is not NEW out of the candidate sections, so
    # merging one would demote a live opening on the strength of a folder name.
    print(f"folders not in the projection (drift, not merged): {len(changes['scan_drift'])}")
    for line in changes["scan_drift"]:
        print(f"  ~ {line}")
    for warning in changes["warnings"]:
        print(f"warning: {warning}", file=sys.stderr)

    if not args.write:
        print("\nDRY RUN — nothing written. Re-run with --write to update the projection.")
        return 0
    save_history(history, args.projection)
    print(f"\nwrote {args.projection}")
    return 0


def cmd_import_urls(args) -> int:
    from src.discovery.manual_import import import_urls

    urls = []
    if args.url:
        urls.extend(args.url)
    if args.file:
        urls.extend(
            line.strip() for line in Path(args.file).read_text().splitlines() if line.strip()
        )
    if not urls:
        print("no URLs given (use --url or --file)", file=sys.stderr)
        return 2
    if not args.live:
        print(
            "import-urls needs --live: it fetches operator-supplied pages through the fetch guard.",
            file=sys.stderr,
        )
        return 2

    ats_fetch = None
    if args.follow_ats:
        from src.common.connectors import get_connector

        def ats_fetch(provider, token):
            connector = get_connector(provider)
            return connector.build_snapshot(token, connector.fetch_raw(token))

    outcome = import_urls(urls, now=_now(), ats_fetch=ats_fetch)
    print(json.dumps(outcome.to_json(), indent=2))
    if outcome.jobs:
        _inp, (markdown, _js) = _assemble_local_report(
            outcome.jobs, run_id=_now().strftime("%Y-%m-%d"), dt=_now().strftime("%Y-%m-%d"),
        )
        print(markdown)
    return 0


def cmd_coverage_diff(args) -> int:
    """Compare the OLD monitored footprint against the NEW discovery footprint on one run.

    A higher raw job count is explicitly not success, so employer/industry/source-type breadth and
    eligible recall are reported separately from the raw totals.
    """
    old = json.loads(Path(args.old).read_text())
    new = json.loads(Path(args.new).read_text())

    def footprint(report: dict) -> dict:
        rows = report.get("complete_candidate_list") or report.get("top_matches") or []
        employers = {r.get("employer") for r in rows if r.get("employer")}
        industries = {r.get("discovery_query_family") or "(monitored board)" for r in rows}
        source_types = {r.get("source_kind", "ATS_BOARD") for r in rows}
        sources = {r.get("source_id") for r in rows if r.get("source_id")}
        leads = sum(1 for r in rows if r.get("verification_state") == "UNVERIFIED_LEAD")
        return {
            "postings_considered": report.get("current_job_count", 0),
            "retained_credible": report.get("matching_job_count", len(rows)),
            "new_strong": report.get("new_strong_count"),
            "needs_check": report.get("needs_check_count"),
            "policy_excluded": report.get("policy_excluded_count"),
            "distinct_employers": len(employers),
            "distinct_query_families_or_boards": len(industries),
            "distinct_source_types": sorted(t for t in source_types if t),
            "distinct_sources": len(sources),
            "unverified_leads": leads,
            "employers": sorted(e for e in employers if e),
        }

    old_fp, new_fp = footprint(old), footprint(new)
    previously_unseen = sorted(set(new_fp["employers"]) - set(old_fp["employers"]))
    result = {
        "evaluation_note": (
            "Both sides are the same evaluation run. A higher raw posting count is NOT success; the "
            "load-bearing numbers are distinct employers, previously unseen employers, and eligible "
            "recall."
        ),
        "old_monitored_footprint": {k: v for k, v in old_fp.items() if k != "employers"},
        "new_discovery_footprint": {k: v for k, v in new_fp.items() if k != "employers"},
        "previously_unseen_employers_count": len(previously_unseen),
        "previously_unseen_employers": previously_unseen[:60],
        "employers_only_in_old": sorted(set(old_fp["employers"]) - set(new_fp["employers"]))[:30],
        "duplicates_merged_new": (new.get("dedup") or {}).get("hard_merges"),
        "distinct_requisitions_protected_new": (new.get("dedup") or {}).get(
            "links_blocked_as_distinct_requisitions"
        ),
        "remaining_coverage_limitations": (new.get("coverage") or {}),
    }
    print(json.dumps(result, indent=2, default=str))
    return 0


def cmd_downgrade_state(args) -> int:
    """Rehearse or perform the rollback state downgrade. DRY RUN unless --apply is given.

    Source rollback alone is not enough: the baseline release's models use extra="forbid" and reject
    the additive fields the new code writes. This makes persisted state readable again, after taking
    a backup, without dropping a single job.
    """
    import boto3

    from src.common.rollback import downgrade_bucket_state

    if not args.bucket:
        print("--bucket is required", file=sys.stderr)
        return 2
    if args.apply and not args.i_have_a_backup_plan:
        print(
            "Refusing to write. --apply rewrites persisted production state.\n"
            "It takes its own backup first, but this is a deployment-time operator action: re-run "
            "with --i-have-a-backup-plan to confirm you intend it.",
            file=sys.stderr,
        )
        return 2
    s3 = boto3.client("s3")
    report = downgrade_bucket_state(
        s3, args.bucket, dt=args.dt or _now().strftime("%Y-%m-%d"), dry_run=not args.apply
    )
    print(json.dumps(report, indent=2, default=str))
    if not args.apply:
        print("\nDRY RUN — nothing was written. Re-run with --apply "
              "--i-have-a-backup-plan to perform it.", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jprs", description="JPRS local dev CLI (offline).")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("connect", help="run a connector against a local fixture")
    c.add_argument("--provider", required=True)
    c.add_argument("--board-token", required=True)
    c.add_argument("--fixture", required=True)
    c.add_argument("--prior-count", type=int, default=None)
    c.set_defaults(func=cmd_connect)

    d = sub.add_parser("diff", help="run the differ over two local snapshot-day fixtures")
    d.add_argument("--prev", required=True)
    d.add_argument("--curr", required=True)
    d.add_argument("--state", default=None, help="optional state file (read+write)")
    d.add_argument("--today", default=None, help="ISO datetime pinned for freshness/repost")
    d.set_defaults(func=cmd_diff)

    r = sub.add_parser("report", help="render a report from an events+scorecards fixture")
    r.add_argument("--fixture", required=True)
    r.set_defaults(func=cmd_report)

    registry = sub.add_parser("registry", help="render the operator registry as SSM JSON")
    registry.add_argument("--config", default="config/companies.yaml")
    registry.add_argument("--compact", action="store_true")
    registry.set_defaults(func=cmd_registry)

    disc = sub.add_parser("discover", help="run discovery and render the full candidate report")
    disc.add_argument("--live", action="store_true",
                      help="fetch the public read-only discovery endpoints (default: offline)")
    disc.add_argument("--fixture-dir", default=None,
                      help="offline mode: directory of <provider>.json payloads")
    disc.add_argument("--providers", default=None, help="comma-separated provider subset")
    disc.add_argument("--config", default="config/companies.yaml")
    disc.add_argument("--monitored-count", type=int, default=15)
    disc.add_argument("--run-id", default=None)
    disc.add_argument("--dt", default=None)
    disc.add_argument("--out", default=None, help="write the report into this directory")
    disc.add_argument("--previous-report", default=None,
                      help="previous round's daily_report.json (or its directory) — the "
                           "freshness boundary; defaults to --out, which holds the last "
                           "run's report")
    disc.set_defaults(func=cmd_discover)

    pol = sub.add_parser("policy-refresh",
                         help="rebuild the candidate-policy projection from the sibling sources")
    pol.add_argument("--repo-root", default=".")
    pol.add_argument("--out", default="config/candidate_policy.json")
    pol.set_defaults(func=cmd_policy_refresh)

    polc = sub.add_parser("policy-check", help="report projection-vs-source divergence")
    polc.add_argument("--repo-root", default=".")
    polc.add_argument("--projection", default="config/candidate_policy.json")
    polc.set_defaults(func=cmd_policy_check)

    hist = sub.add_parser("history-scan",
                          help="drift-check the reviewed application-history projection")
    hist.add_argument("--root", default="../Infotropy Book/INBOX/Employment Search")
    hist.add_argument("--projection", default="config/application_history.json")
    hist.set_defaults(func=cmd_history_scan)

    histr = sub.add_parser(
        "history-refresh",
        help="rebuild the application-history projection from the submission logs (dry by default)")
    histr.add_argument("--root", default="../Infotropy Book/INBOX/Employment Search")
    histr.add_argument("--projection", default="config/application_history.json")
    histr.add_argument(
        "--submission-logs",
        default="../Infotropy Book/career-factory/outputs/candidates/brett-westerlund/applications")
    histr.add_argument("--write", action="store_true",
                       help="required to modify the projection; omit for a dry run")
    histr.set_defaults(func=cmd_history_refresh)

    imp = sub.add_parser("import-urls", help="import operator-supplied posting URLs")
    imp.add_argument("--url", action="append", default=None)
    imp.add_argument("--file", default=None, help="file with one URL per line")
    imp.add_argument("--live", action="store_true", help="required; this command fetches pages")
    imp.add_argument("--follow-ats", action="store_true",
                     help="for a supported ATS URL, read the employer's board directly")
    imp.set_defaults(func=cmd_import_urls)

    dg = sub.add_parser("downgrade-state",
                        help="make persisted state readable by the previous release (rollback)")
    dg.add_argument("--bucket", required=True)
    dg.add_argument("--dt", default=None, help="event partition to downgrade (default: today)")
    dg.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    dg.add_argument("--i-have-a-backup-plan", action="store_true",
                    dest="i_have_a_backup_plan",
                    help="required with --apply; confirms this deployment-time action is intended")
    dg.set_defaults(func=cmd_downgrade_state)

    cov = sub.add_parser("coverage-diff",
                         help="compare the old monitored footprint with the new discovery footprint")
    cov.add_argument("--old", required=True, help="daily_report.json from the monitored-only run")
    cov.add_argument("--new", required=True, help="daily_report.json from the discovery run")
    cov.set_defaults(func=cmd_coverage_diff)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
