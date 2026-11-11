"""The dedup cleanup pass: same answers, without the all-survivor-pairs scan.

`deduplicate` used to finish with a scan over EVERY ORDERED PAIR of survivors, normalizing both
employer names per pair, in order to remove soft `possible_duplicate_of` links between records whose
requisition ids prove they are different openings. The removal can only ever fire when the id is
ALREADY in the list, so the work was quadratic while the effect was bounded by the existing link set:
on the 2026-09-30 production corpus that was 1,526**2 = 2,328,676 pair comparisons to police FOUR
links, at ~47% of a report runtime with 24% of its budget left.

Two families of test here, because the repair has two obligations that pull in opposite directions:

  SEMANTICS  the repaired pass must produce the same links, removals, ordering and mutations. These
             tests CANNOT fail against the old implementation, because the two are equivalent by
             design — that is the point. They fail against a WRONG repair, and the cases chosen are
             the ones where a plausible rewrite silently diverges.

  SCALING    an operation-count instrument that counts reads of `employer_name`. This is what fails
             against the old scan AND against a cache-only placebo: memoizing `normalize_employer`
             makes each of the 2.3M comparisons cheaper but still has to READ both employer names to
             look the result up, so its read count stays quadratic. Counting `normalize_employer`
             calls alone could not tell those two apart.
"""

from __future__ import annotations

import pytest

from src.common.dedup import deduplicate, normalize_employer
from src.common.models import CanonicalJob, IdKind, SourceKind, VerificationState


# --------------------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------------------
def job(job_id, *, employer="Acme Corp", title="Staff Engineer", location="Remote - US",
        apply_url=None, requisition_id=None, source_id="greenhouse:acme",
        source_kind=SourceKind.ATS_BOARD, links=None, secondary=None,
        verification=VerificationState.FEED_COMPLETE):
    return CanonicalJob(
        source_id=source_id,
        job_id=job_id,
        id_kind=IdKind.NATIVE_ID,
        title=title,
        employer_name=employer,
        canonical_location=location,
        secondary_locations=list(secondary or []),
        apply_url=apply_url if apply_url is not None else f"https://boards.example.com/{job_id}",
        requisition_id=requisition_id,
        source_kind=source_kind,
        verification_state=verification,
        possible_duplicate_of=list(links or []),
    )


# Every field the cleanup has to consult to decide one pair. Counting only `employer_name` was not
# enough: the independent review built a wrong fix that keeps the full Cartesian scan but precomputes
# the employer key once per record, and it read ZERO employer names inside the loop while staying
# visibly quadratic in wall clock. Any per-pair scan must still touch at least one of these.
COUNTED_FIELDS = ("employer_name", "dedup_group_id", "requisition_id", "possible_duplicate_of")

READS: dict[str, int] = {"employer_name": 0, "any": 0}


class CountingJob(CanonicalJob):
    """Counts reads of the fields a pair decision needs.

    Known limit, stated rather than discovered later: this hooks Python attribute access only.
    `job.__dict__["employer_name"]`, `object.__getattribute__(...)` and `model_dump()` (pydantic-core
    serialises in Rust and never calls this) all read the value without being counted. An
    implementation that precomputed EVERY one of these fields into its own index before scanning
    would therefore still read as linear here — which is why
    `test_wall_clock_growth_backs_up_the_operation_count` exists and cannot be gamed that way.
    """

    def __getattribute__(self, name):
        if name in COUNTED_FIELDS:
            READS["any"] += 1
            if name == "employer_name":
                READS["employer_name"] += 1
        return super().__getattribute__(name)


def counting(**kwargs):
    return CountingJob.model_validate(job(**kwargs).model_dump())


# --------------------------------------------------------------------------------------------------
# SEMANTICS — what a wrong repair breaks
# --------------------------------------------------------------------------------------------------
def test_a_link_between_proven_different_requisitions_is_removed():
    """The cleanup's whole purpose. Two rows, one employer, same title and location, different
    requisition ids — soft-linked by the loose soft key, then unlinked by the cleanup."""
    a = job("A", requisition_id="27523", apply_url="https://boards.example.com/a")
    b = job("B", requisition_id="27535", apply_url="https://boards.example.com/b")

    kept, report = deduplicate([a, b])

    assert len(kept) == 2
    assert a.possible_duplicate_of == []
    assert b.possible_duplicate_of == []
    assert report.to_json()["links_blocked_as_distinct_requisitions"] == 1


def test_a_link_survives_when_only_one_side_has_a_requisition_id():
    """Missing ids are not proof of difference. Removing here would hide a real possible duplicate."""
    a = job("A", requisition_id="27523", apply_url="https://boards.example.com/a")
    b = job("B", requisition_id=None, apply_url="https://boards.example.com/b")

    deduplicate([a, b])

    assert b.job_id in a.possible_duplicate_of
    assert a.job_id in b.possible_duplicate_of


def test_a_link_survives_when_the_requisition_ids_agree():
    a = job("A", requisition_id="27523", apply_url="https://boards.example.com/a")
    b = job("B", requisition_id="27523", apply_url="https://boards.example.com/b")

    deduplicate([a, b])

    assert b.job_id in a.possible_duplicate_of
    assert a.job_id in b.possible_duplicate_of


def test_a_stale_link_already_on_the_input_is_cleaned():
    """The projection is hand-editable and callers may pass records carrying links from an earlier
    round, so the cleanup cannot assume it only sees links the soft pass just made. A link-driven
    rewrite that walked only freshly-created links would miss this."""
    a = job("A", requisition_id="27523", apply_url="https://x.example.com/a", links=["Z"])
    z = job("Z", requisition_id="99999", apply_url="https://y.example.com/z",
            title="Totally Different Role")

    deduplicate([a, z])

    assert "Z" not in a.possible_duplicate_of, "a stale cross-requisition link must be removed"


def test_a_stale_link_to_a_job_that_is_not_present_is_left_alone():
    """No survivor to compare against means no proof of difference, so nothing is removed."""
    a = job("A", requisition_id="27523", links=["GHOST-NOT-IN-CORPUS"])

    deduplicate([a])

    assert a.possible_duplicate_of == ["GHOST-NOT-IN-CORPUS"]


def test_only_one_occurrence_is_removed_per_pair():
    """The old pair scan visited each (job, other) pair once and `list.remove` takes the first match,
    so a list carrying the same id twice kept its second copy. A rewrite that iterates the link list
    and removes every match changes behavior on exactly this input."""
    a = job("A", requisition_id="27523", apply_url="https://x.example.com/a", links=["B", "B"])
    b = job("B", requisition_id="27535", apply_url="https://y.example.com/b",
            title="Totally Different Role")

    deduplicate([a, b])

    assert a.possible_duplicate_of == ["B"], "exactly one occurrence is removed, as before"


def test_three_survivors_sharing_one_job_id_do_not_crash_the_removal():
    """The membership re-check before `.remove()` is load-bearing, and nothing tested it.

    Found by the independent review, which removed that one line and watched all 659 tests stay
    green while the code raised `ValueError: list.remove(x): x not in list` on this shape. Cross-
    source `job_id` collision is exactly the domain this module exists for, so the shape is real.

    The link list names `DUP` once. Three survivors carry that id: one at a different employer
    (skipped on the employer guard) and two at the same employer with differing requisition ids.
    The first match removes the single occurrence; the second match must find it already gone and
    leave the list alone rather than raising.
    """
    a = job("A", employer="Acme Corp", requisition_id="1",
            apply_url="https://x.example.com/a", links=["DUP"])
    other_employer = job("DUP", employer="Globex Inc", requisition_id="2",
                         apply_url="https://y.example.com/b", title="Other")
    same_1 = job("DUP", employer="Acme Corp", requisition_id="3",
                 apply_url="https://z.example.com/c", title="Other Two")
    same_2 = job("DUP", employer="Acme Corp", requisition_id="4",
                 apply_url="https://w.example.com/d", title="Other Three")

    kept, _ = deduplicate([a, other_employer, same_1, same_2])

    assert len(kept) == 4
    assert a.possible_duplicate_of == [], "the single occurrence is removed exactly once"


def test_two_records_sharing_a_dedup_group_are_never_unlinked():
    """Same canonical apply target means the same posting; the hard tier already merged them, and the
    cleanup's group-id guard is what keeps it from second-guessing that."""
    a = job("A", requisition_id="27523", apply_url="https://boards.example.com/same")
    b = job("B", requisition_id="27535", apply_url="https://boards.example.com/same")

    kept, _ = deduplicate([a, b])

    assert len(kept) == 1, "identical apply target is a hard merge"


def test_records_with_no_group_id_are_skipped_exactly_as_before():
    """Two records with no hard key both carry dedup_group_id None. `None == None` compared equal, so
    the old scan SKIPPED that pair — a rewrite using a truthiness guard would start unlinking them."""
    a = job("A", requisition_id="27523", apply_url="", links=["B"])
    b = job("B", requisition_id="27535", apply_url="", links=["A"])
    a.posting_url = ""
    b.posting_url = ""

    assert a.dedup_group_id is None and b.dedup_group_id is None
    deduplicate([a, b])

    assert a.possible_duplicate_of == ["B"], "both group ids None compares equal and is skipped"
    assert b.possible_duplicate_of == ["A"]


def test_different_employers_are_never_unlinked_by_this_pass():
    a = job("A", employer="Acme Corp", requisition_id="1", apply_url="https://x.example.com/a",
            links=["B"])
    b = job("B", employer="Globex Inc", requisition_id="2", apply_url="https://y.example.com/b")

    deduplicate([a, b])

    assert "B" in a.possible_duplicate_of


def test_employer_suffixes_fold_so_the_pass_still_recognises_one_employer():
    """`Acme Corp` and `Acme, Inc.` normalize alike, which is what makes them comparable at all."""
    assert normalize_employer("Acme Corp") == normalize_employer("Acme, Inc.") == "acme"
    a = job("A", employer="Acme Corp", requisition_id="1", apply_url="https://x.example.com/a")
    b = job("B", employer="Acme, Inc.", requisition_id="2", apply_url="https://y.example.com/b")

    deduplicate([a, b])

    assert a.possible_duplicate_of == []


def test_empty_employer_names_fall_back_to_source_id_without_crashing():
    a = job("A", employer="", requisition_id="1", apply_url="https://x.example.com/a")
    b = job("B", employer="", requisition_id="2", apply_url="https://y.example.com/b")

    kept, _ = deduplicate([a, b])

    assert len(kept) == 2


def test_different_eligibility_variants_block_the_link_before_the_cleanup_sees_it():
    a = job("A", apply_url="https://x.example.com/a", secondary=["Canada"])
    b = job("B", apply_url="https://y.example.com/b", secondary=["Germany"])

    _kept, report = deduplicate([a, b])

    assert report.to_json()["links_blocked_as_distinct_requisitions"] == 1
    assert a.possible_duplicate_of == []


def test_two_employer_owned_boards_with_different_apply_hosts_are_blocked():
    # `apply_host` is a stored field rather than one derived from `apply_url`, so a fixture that only
    # sets the URL leaves it None and the host guard never fires. Set it the way the collectors do.
    a = job("A", source_id="greenhouse:acme", apply_url="https://boards.greenhouse.io/acme/1")
    b = job("B", source_id="ashby:acme", apply_url="https://jobs.ashbyhq.com/acme/2")
    a.apply_host = "boards.greenhouse.io"
    b.apply_host = "jobs.ashbyhq.com"

    _kept, report = deduplicate([a, b])

    assert any("apply hosts" in r for r in report.blocked_links)
    assert a.possible_duplicate_of == [] and b.possible_duplicate_of == []


def test_provenance_and_enrichment_survive_a_hard_merge():
    a = job("A", apply_url="https://boards.example.com/same", source_id="remoteok:feed",
            source_kind=SourceKind.DISCOVERY_FEED)
    a.description_text = "the full description"
    b = job("B", apply_url="https://boards.example.com/same", source_id="greenhouse:acme",
            source_kind=SourceKind.ATS_BOARD)

    kept, report = deduplicate([a, b])

    assert len(kept) == 1
    winner = kept[0]
    assert winner.job_id == "B", "the employer's own board outranks a feed"
    assert winner.description_text == "the full description", "loser's description is not lost"
    assert {p.source_id for p in winner.provenance} == {"remoteok:feed", "greenhouse:acme"}
    assert report.to_json()["records_absorbed_into_a_survivor"] == 1


def test_running_dedup_twice_is_stable():
    a = job("A", requisition_id="27523", apply_url="https://x.example.com/a")
    b = job("B", requisition_id="27535", apply_url="https://y.example.com/b")

    kept_once, _ = deduplicate([a, b])
    before = [(j.job_id, list(j.possible_duplicate_of), j.dedup_group_id) for j in kept_once]
    kept_twice, _ = deduplicate(kept_once)
    after = [(j.job_id, list(j.possible_duplicate_of), j.dedup_group_id) for j in kept_twice]

    assert before == after


# --------------------------------------------------------------------------------------------------
# SCALING — the instrument, and what it discriminates
# --------------------------------------------------------------------------------------------------
def _old_global_cleanup(kept):
    """The pre-repair pass, verbatim in shape: every ORDERED PAIR of survivors."""
    for a in kept:
        for b in kept:
            if a is b or a.dedup_group_id == b.dedup_group_id:
                continue
            if normalize_employer(a.employer_name) != normalize_employer(b.employer_name):
                continue
            if a.requisition_id and b.requisition_id and (
                a.requisition_id != b.requisition_id
            ) and b.job_id in a.possible_duplicate_of:
                a.possible_duplicate_of.remove(b.job_id)


def _cache_only_cleanup(kept):
    """The placebo the packet names: memoize the normalization, keep the Cartesian scan."""
    cache: dict[str, str] = {}

    def cached(name):
        if name not in cache:
            cache[name] = normalize_employer(name)
        return cache[name]

    for a in kept:
        for b in kept:
            if a is b or a.dedup_group_id == b.dedup_group_id:
                continue
            if cached(a.employer_name) != cached(b.employer_name):
                continue
            if a.requisition_id and b.requisition_id and (
                a.requisition_id != b.requisition_id
            ) and b.job_id in a.possible_duplicate_of:
                a.possible_duplicate_of.remove(b.job_id)


def _sparse(n):
    """n distinct employers, distinct apply targets. No soft links at all."""
    return [counting(job_id=f"J{i}", employer=f"Employer {i}", requisition_id=f"R{i}",
                     apply_url=f"https://e{i}.example.com/{i}") for i in range(n)]


def _one_employer_distinct_keys(n):
    """n jobs at ONE employer, each a genuinely different opening. The cleanup's real workload."""
    return [counting(job_id=f"J{i}", employer="Acme Corp", title=f"Engineer Level {i}",
                     requisition_id=f"R{i}", apply_url=f"https://acme.example.com/{i}")
            for i in range(n)]


def _dense_bucket(n):
    """n jobs sharing employer+title+location with NO requisition ids: every pair legitimately
    soft-links. The output here is inherently quadratic and must not be called linear."""
    return [counting(job_id=f"J{i}", employer="Acme Corp", title="Staff Engineer",
                     requisition_id=None, apply_url=f"https://acme.example.com/{i}")
            for i in range(n)]


def _precompute_then_scan_cleanup(kept):
    """The strongest 'wrong fix' the independent review could build.

    It keeps the whole Cartesian scan and only hoists the normalization into an id()-keyed index —
    the same trick the shipped code uses, applied without removing the scan. It reads no employer
    name inside the loop, so an employer-name-only instrument calls it linear while it is plainly
    quadratic. It is here so the suite fails against it.
    """
    key = {id(j): normalize_employer(j.employer_name) for j in kept}
    for a in kept:
        for b in kept:
            if a is b or a.dedup_group_id == b.dedup_group_id:
                continue
            if key[id(a)] != key[id(b)]:
                continue
            if a.requisition_id and b.requisition_id and (
                a.requisition_id != b.requisition_id
            ) and b.job_id in a.possible_duplicate_of:
                a.possible_duplicate_of.remove(b.job_id)


def _reads_for(builder, n):
    READS["employer_name"] = 0
    deduplicate(builder(n))
    return READS["employer_name"]


def _any_reads_for(builder, n):
    READS["any"] = 0
    deduplicate(builder(n))
    return READS["any"]


@pytest.mark.parametrize("builder,label", [
    (_sparse, "sparse distinct employers"),
    (_one_employer_distinct_keys, "many jobs at one employer, distinct keys"),
])
def test_employer_name_reads_grow_linearly_not_quadratically(builder, label):
    """Quadrupling the input must not multiply the reads by ~16.

    This is the test that fails against the old scan and against the cache-only placebo: both have to
    read two employer names per ordered pair to make their comparison at all.
    """
    small = _reads_for(builder, 60)
    large = _reads_for(builder, 240)

    growth = large / small
    assert growth < 6, (
        f"{label}: 4x the input grew employer_name reads {growth:.1f}x, which is superlinear "
        f"({small} -> {large})"
    )


@pytest.mark.parametrize("cleanup,name", [
    (_old_global_cleanup, "old global pair scan"),
    (_cache_only_cleanup, "cache-only placebo"),
])
def test_the_instrument_discriminates_the_old_scan_and_the_cache_only_placebo(cleanup, name):
    """Both rejected implementations are quadratic in employer_name reads; the shipped one is not.

    Without this, 'the tests pass' would say nothing about whether the scan was actually removed.
    """
    survivors = _one_employer_distinct_keys(120)
    READS["employer_name"] = 0
    deduplicate(survivors)
    shipped = READS["employer_name"]

    READS["employer_name"] = 0
    cleanup(survivors)
    rejected = READS["employer_name"]

    n = len(survivors)
    assert rejected > n * n / 2, (
        f"{name} should read ~2n^2={2 * n * n} employer names, saw {rejected}"
    )
    assert shipped < rejected / 10, (
        f"shipped implementation ({shipped}) must be far below {name} ({rejected})"
    )


def test_a_dense_bucket_is_reported_as_inherently_pairwise_not_as_linear():
    """Honesty guard. Where every pair legitimately links, the OUTPUT is quadratic and no repair can
    make it linear. What must still be true is that the cleanup adds no *further* global scan: reads
    stay O(n) even while links are O(n^2)."""
    small_n, large_n = 30, 120

    READS["employer_name"] = 0
    small = _dense_bucket(small_n)
    _kept, small_report = deduplicate(small)
    small_reads = READS["employer_name"]

    READS["employer_name"] = 0
    large = _dense_bucket(large_n)
    _kept, large_report = deduplicate(large)
    large_reads = READS["employer_name"]

    # The links really are quadratic, and we say so.
    assert small_report.soft_links == small_n * (small_n - 1) // 2
    assert large_report.soft_links == large_n * (large_n - 1) // 2

    # The employer-name reads are not.
    assert large_reads / small_reads < 6, (
        f"reads grew {large_reads / small_reads:.1f}x for a 4x input, so a global scan remains "
        f"({small_reads} -> {large_reads})"
    )


@pytest.mark.parametrize("cleanup,name", [
    (_old_global_cleanup, "old global pair scan"),
    (_cache_only_cleanup, "cache-only placebo"),
    (_precompute_then_scan_cleanup, "precompute-then-scan placebo"),
])
def test_every_per_pair_scan_is_caught_by_the_broadened_counter(cleanup, name):
    """The employer-name counter misses the third variant. Counting every field a pair decision
    needs does not: a Cartesian scan has to read `dedup_group_id` on both sides before it can skip,
    and there is nowhere else for that read to come from."""
    survivors = _one_employer_distinct_keys(120)

    READS["any"] = 0
    deduplicate(survivors)
    shipped = READS["any"]

    READS["any"] = 0
    cleanup(survivors)
    rejected = READS["any"]

    n = len(survivors)
    assert rejected > n * n / 2, f"{name} should be quadratic in counted reads, saw {rejected}"
    assert shipped < rejected / 10, f"shipped ({shipped}) must be far below {name} ({rejected})"


@pytest.mark.parametrize("builder,label", [
    (_sparse, "sparse distinct employers"),
    (_one_employer_distinct_keys, "many jobs at one employer, distinct keys"),
])
def test_all_counted_field_reads_grow_linearly(builder, label):
    small = _any_reads_for(builder, 60)
    large = _any_reads_for(builder, 240)

    growth = large / small
    assert growth < 6, (
        f"{label}: 4x the input grew counted reads {growth:.1f}x ({small} -> {large})"
    )


def test_wall_clock_growth_backs_up_the_operation_count():
    """The instrument of last resort, and the only one a precomputing implementation cannot dodge.

    Thresholds are deliberately loose because wall clock is noisy: quadratic growth over a 4x input
    is ~16x, linear is ~4x, and the bar here is 8x. That is wide enough not to flake and narrow
    enough that no quadratic implementation passes — the review's precompute-then-scan variant
    measured ~217x over a 16x input.
    """
    import time

    def elapsed(n):
        jobs = _one_employer_distinct_keys(n)
        start = time.perf_counter()
        deduplicate(jobs)
        return time.perf_counter() - start

    elapsed(200)  # warm import/JIT-ish paths so the first sample is not the outlier
    small = min(elapsed(200) for _ in range(3))
    large = min(elapsed(800) for _ in range(3))

    growth = large / max(small, 1e-9)
    assert growth < 8, (
        f"4x the input took {growth:.1f}x the time ({small:.4f}s -> {large:.4f}s); "
        f"a quadratic scan would be ~16x"
    )


def test_the_real_corpus_shape_does_almost_no_cleanup_work():
    """The measured production shape: ~1,500 survivors, a handful of links. The cleanup should touch
    the links, not the pairs."""
    jobs = _one_employer_distinct_keys(400)
    READS["employer_name"] = 0
    deduplicate(jobs)

    # One read per record for the precomputed key, plus the soft-key pass. Comfortably under the
    # 320,000 that an all-pairs scan over 400 survivors would need.
    assert READS["employer_name"] < 4000, READS["employer_name"]
