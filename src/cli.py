"""Thin local CLI for dev/test only (NOT a Lambda entry point).

Subcommands:
  connect   — run a connector against a local fixture file (no network), print the snapshot + jobs
  diff      — run the differ over two local snapshot-day fixtures (replay-from-raw semantics)
  report    — render a report locally from an events+scorecards fixture
  registry  — render config/companies.yaml as the JSON payload stored in SSM

Every path is offline: fixtures are JSON files, never a live ATS call.
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
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
