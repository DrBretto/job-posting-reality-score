"""Enumerate Lambda — PANEL_DISSENT M1, the completeness backbone.

The whole two-silences guarantee (VERIFIED-QUIET vs INCOMPLETE vs NO-RUN) depends on this:
it reads the operator-curated company/board registry, writes a RUN_OPEN manifest to S3 recording
the EXPECTED [provider, company] task set for the run, and fans out one SQS message per company.

Completeness is later judged manifest-expected sources vs SUCCESS sentinels — NEVER wall-clock.
`build_manifest` + `incomplete_sources` are pure so the INCOMPLETE-detection contract is testable
without AWS.

Registry source: local `config/companies.yaml` for dev; SSM `/jprs/companies` in prod.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.common.connectors import ASHBY_ENABLED
from src.common.models import Provider, SourceKind


class CompanyEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Provider
    board_token: str
    company_slug: str
    enabled: bool = True
    # Optional operator-curated display name. Without it the employer label falls back to the board
    # token, which is still better than the hardcoded company table this replaced.
    employer_name: str | None = None


class DiscoverySourceEntry(BaseModel):
    """A discovery source: keyed by a question about work, not by an employer."""

    model_config = ConfigDict(extra="forbid")
    provider: Provider
    kind: str = "bulk_feed"                    # bulk_feed | query_feed
    enabled: bool = True
    max_requests_per_run: int = 1
    auth: str = "none"
    credential_env: list[str] = Field(default_factory=list)
    attribution_required: bool = True
    notes: str | None = None

    @property
    def source_id(self) -> str:
        # A discovery source is not board-keyed. "all" is its whole-feed slice; a query feed is
        # sliced per query family at fetch time.
        return f"{self.provider.value}:all"


class RunManifest(BaseModel):
    """The RUN_OPEN manifest — the authoritative expected-task set for a run."""

    model_config = ConfigDict(extra="forbid")
    run_id: str
    opened_at: datetime
    state: str = "RUN_OPEN"
    expected_tasks: list[str] = Field(default_factory=list)  # task_id = run_id:provider:company_slug
    expected_sources: list[str] = Field(default_factory=list)  # source_id = provider:board_token
    source_labels: dict[str, str] = Field(default_factory=dict)  # source_id -> operator company slug
    # source_id -> SourceKind. This is how the report can tell a monitored employer board apart from
    # an employer-independent feed, and therefore how it keeps collection health from being read as
    # market coverage.
    source_kinds: dict[str, str] = Field(default_factory=dict)
    # Discovery sources are recorded as EXPECTED so a discovery source that silently produced nothing
    # reads INCOMPLETE, exactly as a monitored board would.
    expected_discovery_sources: list[str] = Field(default_factory=list)
    # Sources that are configured but cannot run without a credential. Named here so the coverage
    # statement is built from the manifest rather than reconstructed later.
    credential_gated_sources: dict[str, list[str]] = Field(default_factory=dict)


def _task_id(run_id: str, provider: str, company_slug: str) -> str:
    return f"{run_id}:{provider}:{company_slug}"


def load_registry_from_yaml(path: str | Path) -> list[CompanyEntry]:
    import yaml

    data = yaml.safe_load(Path(path).read_text()) or {}
    entries = [CompanyEntry.model_validate(c) for c in data.get("companies", [])]
    return entries


def _active_entries(entries: list[CompanyEntry]) -> list[CompanyEntry]:
    active = []
    for e in entries:
        if not e.enabled:
            continue
        # Ashby stays gated until UUID permanence is verified (D2/U4); never fan out a gated source.
        if e.provider == Provider.ASHBY and not ASHBY_ENABLED:
            continue
        active.append(e)
    return active


def load_discovery_sources(path: str | Path) -> list[DiscoverySourceEntry]:
    import yaml

    p = Path(path)
    if not p.is_file():
        return []
    data = yaml.safe_load(p.read_text()) or {}
    return [
        DiscoverySourceEntry.model_validate(s) for s in data.get("discovery_sources", [])
    ]


def _active_discovery(
    sources: list[DiscoverySourceEntry], env=None
) -> tuple[list[DiscoverySourceEntry], dict[str, list[str]]]:
    """Split discovery sources into runnable and credential-gated.

    A gated source is NAMED, not dropped. Silently omitting it would let the report claim the
    planned coverage was achieved when the one source with general industry breadth never ran.
    """
    import os

    env = env if env is not None else os.environ
    runnable: list[DiscoverySourceEntry] = []
    gated: dict[str, list[str]] = {}
    for source in sources:
        if not source.enabled:
            continue
        missing = [name for name in source.credential_env if not env.get(name)]
        if missing:
            gated[source.source_id] = missing
            continue
        runnable.append(source)
    return runnable, gated


def build_manifest(
    run_id: str,
    entries: list[CompanyEntry],
    *,
    now: datetime | None = None,
    discovery_sources: list[DiscoverySourceEntry] | None = None,
    env=None,
) -> RunManifest:
    """Pure: registry -> RUN_OPEN manifest recording the expected task set."""
    now = now or datetime.now(timezone.utc)
    active = _active_entries(entries)
    expected_tasks = [_task_id(run_id, e.provider.value, e.company_slug) for e in active]
    expected_sources = [f"{e.provider.value}:{e.board_token}" for e in active]
    source_labels = {
        f"{e.provider.value}:{e.board_token}": (e.employer_name or e.company_slug) for e in active
    }
    source_kinds = {
        f"{e.provider.value}:{e.board_token}": SourceKind.ATS_BOARD.value for e in active
    }

    runnable_discovery, gated = _active_discovery(discovery_sources or [], env=env)
    discovery_ids = [s.source_id for s in runnable_discovery]
    for source in runnable_discovery:
        source_kinds[source.source_id] = SourceKind.DISCOVERY_FEED.value
        source_labels.setdefault(source.source_id, source.provider.value)

    return RunManifest(
        run_id=run_id,
        opened_at=now,
        expected_tasks=sorted(expected_tasks),
        expected_sources=sorted(expected_sources),
        source_labels=dict(sorted(source_labels.items())),
        source_kinds=dict(sorted(source_kinds.items())),
        expected_discovery_sources=sorted(discovery_ids),
        credential_gated_sources=dict(sorted(gated.items())),
    )


def incomplete_sources(manifest: RunManifest, succeeded_source_ids: set[str]) -> list[str]:
    """The INCOMPLETE-detection contract: expected sources lacking a SUCCESS sentinel.

    A source in the manifest that never produced a SUCCESS sentinel reads INCOMPLETE (not quiet).
    Returns the sorted list of source_ids that are missing — empty list => run is complete.
    """
    return sorted(s for s in manifest.expected_sources if s not in succeeded_source_ids)


def fan_out_messages(run_id: str, entries: list[CompanyEntry]) -> list[dict]:
    """One SQS message body per company (pure; the handler enqueues these)."""
    return [
        {
            "run_id": run_id,
            "task_id": _task_id(run_id, e.provider.value, e.company_slug),
            "provider": e.provider.value,
            "board_token": e.board_token,
            "company_slug": e.company_slug,
            "employer_name": e.employer_name or e.company_slug,
            "correlation_id": run_id,
        }
        for e in _active_entries(entries)
    ]


def handler(event, context):  # pragma: no cover - AWS glue
    import boto3

    from src.common import s3layout

    bucket = os.environ["JPRS_BUCKET"]
    queue_url = os.environ["JPRS_COLLECT_QUEUE_URL"]
    run_id = event.get("run_id") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entries = _load_registry()
    discovery_sources = load_discovery_sources(
        os.environ.get("JPRS_DISCOVERY_YAML", "config/discovery_sources.yaml")
    )
    manifest = build_manifest(run_id, entries, discovery_sources=discovery_sources)

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=bucket,
        Key=s3layout.run_manifest_key(run_id),
        Body=manifest.model_dump_json().encode(),
        ContentType="application/json",
    )

    sqs = boto3.client("sqs")
    messages = fan_out_messages(run_id, entries)
    for msg in messages:
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(msg),
            MessageAttributes={
                "correlation_id": {"DataType": "String", "StringValue": run_id},
            },
        )

    return {
        "run_id": run_id,
        "expected_tasks": len(manifest.expected_tasks),
        "expected_discovery_sources": manifest.expected_discovery_sources,
        "credential_gated_sources": manifest.credential_gated_sources,
        "enqueued": len(messages),
    }


def _load_registry() -> list[CompanyEntry]:  # pragma: no cover - AWS glue
    ssm_param = os.environ.get("JPRS_COMPANIES_SSM")
    if ssm_param:
        import boto3

        ssm = boto3.client("ssm")
        raw = ssm.get_parameter(Name=ssm_param)["Parameter"]["Value"]
        data = json.loads(raw)
        return [CompanyEntry.model_validate(c) for c in data.get("companies", data)]
    path = os.environ.get("JPRS_COMPANIES_YAML", "config/companies.yaml")
    return load_registry_from_yaml(path)
