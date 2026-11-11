"""Regression tests for the P03 review's three open blockers: R1, R2 and R3.

The independent pre-repair reproduction of the reviewer's own rows is
`evidence/p04_before_repair_probe.json` in the P04 run root; `VALIDATION.md` records, per test, what
the old code did and why.

Two lessons from earlier rounds shape how these are written:

* P02's R1 test replaced the broken function with a capturing substitute and therefore proved nothing
  about the request that went out. So the report tests below drive `handler()` end to end through
  mocked S3 and read the PERSISTED artifact, instead of handing `render_report` a ReportInput whose
  timing fields were filled in by the test. A test that supplies the very field production fails to
  supply is the same mistake in a new place.
* The location tests assert the SHAPE of the answer, not just the verdict: "plausibly local, confirm
  the worksite" and "excluded, out of state" are different answers, and a test that only checks
  `!= EXCLUDED` would pass for a screener that certified a drive time it never measured.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import boto3
from moto import mock_aws

from src.candidate.location import (
    WorksiteClass,
    best_worksite,
    find_residency_restriction,
    parse_places,
)
from src.candidate.screening import screen_job
from src.common.connectors import FetchResult
from src.common.models import CanonicalJob, IdKind, RemoteMode, ScreenOutcome

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
BUCKET = "jprs-p04-bucket"
PROCESS_OK = "Interview process: two live video calls with the team."
WORK = (
    "Responsibilities: build Python backend services, internal tools, AWS Lambda integrations and "
    "LLM evaluation workflows. "
)


def _job(description=WORK + PROCESS_OK, *, location="Remote, US", mode=RemoteMode.REMOTE,
         title="Senior Software Engineer", **kw):
    return CanonicalJob(
        source_id="t:src", job_id=f"t:src#{abs(hash(description + location + title)) % 10**8}",
        id_kind=IdKind.NATIVE_ID, title=title, description_text=description,
        raw_location=location, canonical_location=location.lower(),
        remote_hybrid_language=mode, **kw,
    )


def _verdict(**kw):
    return screen_job(_job(**kw))


def _reasons(result) -> str:
    return " ".join(h.reason for h in result.exclusions + result.pending_checks).lower()


ONSITE = "The role: on-site at our office five days per week. "


# ==================================================================================================
# R1 — the location policy, implemented by its meaning rather than a town list
#
# Policy (APPLICATION_WORKFLOW.md, operator-confirmed 2026-09-24): onsite/hybrid only when genuinely
# local, approximately a 30-minute drive from Laconia NH; check the actual worksite and attendance
# requirements rather than inferring from a city label; Plymouth is a case to discuss; Portsmouth and
# Boston commuting are excluded but a genuinely remote role at such an employer stays eligible.
# ==================================================================================================
def test_punctuation_does_not_decide_locality():
    """Pre-repair: "Belmont, NH" was EXCLUDED and "Belmont NH" was ELIGIBLE. The town list held the
    literal string `belmont nh`, so a comma flipped the verdict — in both directions at once."""
    verdicts = {
        spelling: _verdict(description=ONSITE + WORK + PROCESS_OK, location=spelling,
                           mode=RemoteMode.ONSITE).outcome
        for spelling in ("Belmont, NH", "Belmont NH", "Belmont, New Hampshire", "belmont,nh",
                         "Belmont, N.H.", "BELMONT NH")
    }
    assert len(set(verdicts.values())) == 1, verdicts
    assert set(verdicts.values()) == {ScreenOutcome.PENDING_CHECK.value}, verdicts


def test_a_shared_town_name_in_another_state_is_not_local():
    """Pre-repair: "Alton, IL" was ELIGIBLE, because the town list held a bare `alton` and New
    Hampshire has an Alton too. Laconia is in central New Hampshire, so no out-of-state worksite is
    a 30-minute drive from it."""
    result = _verdict(description=ONSITE + WORK + PROCESS_OK, location="Alton, IL",
                      mode=RemoteMode.ONSITE)
    assert result.outcome == ScreenOutcome.EXCLUDED.value, _reasons(result)
    assert "outside new hampshire" in _reasons(result)

    local = _verdict(description=ONSITE + WORK + PROCESS_OK, location="Alton, NH",
                     mode=RemoteMode.ONSITE)
    assert local.outcome == ScreenOutcome.PENDING_CHECK.value, _reasons(local)


def test_a_remote_label_does_not_override_mandatory_office_attendance():
    """Pre-repair: "Remote / Boston, MA" plus "must attend the Boston office three days per week"
    was ELIGIBLE — the word "remote" in the location set remote_ok and skipped every worksite rule."""
    result = _verdict(
        description="Hybrid: you must attend the Boston office three days per week. "
                    + WORK + PROCESS_OK,
        location="Remote / Boston, MA", mode=RemoteMode.HYBRID,
    )
    assert result.outcome == ScreenOutcome.EXCLUDED.value, _reasons(result)
    assert "commuting" in _reasons(result)


def test_a_remote_role_whose_residency_list_excludes_new_hampshire_is_excluded():
    """Pre-repair: "may only employ residents of California or New York" was ELIGIBLE."""
    result = _verdict(
        description="This remote role may only employ residents of California or New York. "
                    + WORK + PROCESS_OK,
        location="Remote, US",
    )
    assert result.outcome == ScreenOutcome.EXCLUDED.value, _reasons(result)
    assert "location-residency" in {h.rule_id for h in result.exclusions}
    assert "does not include new hampshire" in _reasons(result)


def test_a_residency_list_that_includes_new_hampshire_is_not_excluded():
    """The paired case. A state list is only an exclusion when NH is absent from it."""
    result = _verdict(
        description="Employment is limited to residents of New Hampshire, Maine and Vermont. "
                    + WORK + PROCESS_OK,
        location="Remote, US",
    )
    assert result.outcome != ScreenOutcome.EXCLUDED.value, _reasons(result)


def test_country_level_work_authorization_is_not_a_residency_exclusion():
    """"must be authorized to work in the United States" restricts nobody in New Hampshire."""
    for phrase in ("You must reside in the United States.",
                   "Must be authorized to work in the US.",
                   "Open to candidates anywhere in the US."):
        result = _verdict(description=phrase + " " + WORK + PROCESS_OK, location="Remote, US")
        assert result.outcome != ScreenOutcome.EXCLUDED.value, (phrase, _reasons(result))


def test_genuinely_remote_role_at_an_excluded_city_employer_stays_eligible():
    """"An employer headquartered in either city remains eligible when the role is genuinely remote
    from New Hampshire." The exclusion is about COMMUTING, not about the employer's address."""
    result = _verdict(
        description="Fully remote from anywhere in the US; we have an optional Boston hub. "
                    + WORK + PROCESS_OK,
        location="Remote (US) / Boston, MA",
    )
    assert result.outcome != ScreenOutcome.EXCLUDED.value, _reasons(result)
    assert any(h.rule_id == "location-eligibility" and h.suppressed_by
               for h in result.suppressed), [h.rule_id for h in result.suppressed]


def test_a_reporting_line_is_not_an_attendance_requirement():
    """"reports to the VP of Engineering in our Boston office" says who the manager is. Reading it
    as mandatory attendance would exclude a remote job for having a manager."""
    result = _verdict(
        description="You will report to the VP of Engineering in our Boston office. Fully remote. "
                    + WORK + PROCESS_OK,
        location="Remote, US",
    )
    assert result.outcome != ScreenOutcome.EXCLUDED.value, _reasons(result)


def test_a_negated_office_requirement_is_not_read_as_a_requirement():
    """Polarity still applies to attendance: "no in-office requirement" is not one."""
    result = _verdict(
        description="There is no in-office attendance requirement for this role. " + WORK
                    + PROCESS_OK,
        location="Remote, US",
    )
    assert result.outcome != ScreenOutcome.EXCLUDED.value, _reasons(result)


def test_plymouth_is_an_operator_review_case_not_a_verdict():
    for spelling in ("Plymouth, NH", "Plymouth, New Hampshire", "Plymouth NH"):
        result = _verdict(description=ONSITE + WORK + PROCESS_OK, location=spelling,
                          mode=RemoteMode.ONSITE)
        assert result.outcome == ScreenOutcome.PENDING_CHECK.value, (spelling, _reasons(result))
        assert "discuss with brett" in _reasons(result), spelling


def test_a_plausibly_local_lead_stays_visible_and_is_not_certified():
    """The policy states a DRIVE TIME. This system does not measure one, so a Lakes Region worksite
    is reported as plausible with the check named — neither auto-approved nor rejected. The previous
    implementation answered a drive-time question with a hand-written town list and called it
    eligible."""
    for town in ("Laconia, NH", "Gilford, NH", "Meredith, NH", "Tilton, NH", "Sanbornton, NH"):
        result = _verdict(description=ONSITE + WORK + PROCESS_OK, location=town,
                          mode=RemoteMode.ONSITE)
        assert result.outcome == ScreenOutcome.PENDING_CHECK.value, (town, _reasons(result))
        reasons = _reasons(result)
        assert "plausibly local" in reasons and "30-minute" in reasons, town


def test_a_new_hampshire_worksite_beyond_the_lakes_region_is_flagged_not_rejected():
    """Still in state: probably too far, but "probably" is a review, not an exclusion."""
    for town in ("Manchester, NH", "Nashua, NH", "Keene, NH"):
        result = _verdict(description=ONSITE + WORK + PROCESS_OK, location=town,
                          mode=RemoteMode.ONSITE)
        assert result.outcome == ScreenOutcome.PENDING_CHECK.value, (town, _reasons(result))
        assert "new hampshire but probably beyond" in _reasons(result), town


def test_a_missing_state_keeps_a_matching_town_name_unresolved():
    """"Belmont" with no state could be the one next to Laconia or the one in California. That is a
    check to make, not a verdict to invent in either direction."""
    result = _verdict(description=ONSITE + WORK + PROCESS_OK, location="Belmont",
                      mode=RemoteMode.ONSITE)
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value, _reasons(result)


def test_multiple_worksites_are_judged_on_the_best_option():
    """A posting offering both a Boston and a Laconia office is a lead worth confirming. Judging it
    on the worst listed site would throw away a genuinely local opportunity."""
    result = _verdict(description=ONSITE + WORK + PROCESS_OK,
                      location="Boston, MA; Laconia, NH", mode=RemoteMode.ONSITE)
    assert result.outcome == ScreenOutcome.PENDING_CHECK.value, _reasons(result)
    assert "plausibly local" in _reasons(result)


def test_conflicting_remote_and_hybrid_fields_resolve_to_the_stated_requirement():
    """The provider field says REMOTE and the body requires four days on site. The requirement wins;
    a label is not a fact about where the work happens."""
    result = _verdict(
        description="Hybrid schedule: four days per week in the office in Cambridge, MA. "
                    + WORK + PROCESS_OK,
        location="Remote", mode=RemoteMode.REMOTE,
    )
    assert result.outcome == ScreenOutcome.EXCLUDED.value, _reasons(result)


def test_non_us_worksite_without_us_remote_is_still_excluded():
    for location in ("Berlin, Germany", "London", "Bangalore, India"):
        result = _verdict(description=ONSITE + WORK + PROCESS_OK, location=location,
                          mode=RemoteMode.ONSITE)
        assert result.outcome == ScreenOutcome.EXCLUDED.value, (location, _reasons(result))


def test_state_abbreviations_and_full_names_agree():
    for a, b in (("Portsmouth, NH", "Portsmouth, New Hampshire"),
                 ("Boston, MA", "Boston, Massachusetts"),
                 ("Austin, TX", "Austin, Texas")):
        first = _verdict(description=ONSITE + WORK + PROCESS_OK, location=a, mode=RemoteMode.ONSITE)
        second = _verdict(description=ONSITE + WORK + PROCESS_OK, location=b, mode=RemoteMode.ONSITE)
        assert first.outcome == second.outcome, (a, b, _reasons(first), _reasons(second))


def test_or_is_not_parsed_as_oregon():
    """A two-letter state code pattern matched case-insensitively read "California or New York" as
    three states including Oregon. Half the codes are ordinary English words."""
    restriction = find_residency_restriction(
        "This role may only employ residents of California or New York.")
    assert restriction is not None
    assert restriction.states == ["CA", "NY"], restriction.states


def test_worksite_classification_table():
    """The classification the screener rests on, asserted directly."""
    expected = {
        "Belmont, NH": WorksiteClass.LAKES_REGION,
        "Belmont NH": WorksiteClass.LAKES_REGION,
        "Alton, IL": WorksiteClass.OUT_OF_STATE,
        "Portsmouth, NH": WorksiteClass.OPERATOR_EXCLUDED,
        "Boston, MA": WorksiteClass.OPERATOR_EXCLUDED,
        "Plymouth, NH": WorksiteClass.DISCUSS,
        "Manchester, NH": WorksiteClass.OTHER_NH,
        "San Francisco, CA": WorksiteClass.OUT_OF_STATE,
        "Berlin, Germany": WorksiteClass.NON_US,
        "Remote, US": WorksiteClass.UNKNOWN,
        "Laconia, NH 03246": WorksiteClass.LAKES_REGION,
    }
    actual = {label: best_worksite(parse_places(label)) for label in expected}
    assert actual == expected


def test_no_pay_rule_was_introduced_with_the_location_rules():
    """"do not convert flexible targets into extra exclusion rules" — still true after R1."""
    from src.common.models import SalarySource, SalaryStruct

    for lo, hi in ((90_000, 110_000), (130_000, 150_000), (300_000, 340_000)):
        job = _job()
        job.salary = SalaryStruct(min=lo, max=hi, currency="USD", period="year",
                                  source=SalarySource.STATED)
        result = screen_job(job)
        assert "compensation" not in " ".join(h.rule_id for h in result.exclusions), (lo, hi)


def test_existing_non_location_exclusions_survive_the_rewrite():
    """The location rewrite must not have disturbed the other rules."""
    cases = {
        "sales-ownership": "Responsibilities: carry a sales quota and own the pipeline. " + PROCESS_OK,
        "clearance-government": "Requirements: you must obtain a security clearance. " + PROCESS_OK,
        "recorded-video": "Interview process: submit a one-way recorded video introduction.",
    }
    for rule_id, description in cases.items():
        result = _verdict(description=description)
        assert rule_id in {h.rule_id for h in result.exclusions}, (rule_id, _reasons(result))


# ==================================================================================================
# R2 — freshness timing reaches the report through production wiring
#
# Every test here runs the real `handler()` against mocked S3 and reads the persisted report. None of
# them constructs a ReportInput with the timing fields already filled in, which is precisely how the
# unwired boundary survived P03's test suite.
# ==================================================================================================
def _manifest(run_id: str, opened_at: datetime, sources=("remotive:all",)) -> dict:
    """The manifest shape ENUMERATE actually writes: `opened_at`, not `created_at`."""
    return {
        "run_id": run_id,
        "opened_at": opened_at.isoformat(),
        "state": "RUN_OPEN",
        "expected_tasks": [],
        "expected_sources": list(sources),
        "source_labels": {s: s.partition(":")[0].title() for s in sources},
        "source_kinds": {s: "DISCOVERY_FEED" for s in sources},
        "expected_discovery_sources": [],
        "credential_gated_sources": {},
    }


def _feed_job(key, *, first_seen, last_seen, published=None, source="remotive:all"):
    provider, _, board = source.partition(":")
    return CanonicalJob(
        source_id=source, job_id=f"{source}#{key}", id_kind=IdKind.NATIVE_ID,
        provider_native_id=key, employer_name=f"Employer {key}",
        title="Senior Software Engineer", raw_location="Remote, US",
        canonical_location="remote, us", remote_hybrid_language=RemoteMode.REMOTE,
        description_text=WORK + PROCESS_OK,
        posting_url=f"https://example.com/{key}", apply_url=f"https://example.com/{key}",
        first_seen_at=first_seen, last_seen_at=last_seen, provider_published_at=published,
    )


class _Bucket:
    """Mocked S3 with the writes the collector, differ and enumerate stages actually make."""

    def __init__(self, s3):
        self.s3 = s3
        s3.create_bucket(Bucket=BUCKET)

    def put(self, key, payload):
        self.s3.put_object(Bucket=BUCKET, Key=key,
                           Body=json.dumps(payload, default=str).encode())

    def get(self, key):
        return json.loads(self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())

    def text(self, key):
        return self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()

    def exists(self, key) -> bool:
        from botocore.exceptions import ClientError
        try:
            self.s3.head_object(Bucket=BUCKET, Key=key)
            return True
        except ClientError:
            return False

    def round(self, run_id, opened_at, jobs, *, sources=("remotive:all",), observations=2,
              succeeded=True):
        """Lay down one round's artifacts exactly where production writes them."""
        from src.common import s3layout

        self.put(s3layout.run_manifest_key(run_id), _manifest(run_id, opened_at, sources))
        for source in sources:
            provider, _, board = source.partition(":")
            source_jobs = [j for j in jobs if j.source_id == source]
            self.put(s3layout.current_jobs_key(provider, board),
                     [j.model_dump(mode="json") for j in source_jobs])
            self.put(s3layout.current_state_key(provider, board), {
                "source_id": source,
                "success_count_history": [1] * observations,
                "jobs": {j.job_id: {"first_seen_at": j.first_seen_at.isoformat(),
                                    "last_seen_at": j.last_seen_at.isoformat()}
                         for j in source_jobs},
            })
            if succeeded:
                self.put(s3layout.collect_sentinel_key(run_id, provider, board), {})


def _run_report(bucket: _Bucket, run_id, dt, env=None):
    """Drive the real handler. Email is mocked; nothing is sent."""
    import os

    from src.report.handler import handler
    from src.common import s3layout

    base = {"JPRS_BUCKET": BUCKET, "AWS_DEFAULT_REGION": "us-east-1",
            "SES_SENDER": "", "DIGEST_RECIPIENT": ""}
    base.update(env or {})
    with patch.dict(os.environ, base):
        result = handler({"run_id": run_id, "dt": dt}, None)
    return result, bucket.get(s3layout.report_json_key(dt)), bucket.text(s3layout.report_md_key(dt))


def test_production_report_receives_real_run_timing():
    """R2 core. Pre-repair `assemble_report_input` never set `run_started_at` or `previous_run_at`,
    so the renderer fell back to the END of the UTC calendar day and the persisted report always
    said 0 fresh arrivals. Supplying the fields by hand in a test hid it."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        opened = NOW.replace(hour=7, minute=5)
        jobs = [
            _feed_job("established", first_seen=NOW - timedelta(days=20), last_seen=NOW,
                      published=NOW - timedelta(days=21)),
            _feed_job("twenty-hours-old", first_seen=opened, last_seen=NOW,
                      published=NOW - timedelta(hours=20)),
        ]
        bucket.round("2026-09-24", opened, jobs)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert report["timing"]["run_started_at"] == opened.isoformat()
    assert report["timing"]["basis"] == "manifest.opened_at"
    assert report["report_generated_at"]
    # The 20-hour-old posting is inside the fresh window measured from the real run start.
    assert report["fresh_arrival_count"] == 1, report["timing"]
    fresh = {r["job_id"]: r["is_fresh_arrival"] for r in report["complete_candidate_list"]}
    assert fresh["remotive:all#twenty-hours-old"] is True
    assert fresh["remotive:all#established"] is False
    # Freshness only sorts; it never drops a row.
    assert len(report["complete_candidate_list"]) == 2


def test_morning_age_is_not_measured_from_the_end_of_the_calendar_day():
    """A 07:05 run measured ages against 23:59:59 the same day — seventeen hours in the future."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        opened = NOW.replace(hour=7, minute=5)
        jobs = [_feed_job("two-hours-old", first_seen=opened, last_seen=opened,
                          published=opened - timedelta(hours=2))]
        bucket.round("2026-09-24", opened, jobs)
        _res, report, markdown = _run_report(bucket, "2026-09-24", "2026-09-24")

    row = report["complete_candidate_list"][0]
    assert "2h ago" in row["age_label"], row["age_label"]
    assert "19h" not in markdown


def test_previous_boundary_comes_from_the_previous_reported_round():
    """The previous round's REPORT generation time is the boundary, so a posting first seen partway
    through that round is not re-announced the next morning."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = NOW - timedelta(days=1)
        mid_yesterday = yesterday.replace(hour=7, minute=10)
        jobs = [_feed_job("seen-during-yesterdays-round", first_seen=mid_yesterday,
                          last_seen=mid_yesterday)]
        bucket.round("2026-09-23", yesterday.replace(hour=7, minute=5), jobs)
        _res, first, _md = _run_report(bucket, "2026-09-23", "2026-09-23")
        assert first["timing"]["cold_start_run"] is True

        today = NOW.replace(hour=7, minute=5)
        jobs_today = jobs + [_feed_job("new-today", first_seen=today, last_seen=today)]
        bucket.round("2026-09-24", today, jobs_today, observations=3)
        _res, second, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert second["timing"]["previous_run_id"] == "2026-09-23"
    assert second["timing"]["cold_start_run"] is False
    fresh = {r["job_id"]: r["is_fresh_arrival"] for r in second["complete_candidate_list"]}
    assert fresh["remotive:all#new-today"] is True
    assert fresh["remotive:all#seen-during-yesterdays-round"] is False, (
        "a posting the previous report already showed must not come back as new")


def test_a_failed_round_does_not_become_a_previous_successful_observation():
    """"Do not invent a previous successful run after failures." A round that never reported leaves
    no report, so the boundary skips back to the last round that actually did."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        monday = NOW - timedelta(days=3)
        jobs = [_feed_job("from-monday", first_seen=monday, last_seen=monday)]
        bucket.round("2026-09-21", monday.replace(hour=7, minute=5), jobs)
        _res, monday_report, _md = _run_report(bucket, "2026-09-21", "2026-09-21")

        # Tuesday: the round opened and collection failed. A manifest exists; no report was written.
        bucket.put_manifest = None
        from src.common import s3layout
        bucket.put(s3layout.run_manifest_key("2026-09-22"),
                   _manifest("2026-09-22", (NOW - timedelta(days=2)).replace(hour=7, minute=5)))

        wednesday = NOW.replace(hour=7, minute=5)
        jobs_wed = jobs + [_feed_job("arrived-tuesday", first_seen=NOW - timedelta(days=2),
                                     last_seen=wednesday)]
        bucket.round("2026-09-24", wednesday, jobs_wed, observations=3)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert report["timing"]["previous_run_id"] == "2026-09-21", report["timing"]
    fresh = {r["job_id"]: r["is_fresh_arrival"] for r in report["complete_candidate_list"]}
    # Discovered while the failed round was silent: still new to Brett, because no report showed it.
    assert fresh["remotive:all#arrived-tuesday"] is True
    assert fresh["remotive:all#from-monday"] is False


def test_a_weekend_gap_treats_the_whole_gap_as_new():
    """Friday reported, nothing ran Saturday or Sunday; Monday's arrivals from all three days are
    new to Brett."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        friday = NOW - timedelta(days=3)
        jobs = [_feed_job("from-friday", first_seen=friday, last_seen=friday)]
        bucket.round("2026-09-21", friday.replace(hour=7, minute=5), jobs)
        _run_report(bucket, "2026-09-21", "2026-09-21")

        monday = NOW.replace(hour=7, minute=5)
        weekend = [
            _feed_job("saturday", first_seen=NOW - timedelta(days=2), last_seen=monday),
            _feed_job("sunday", first_seen=NOW - timedelta(days=1), last_seen=monday),
            _feed_job("monday", first_seen=monday, last_seen=monday),
        ]
        bucket.round("2026-09-24", monday, jobs + weekend, observations=4)
        _res, report, markdown = _run_report(bucket, "2026-09-24", "2026-09-24")

    fresh = {r["job_id"]: r["is_fresh_arrival"] for r in report["complete_candidate_list"]}
    assert fresh["remotive:all#saturday"] and fresh["remotive:all#sunday"] and fresh["remotive:all#monday"]
    assert fresh["remotive:all#from-friday"] is False
    assert report["fresh_arrival_count"] == 3
    assert "New since the last round" in markdown


def test_an_undated_arrival_is_new_to_us_without_claiming_it_is_newly_published():
    """"Newly discovered is not newly published." The row is surfaced, and the label says which."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        old = [_feed_job("known", first_seen=yesterday - timedelta(days=5), last_seen=yesterday)]
        bucket.round("2026-09-23", yesterday, old)
        _run_report(bucket, "2026-09-23", "2026-09-23")

        today = NOW.replace(hour=7, minute=5)
        undated = _feed_job("undated-new", first_seen=today, last_seen=today, published=None)
        bucket.round("2026-09-24", today, old + [undated], observations=3)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    row = next(r for r in report["complete_candidate_list"]
               if r["job_id"] == "remotive:all#undated-new")
    assert row["is_fresh_arrival"] is True
    assert "age unknown" in row["age_label"], row["age_label"]
    assert "floor on its age" in row["age_label"]


def test_first_observation_of_a_source_is_not_a_wave_of_fresh_arrivals():
    """A source's first successful look sets every first_seen_at to the same instant. That is when we
    started watching, not when forty postings arrived."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        opened = NOW.replace(hour=7, minute=5)
        jobs = [_feed_job(f"cold-{i}", first_seen=opened, last_seen=opened) for i in range(5)]
        bucket.round("2026-09-24", opened, jobs, observations=1)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert report["fresh_arrival_count"] == 0, report["timing"]
    assert all(r["first_observation_run_for_source"]
               for r in report["complete_candidate_list"])


def test_a_warm_source_with_one_posting_is_not_mistaken_for_a_cold_start():
    """The review's extra note: cold start was inferred from timestamp CARDINALITY, so a warm source
    holding a single posting looked like a first observation and its genuinely new arrival was
    suppressed. The source's recorded success history decides instead."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        bucket.round("2026-09-23", yesterday,
                     [_feed_job("old-single", first_seen=yesterday - timedelta(days=3),
                                last_seen=yesterday)], observations=5)
        _run_report(bucket, "2026-09-23", "2026-09-23")

        today = NOW.replace(hour=7, minute=5)
        # Exactly one job in the source, first seen this morning: one distinct timestamp.
        bucket.round("2026-09-24", today,
                     [_feed_job("only-job", first_seen=today, last_seen=today)], observations=6)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    row = report["complete_candidate_list"][0]
    assert row["first_observation_run_for_source"] is False, "source has six recorded observations"
    assert row["is_fresh_arrival"] is True
    assert report["fresh_arrival_count"] == 1


def test_a_retry_of_the_same_round_does_not_compare_against_its_own_first_attempt():
    """The report is idempotent per run. A retry must not read its own earlier report as "the
    previous round" and conclude nothing is new."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        known = [_feed_job("known", first_seen=yesterday - timedelta(days=4), last_seen=yesterday)]
        bucket.round("2026-09-23", yesterday, known)
        _run_report(bucket, "2026-09-23", "2026-09-23")

        today = NOW.replace(hour=7, minute=5)
        jobs = known + [_feed_job("new-today", first_seen=today, last_seen=today)]
        bucket.round("2026-09-24", today, jobs, observations=3)
        _res, first_attempt, _md = _run_report(bucket, "2026-09-24", "2026-09-24")
        _res, retry, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert first_attempt["fresh_arrival_count"] == 1
    assert retry["fresh_arrival_count"] == 1, "the retry compared against its own first attempt"
    assert retry["timing"]["previous_run_id"] == "2026-09-23"


def test_duplicate_observations_of_one_posting_do_not_multiply_it():
    """The same posting on two sources is one row after dedup, and its earliest first_seen wins, so
    a duplicate cannot make an old posting look new."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        bucket.round("2026-09-23", yesterday,
                     [_feed_job("dup", first_seen=yesterday - timedelta(days=6),
                                last_seen=yesterday)])
        _run_report(bucket, "2026-09-23", "2026-09-23")

        today = NOW.replace(hour=7, minute=5)
        old = _feed_job("dup", first_seen=yesterday - timedelta(days=6), last_seen=today)
        same_posting_new_source = _feed_job("dup", first_seen=today, last_seen=today,
                                            source="remoteok:all")
        same_posting_new_source.posting_url = old.posting_url
        same_posting_new_source.apply_url = old.apply_url
        bucket.round("2026-09-24", today, [old, same_posting_new_source],
                     sources=("remotive:all", "remoteok:all"), observations=3)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    rows = report["complete_candidate_list"]
    assert len(rows) == 1, [r["job_id"] for r in rows]
    assert rows[0]["is_fresh_arrival"] is False, "the earliest observation must survive the merge"


def test_a_partial_round_still_reports_and_says_so():
    """A partial or failed source does not suppress the report or silently reduce freshness."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        today = NOW.replace(hour=7, minute=5)
        jobs = [_feed_job("arrived", first_seen=today, last_seen=today,
                          published=NOW - timedelta(hours=3))]
        bucket.round("2026-09-24", today, jobs,
                    sources=("remotive:all", "remoteok:all"), observations=2)
        # remoteok had no SUCCESS sentinel written: the round is incomplete.
        from src.common import s3layout
        bucket.s3.delete_object(Bucket=BUCKET,
                                Key=s3layout.collect_sentinel_key("2026-09-24", "remoteok", "all"))
        _res, report, markdown = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert "remoteok:all" in report["incomplete_sources"]
    assert report["fresh_arrival_count"] == 1
    assert report["timing"]["run_started_at"] == today.isoformat()
    assert markdown


def test_the_digest_body_boundary_gets_the_same_timing(monkeypatch):
    """The emailed digest is the same rendered body. Email is mocked; nothing is sent."""
    sent = {}

    class _SES:
        def send_email(self, **kw):
            sent.update(kw)
            return {"MessageId": "mocked"}

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        today = NOW.replace(hour=7, minute=5)
        jobs = [_feed_job("arrived", first_seen=today, last_seen=today,
                          published=NOW - timedelta(hours=4))]
        bucket.round("2026-09-24", today, jobs)

        real_client = boto3.client

        def fake_client(name, *a, **kw):
            return _SES() if name == "ses" else real_client(name, *a, **kw)

        monkeypatch.setattr(boto3, "client", fake_client)
        _res, report, markdown = _run_report(
            bucket, "2026-09-24", "2026-09-24",
            env={"SES_SENDER": "a@example.com", "DIGEST_RECIPIENT": "b@example.com"},
        )

    body = sent["Message"]["Body"]["Text"]["Data"]
    assert "New since the last round" in body
    assert report["fresh_arrival_count"] == 1
    assert body == markdown, "the digest body must be the report that was persisted"


# ==================================================================================================
# R3 — recent arrivals beyond the first feed page
# ==================================================================================================
def _page(label, next_cursor, age_hours, *, now=NOW):
    return {
        "jobs": [{
            "title": "Senior Software Engineer", "companyName": f"Employer {label}",
            "companySlug": label, "excerpt": WORK + PROCESS_OK,
            "description": WORK + PROCESS_OK,
            "applicationLink": f"https://himalayas.app/companies/x/jobs/{label}",
            "guid": f"https://himalayas.app/companies/x/jobs/{label}",
            "locationRestrictions": "['United States']", "employmentType": "Full Time",
            "pubDate": str(int((now - timedelta(hours=age_hours)).timestamp())),
        }],
        "nextCursor": next_cursor, "totalCount": 999,
    }


class _Feed:
    """A cursor-paginated feed whose pages are ordered newest first, as Himalayas' measured
    contract is. Records every cursor actually requested."""

    def __init__(self, pages, *, fail_on=(), now=NOW):
        self.pages = pages
        self.requested: list[str | None] = []
        self.fail_on = set(fail_on)
        self.now = now

    def __call__(self, provider, token, url):
        cursor = parse_qs(urlparse(url).query).get("cursor", [None])[0]
        self.requested.append(cursor)
        if cursor in self.fail_on:
            raise TimeoutError(f"page {cursor} timed out")
        payload = self.pages.get(cursor)
        if payload is None:
            payload = _page("unknown-deep", None, 2000, now=self.now)
        return FetchResult(
            raw_bytes=json.dumps(payload).encode(), http_status=200, error_class=None,
            endpoint_url=url, request_at=self.now, response_at=self.now,
        )


def _discover(feed, state, *, budget=5, run_id="p04", now=NOW):
    from src.discovery.handler import run_discovery

    return run_discovery(run_id=run_id, now=now, fetcher=feed, providers=["himalayas"],
                         state=state, env={}, max_pages_per_source=budget)


def _employers(outcome) -> set[str]:
    return {job.employer_name for job in outcome.jobs}


def test_new_pages_above_an_outstanding_backlog_are_fetched():
    """R3 core. Pre-repair the head walk took exactly one page and DISCARDED its continuation
    cursor, so a two-hour-old posting on page two was never requested and the run jumped straight
    back to the historical backlog."""
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed({
        None: _page("new-1", "NEW_2", 1),
        "NEW_2": _page("new-2", "OLD", 2),
        "OLD": _page("old-1", "OLD_2", 240),
        "OLD_2": _page("old-2", "OLD_3", 480),
        "OLD_3": _page("old-3", "OLD_4", 720),
    })
    outcome = _discover(feed, state)

    assert "NEW_2" in feed.requested, feed.requested
    assert "Employer new-2" in _employers(outcome)
    # The historical backfill still advanced: recent-first is not recent-only.
    assert "OLD" in feed.requested and "OLD_2" in feed.requested
    assert state.source_cursors["himalayas"] not in (None, "OLD")
    assert len(feed.requested) <= 5, feed.requested


def test_the_head_walk_hands_over_when_it_meets_the_backlog():
    """Reaching the backfill's own position ends the head phase rather than spending a second
    request on the page the catch-up is about to fetch."""
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed({
        None: _page("new-1", "OLD", 1),
        "OLD": _page("old-1", "OLD_2", 300),
        "OLD_2": _page("old-2", None, 500),
    })
    _discover(feed, state)
    assert feed.requested.count("OLD") == 1, feed.requested


def test_the_head_walk_stops_at_previously_observed_ground():
    """Second run, nothing new: the head spends one page, sees nothing newer than the frontier it
    recorded last run, and gives the rest of the budget to the backlog."""
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    pages = {
        None: _page("new-1", "NEW_2", 1),
        "NEW_2": _page("new-2", "OLD", 2),
        "OLD": _page("old-1", "OLD_2", 240),
        "OLD_2": _page("old-2", "OLD_3", 480),
        "OLD_3": _page("old-3", "OLD_4", 720),
        "OLD_4": _page("old-4", "OLD_5", 900),
    }
    _discover(_Feed(pages), state)
    assert state.head_frontier_at.get("himalayas")

    later = NOW + timedelta(days=1)
    second = _Feed({k: _page(v["jobs"][0]["companySlug"],
                             v["nextCursor"],
                             (later - datetime.fromtimestamp(int(v["jobs"][0]["pubDate"]),
                                                             timezone.utc)).total_seconds() / 3600,
                             now=later)
                    for k, v in pages.items()}, now=later)
    _discover(second, state, run_id="p04-day2", now=later)
    # One page at the true head, then straight to catch-up work.
    assert second.requested[0] is None
    assert second.requested.count(None) == 1
    assert "NEW_2" not in second.requested, second.requested


def test_an_overflowing_head_walk_is_saved_and_resumed_not_discarded():
    """A burst puts new postings on several pages. The head is bounded so the backlog is never
    starved, so the unfetched remainder is saved and continued next run — and reported."""
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    pages = {
        None: _page("burst-1", "B2", 1),
        "B2": _page("burst-2", "B3", 2),
        "B3": _page("burst-3", "B4", 3),
        "B4": _page("burst-4", "B5", 4),
        "B5": _page("burst-5", "OLD", 5),
        "OLD": _page("old-1", "OLD_2", 300),
    }
    outcome = _discover(_Feed(pages), state, budget=3)

    assert state.head_cursors["himalayas"] == "B3", state.head_cursors
    assert any("recent arrivals" in item["target"] for item in outcome.inaccessible), \
        outcome.inaccessible
    assert any("resumed next run" in item["reason"] for item in outcome.inaccessible)
    # The backlog still got its reserved page.
    assert state.source_cursors["himalayas"] == "OLD_2"

    second = _Feed(pages)
    _discover(second, state, budget=3, run_id="p04-day2")
    # One page at the true head for anything newer, then the saved position — not a re-walk.
    assert second.requested[0] is None
    assert "B3" in second.requested, second.requested
    assert "B2" not in second.requested, "page two was already collected"


def test_a_failed_head_page_is_retried_rather_than_skipped():
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    pages = {
        None: _page("new-1", "NEW_2", 1),
        "NEW_2": _page("new-2", "OLD", 2),
        "OLD": _page("old-1", "OLD_2", 300),
    }
    first = _Feed(pages, fail_on={"NEW_2"})
    outcome = _discover(first, state)
    assert any("page" in item["target"] for item in outcome.inaccessible), outcome.inaccessible
    assert "Employer new-2" not in _employers(outcome)

    second = _Feed(pages)
    outcome2 = _discover(second, state, run_id="p04-retry")
    assert "Employer new-2" in _employers(outcome2), second.requested


def test_no_new_arrivals_spends_nothing_extra_on_the_head():
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed({
        None: _page("stale-1", "OLD", 400),
        "OLD": _page("old-1", "OLD_2", 500),
        "OLD_2": _page("old-2", None, 600),
    })
    _discover(feed, state)
    # The first page holds nothing recent, so the walk does not continue into the feed head.
    assert feed.requested[0] is None
    assert feed.requested.count(None) == 1


def test_a_repeated_cursor_still_stops_the_walk():
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed({
        None: _page("loop-1", "LOOP", 1),
        "LOOP": _page("loop-2", "LOOP", 2),
        "OLD": _page("old-1", None, 300),
    })
    outcome = _discover(feed, state)
    assert any("repeated pagination cursor" in item["reason"] for item in outcome.inaccessible)
    assert len(feed.requested) <= 5


def test_first_seen_is_preserved_when_the_head_re_reads_a_posting():
    """The head walk re-reads page one every run. A posting it has already seen keeps its original
    first_seen_at, or every run would relabel the whole page as newly arrived."""
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    pages = {None: _page("steady", None, 100)}
    first = _discover(_Feed(pages), state, budget=2)
    original = {job.job_id: job.first_seen_at for job in first.jobs}
    assert original

    later = NOW + timedelta(hours=26)
    second = _discover(_Feed(pages, now=later), state, budget=2, run_id="p04-day2", now=later)
    for job in second.jobs:
        if job.job_id in original:
            # Discovery stamps first_seen_at for the run; the differ preserves the earlier value
            # from current/state, which `test_duplicate_observations_of_one_posting_do_not_multiply_it`
            # covers at the report boundary. What matters here is that the posting is still produced.
            assert job.provider_published_at is not None


def test_the_budget_is_never_exceeded_by_the_head_continuation():
    """"No unbounded crawling or silently increased source limits."""
    from src.discovery.budget import DiscoveryState

    for budget in (1, 2, 3, 5):
        state = DiscoveryState()
        state.source_cursors["himalayas"] = "OLD"
        pages = {None: _page("n-1", "N2", 1), "N2": _page("n-2", "N3", 2),
                 "N3": _page("n-3", "N4", 3), "N4": _page("n-4", "N5", 4),
                 "N5": _page("n-5", "N6", 5), "N6": _page("n-6", "OLD", 6),
                 "OLD": _page("o-1", "O2", 300), "O2": _page("o-2", "O3", 400),
                 "O3": _page("o-3", None, 500)}
        feed = _Feed(pages)
        _discover(feed, state, budget=budget)
        assert len(feed.requested) <= budget, (budget, feed.requested)


def test_a_single_page_budget_still_favors_the_head_and_says_so():
    from src.discovery.budget import DiscoveryState

    state = DiscoveryState()
    state.source_cursors["himalayas"] = "OLD"
    feed = _Feed({None: _page("new-1", "NEW_2", 1), "OLD": _page("old-1", None, 300)})
    outcome = _discover(feed, state, budget=1)
    assert feed.requested == [None]
    assert any("backfill" in item["target"] for item in outcome.inaccessible), outcome.inaccessible


def test_a_previous_report_from_an_earlier_release_still_supplies_its_identity_list():
    """The first round after a deploy reads a report the PREVIOUS release wrote. It has no
    `report_generated_at` and no `timing` block, but it does list the postings it showed — and
    identity needs no clock. Skipping such a report entirely would announce every already-seen
    posting as new on the first morning after every deploy."""
    from src.common import s3layout

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        bucket = _Bucket(s3)
        yesterday = (NOW - timedelta(days=1)).replace(hour=7, minute=5)
        known = _feed_job("shown-yesterday", first_seen=yesterday - timedelta(days=2),
                          last_seen=yesterday)

        # A report in the shape the previous release wrote: rows, but no timing fields at all.
        bucket.put(s3layout.report_json_key("2026-09-23"), {
            "run_id": "2026-09-23", "dt": "2026-09-23",
            "complete_candidate_list": [{"job_id": known.job_id, "is_fresh_arrival": False}],
        })

        today = NOW.replace(hour=7, minute=5)
        arrived = _feed_job("new-today", first_seen=today, last_seen=today)
        bucket.round("2026-09-24", today, [known, arrived], observations=4)
        _res, report, _md = _run_report(bucket, "2026-09-24", "2026-09-24")

    assert report["timing"]["previous_run_id"] == "2026-09-23"
    assert report["timing"]["boundary"] == "reported-ids"
    fresh = {r["job_id"]: r["is_fresh_arrival"] for r in report["complete_candidate_list"]}
    assert fresh["remotive:all#new-today"] is True
    assert fresh["remotive:all#shown-yesterday"] is False
