"""M1 completeness-backbone (enumerate) + M2 narrator-boundary tests."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.cli import main as cli_main
from src.enumerate.handler import (
    CompanyEntry,
    build_manifest,
    fan_out_messages,
    incomplete_sources,
    load_registry_from_yaml,
)
from src.llm.narrator import NARRATOR_ENABLED, narrate, post_check
from src.common.models import Provider

NOW = datetime(2026, 7, 24, tzinfo=timezone.utc)


def _entries():
    return [
        CompanyEntry(provider=Provider.GREENHOUSE, board_token="stripe", company_slug="stripe"),
        CompanyEntry(provider=Provider.GREENHOUSE, board_token="figma", company_slug="figma"),
        # a disabled entry must NOT be enumerated
        CompanyEntry(provider=Provider.GREENHOUSE, board_token="off", company_slug="off", enabled=False),
        # Ashby is now ENABLED (its identity concern was resolved with live evidence on 2026-09-24),
        # so this entry IS enumerated. It used to be excluded by the ASHBY_ENABLED feature flag.
        CompanyEntry(provider=Provider.ASHBY, board_token="ramp", company_slug="ramp"),
    ]


def test_manifest_records_expected_task_set():
    m = build_manifest("2026-07-24", _entries(), now=NOW)
    assert m.state == "RUN_OPEN"
    assert m.run_id == "2026-07-24"
    # the two enabled Greenhouse sources plus the now-enabled Ashby board; the disabled one is out
    assert m.expected_sources == ["ashby:ramp", "greenhouse:figma", "greenhouse:stripe"]
    assert m.source_labels == {
        "ashby:ramp": "ramp",
        "greenhouse:figma": "figma",
        "greenhouse:stripe": "stripe",
    }
    assert len(m.expected_tasks) == 3
    # Every monitored board is labelled as such, which is how the report keeps collection health
    # from being read as market coverage.
    assert set(m.source_kinds.values()) == {"ATS_BOARD"}


def test_incomplete_detection_contract():
    """A source in the manifest that never produced a SUCCESS sentinel reads INCOMPLETE."""
    m = build_manifest("2026-07-24", _entries(), now=NOW)
    # only stripe succeeded -> figma is INCOMPLETE
    missing = incomplete_sources(m, succeeded_source_ids={"greenhouse:stripe"})
    assert missing == ["ashby:ramp", "greenhouse:figma"]
    # all succeeded -> empty (complete)
    assert incomplete_sources(
        m, {"greenhouse:stripe", "greenhouse:figma", "ashby:ramp"}
    ) == []


def test_fan_out_one_message_per_active_company():
    msgs = fan_out_messages("2026-07-24", _entries())
    assert len(msgs) == 3
    assert {mm["board_token"] for mm in msgs} == {"stripe", "figma", "ramp"}
    # The employer name travels with the task so the collector can stamp it onto each job, instead
    # of the report translating a board token through a hardcoded company table.
    assert all(mm["employer_name"] for mm in msgs)
    assert all(mm["run_id"] == "2026-07-24" and mm["correlation_id"] == "2026-07-24" for mm in msgs)


def test_registry_loads_from_config_yaml():
    entries = load_registry_from_yaml("config/companies.yaml")
    slugs = {e.company_slug for e in entries if e.enabled}
    assert len(slugs) == 15
    assert {
        "machinify", "icon", "cargomatic", "future", "axiomatic-ai", "nimble-gravity",
        "legion-intelligence", "warp", "tailscale", "grafana-labs", "mozilla", "snorkel-ai",
        "bolt-new", "cadence-solutions", "implicit",
    } == slugs


def test_registry_cli_renders_ssm_payload(capsys):
    assert cli_main(["registry", "--compact"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["companies"]) == 15
    assert payload["companies"][0]["board_token"] == "machinifyinc"


def test_narrator_off_by_default_returns_template():
    """M2: V1 path is deterministic-only; narrator is feature-flagged OFF."""
    assert NARRATOR_ENABLED is False
    out = narrate({"evidence_values": []}, template_fallback="First observed 2026-07-24.")
    assert out == "First observed 2026-07-24."


def test_post_check_rejects_unsupported_number():
    ok, reason = post_check("Live for 999 days.", evidence_values={"12", "2026-07-24"})
    assert ok is False and "unsupported" in reason


def test_post_check_rejects_accusatory_banned_paraphrase():
    """M2 red-team: a paraphrase with a banned token is rejected (falls back to template)."""
    ok, reason = post_check("This appears to be a fake vacancy.", evidence_values=set())
    assert ok is False and "banned" in reason


def test_post_check_allows_supported_numbers():
    ok, _ = post_check("First observed 2026-07-24; edited 3 times.",
                       evidence_values={"2026-07-24", "3"})
    assert ok is True
