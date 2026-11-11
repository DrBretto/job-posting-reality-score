"""Live acceptance check: did discovery's postings actually reach the morning report?

Why the obvious check does not work
-----------------------------------
P07's handoff proposed reading a nonempty live view, coverage metadata and the report's
exclusion/below-fit counts. P07's review refuted that: every one of those numbers can come entirely
from the 15 monitored Greenhouse boards, so all three can look healthy on a morning when not one
discovered posting was consumed. A count that cannot distinguish the two populations cannot verify an
integration between them.

Its employer-absence check had the same shape of flaw: it compared a discovery source id against the
ATS source ids. Those differ by construction — `himalayas:all` is not `greenhouse:machinifyinc`
whatever employer the posting names — so it would have reported success for a posting from a company
already in the registry. The question is about the EMPLOYER, so this reconciles employer identity
against `config/companies.yaml`.

What it does instead
--------------------
It takes discovery's own stored postings as the INPUT set, and reconciles every one of those
identities to a disposition in the report:

    retained            a row in `complete_candidate_list`
    excluded            a row in `policy_exclusions`, with the rule that fired
    absorbed            merged into another row as a duplicate, traceable in that row's provenance
    consumed-unlisted   named in the report's own `below_fit_threshold_job_ids`
    pending publication durably captured, not yet published — owed, and named in the receipt
    observed-later      first observed in a run AFTER this report's, so this report could not have
                        consumed it; the two artifacts are not the same population
    NOT CONSUMED        none of the above: the input did not reach the consumer

Every one of those comes from evidence the CONSUMER states. P08's version inferred the
`consumed-unlisted` case instead: it treated an employer's presence in `previously_unseen_employers`
as proof that each posting from that employer had been consumed. Its review reproduced what that
costs — a stored job from the same employer as a consumed one, absent from a report with ZERO
below-fit jobs, was labelled "below the fit threshold" and the check exited 0. An employer-name
match is not evidence about a posting, so the report now states the consumed identities and the
below-fit identities directly, and this script reads them.

    ACCEPTANCE_MET            every input reconciled, and a registry-absent employer's posting is
                              retained in the human report
    INTEGRATION_OK            every input reconciled; none qualified today (a legitimate zero)
    RECONCILIATION_INCOMPLETE some inputs were consumed and at least one reached no disposition.
                              A positive open-market witness can still be true and is printed, but
                              the integration is NOT clean and this does not exit 0
    MISSING_INGESTION         discovery postings exist and none reached the consumer (the defect)
    PENDING_PUBLICATION       the only observations on record are owed, not yet published
    INPUTS_NOT_COHERENT       the live view holds postings first observed after this report's run,
                              so it is not the population that report consumed; re-pair the inputs
    EVIDENCE_UNAVAILABLE      the report predates per-identity consumption evidence, so a
                              reconciliation cannot be made. Absent evidence, not an honest zero
    NO_INPUT                  discovery stored nothing to consume; cannot conclude either way

A zero is an allowed result. It must be recorded with the source-specific evidence this prints, not
re-run until a pleasing sample appears.

Employer identity
-----------------
An employer whose identity cannot be established is labelled UNKNOWN-REVIEW-NEEDED and never counted
toward the acceptance claim. Absence of a name is not evidence of a new employer.

Usage
-----
    python scripts/inspect_discovery_integration.py \
        --report <daily_report.json> \
        --live <live_jobs.json> [--live <live_jobs.json> ...] \
        [--coverage <coverage.json>] [--registry config/companies.yaml]

Reads local files only. It makes no AWS call, so fetching the inputs is a separate, explicitly
read-only step; DEPLOYMENT_HANDOFF.md gives those exact commands. Exit code 0 only on
ACCEPTANCE_MET or INTEGRATION_OK, 1 on MISSING_INGESTION and RECONCILIATION_INCOMPLETE, 2 on the
cases where this check cannot conclude (NO_INPUT, PENDING_PUBLICATION, INPUTS_NOT_COHERENT,
EVIDENCE_UNAVAILABLE).
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.common.normalize import normalize_employer  # noqa: E402

UNKNOWN = "UNKNOWN-REVIEW-NEEDED"


def _load(path: pathlib.Path):
    return json.loads(path.read_text())


def _registry_keys(path: pathlib.Path) -> tuple[set[str], set[str]]:
    """Employer identities the system already monitors, as normalized names and as board tokens."""
    import yaml

    doc = yaml.safe_load(path.read_text()) or {}
    names: set[str] = set()
    tokens: set[str] = set()
    for row in doc.get("companies", []) or []:
        token = str(row.get("board_token") or "")
        slug = str(row.get("company_slug") or "")
        if token:
            tokens.add(token.lower())
            names.add(normalize_employer(token.replace("-", " ")))
        if slug:
            tokens.add(slug.lower())
            names.add(normalize_employer(slug.replace("-", " ")))
    return {n for n in names if n}, tokens


def _in_registry(employer: str, names: set[str], tokens: set[str]) -> bool:
    key = normalize_employer(employer)
    if not key:
        return False
    if key in names:
        return True
    slug = key.replace(" ", "-")
    return slug in tokens or key.replace(" ", "") in {t.replace("-", "") for t in tokens}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=pathlib.Path)
    parser.add_argument("--live", action="append", default=[], type=pathlib.Path)
    parser.add_argument("--coverage", type=pathlib.Path)
    parser.add_argument(
        "--registry", type=pathlib.Path, default=pathlib.Path("config/companies.yaml")
    )
    args = parser.parse_args(argv)

    report = _load(args.report)
    names, tokens = _registry_keys(args.registry)

    # ---- INPUT side: what discovery stored, by identity ------------------------------------------
    inputs: dict[str, dict] = {}
    for path in args.live:
        view = _load(path)
        for job_id, record in (view.get("jobs") or {}).items():
            job = record.get("job") or {}
            observed = record.get("observed_run_ids") or []
            inputs[job_id] = {
                "source_id": view.get("source_id") or job.get("source_id"),
                "employer": job.get("employer_name") or "",
                "title": job.get("title") or "",
                "last_seen_run_id": record.get("last_seen_run_id"),
                "observed_run_ids": observed,
                # The earliest run that actually observed this posting. If that is later than the
                # report's run, the report could not have consumed it and its absence says nothing
                # about the integration — it says the two artifacts were fetched at different times.
                "first_observed_run_id": (
                    min(observed) if observed
                    else record.get("first_seen_run_id") or record.get("last_seen_run_id")
                ),
            }

    # ---- owed publication: captured, not yet consumable -----------------------------------------
    coverage_doc = _load(args.coverage) if args.coverage else {}
    pending: dict[str, str] = {}
    owed = (coverage_doc.get("pending_publication")
            or (report.get("coverage") or {}).get("pending_publication") or {})
    for provider, batches in owed.items():
        for batch in batches:
            for job_id in batch.get("job_ids", []):
                pending[job_id] = f"{provider} run {batch.get('run_id')}"

    # ---- OUTPUT side: every disposition the report expresses -------------------------------------
    retained = {row["job_id"]: row for row in report.get("complete_candidate_list", [])}
    excluded = {row["job_id"]: row for row in report.get("policy_exclusions", [])}
    absorbed: dict[str, str] = {}
    for row in list(retained.values()) + list(excluded.values()):
        for stamp in row.get("provenance") or []:
            absorbed.setdefault(stamp.get("job_id", ""), row["job_id"])
        for other in row.get("possible_duplicate_of") or []:
            absorbed.setdefault(other, row["job_id"])
    absorbed.pop("", None)

    discovery_rows = [
        row for row in list(retained.values()) + list(excluded.values())
        if row.get("source_kind") == "DISCOVERY_FEED"
    ]
    unseen_employers = (report.get("coverage") or {}).get("previously_unseen_employers") or []
    # The consumer's own per-identity statement. `None` means this report predates that evidence —
    # a different thing from a report that consumed nothing, and it is never treated as one.
    consumed_ids = report.get("consumed_job_ids")
    below_fit_ids = set(report.get("below_fit_threshold_job_ids") or [])
    evidence_available = consumed_ids is not None
    consumed_ids = set(consumed_ids or [])
    report_run_id = str(report.get("run_id") or "")

    print("=== discovery integration inspection ===")
    print(f"report: {args.report}  run {report.get('run_id')}  dt {report.get('dt')}")
    print(f"registry monitors {len(tokens)} board/slug identit(ies)")
    print()

    # ---- reconciliation, identity by identity ---------------------------------------------------
    print("--- every stored discovery identity, reconciled to a disposition ---")
    buckets: dict[str, list[str]] = {}
    acceptance: list[dict] = []
    review_needed: list[str] = []
    for job_id in sorted(inputs):
        info = inputs[job_id]
        employer = info["employer"].strip()
        if not employer:
            employer_label = UNKNOWN
            review_needed.append(job_id)
        else:
            employer_label = employer
        if job_id in retained:
            disposition = "retained"
            detail = f"fit {retained[job_id].get('fit_band')}"
        elif job_id in excluded:
            rules = [
                hit.get("rule_id")
                for hit in ((excluded[job_id].get("screen_detail") or {}).get("exclusions") or [])
            ]
            disposition = "excluded"
            detail = f"rule(s) {', '.join(filter(None, rules)) or 'unstated'}"
        elif job_id in absorbed:
            disposition = "absorbed"
            detail = f"merged into {absorbed[job_id]}"
        elif job_id in pending:
            disposition = "pending publication"
            detail = pending[job_id]
        elif job_id in below_fit_ids:
            # The report itself names this identity as scored and below the fit threshold. Stated by
            # the consumer, never inferred here from the employer's name appearing somewhere else.
            disposition = "consumed-unlisted"
            detail = "the report names this id in below_fit_threshold_job_ids"
        elif job_id in consumed_ids:
            # Consumed, but in no readable section and not named below-fit. The report accounts for
            # it, yet does not say where it went; that gap is real and is reported as one.
            disposition = "consumed-unexplained"
            detail = "in consumed_job_ids but in no section and not named below the fit threshold"
        elif (
            report_run_id
            and info["first_observed_run_id"]
            and str(info["first_observed_run_id"]) > report_run_id
        ):
            disposition = "observed-later"
            detail = (
                f"first observed in run {info['first_observed_run_id']}, after this report's run "
                f"{report_run_id}; this report could not have consumed it"
            )
        elif not evidence_available:
            disposition = "UNRECONCILABLE"
            detail = (
                "this report carries no consumed_job_ids, so whether it consumed this posting "
                "cannot be established from the artifact"
            )
        else:
            disposition = "NOT CONSUMED"
            detail = "absent from the report's own consumed_job_ids"
        buckets.setdefault(disposition, []).append(job_id)
        print(f"  {disposition:20s} {job_id}")
        print(f"  {'':20s}   employer {employer_label} — {detail}")

        if disposition == "retained" and employer:
            if not _in_registry(employer, names, tokens):
                acceptance.append({"job_id": job_id, "employer": employer,
                                   "title": info["title"]})
    if not inputs:
        print("  (discovery has no stored postings for the feeds supplied)")
    print()

    # ---- arithmetic that must close --------------------------------------------------------------
    print("--- reconciliation totals ---")
    for disposition in sorted(buckets):
        print(f"  {disposition}: {len(buckets[disposition])}")
    print(f"  stored discovery identities: {len(inputs)}")
    print(f"  discovery-origin rows in the report: {len(discovery_rows)}")
    print(f"  report below-fit-threshold count (both populations): "
          f"{report.get('below_fit_threshold_count')}")
    print(f"  report states {len(consumed_ids)} consumed identit(ies)"
          if evidence_available else
          "  report states NO per-identity consumption evidence (predates consumed_job_ids)")
    # Everything the report does not account for. An unexplained identity keeps this list non-empty
    # whether or not other inputs were consumed, which is the whole repair: a mixed successful and
    # missing population is not a healthy one.
    unreconciled = (
        buckets.get("NOT CONSUMED", [])
        + buckets.get("consumed-unexplained", [])
        + buckets.get("UNRECONCILABLE", [])
    )
    incoherent = buckets.get("observed-later", [])
    print()

    if review_needed:
        print(f"--- {len(review_needed)} posting(s) carry no establishable employer identity ---")
        for job_id in review_needed:
            print(f"  {UNKNOWN}: {job_id}")
        print("  These are excluded from the acceptance claim; absence of a name is not evidence")
        print("  of a previously unseen employer.")
        print()

    if pending:
        print(f"--- {len(pending)} posting(s) are captured but not yet published ---")
        for job_id, where in sorted(pending.items()):
            print(f"  owed: {job_id} ({where})")
        print("  These are NOT a failed integration and NOT a thin day. They are owed, and the next")
        print("  discovery round publishes them without the feed having to return them again.")
        print()

    # ---- the verdict, with the three cases kept apart --------------------------------------------
    # Consumption is decided by identities the report accounts for, never by an employer name
    # appearing in a coverage list: that list cannot distinguish one posting from another.
    consumed = bool(
        discovery_rows or buckets.get("absorbed") or buckets.get("consumed-unlisted")
        or (consumed_ids & set(inputs))
    )
    print("--- verdict ---")
    if incoherent:
        print(f"INPUTS_NOT_COHERENT — {len(incoherent)} stored posting(s) were first observed in a")
        print(f"  run after this report's ({report_run_id}), so this live view is not the population")
        print("  that report consumed. Nothing can be concluded from the pairing; fetch the view and")
        print("  the report for the same run and re-run this check.")
        for job_id in incoherent[:10]:
            print(f"    observed later: {job_id} (first observed "
                  f"{inputs[job_id]['first_observed_run_id']})")
        return 2
    if inputs and not evidence_available:
        print("EVIDENCE_UNAVAILABLE — this report carries no per-identity consumption evidence, so")
        print("  no stored posting can be reconciled to a disposition. This is ABSENT EVIDENCE, not")
        print("  an honest zero and not a defect: re-run the check against a report written by the")
        print("  current consumer, which states `consumed_job_ids`.")
        return 2
    if not inputs and not pending:
        print("NO_INPUT — discovery stored no postings for these feeds, so consumption cannot be")
        print("  observed either way. This is not a pass and not a failure; check the coverage")
        print("  receipt for whether the feeds were reachable at all.")
        return 2
    if pending and not consumed and not unreconciled:
        print("PENDING_PUBLICATION — the only discovery observations on record are owed, not yet")
        print("  published, so there is nothing for the report to have consumed. This is neither a")
        print("  thin day nor a broken consumer; re-run this check after the next discovery round.")
        return 2
    if unreconciled and not consumed:
        print(f"MISSING_INGESTION — {len(unreconciled)} stored posting(s) reached no disposition and")
        print("  nothing in the report evidences a consumed discovery posting. The consumer")
        print("  connection is the thing to check, not the feeds.")
        for job_id in unreconciled[:10]:
            print(f"    unconsumed: {job_id}")
        return 1
    if unreconciled:
        # Mixed: some inputs were consumed and at least one was not. P08's branch fired only when
        # NOTHING was consumed, so exactly this case passed. A positive witness does not make the
        # reconciliation complete, and an incomplete reconciliation does not exit 0.
        print(f"RECONCILIATION_INCOMPLETE — {len(unreconciled)} stored posting(s) reached no")
        print("  disposition, while others were consumed. The integration is partial: this is not")
        print("  a clean run and not a legitimate zero-fit day.")
        for job_id in unreconciled[:10]:
            print(f"    unexplained: {job_id} — {inputs[job_id]['employer'] or UNKNOWN}")
        if acceptance:
            print()
            print(f"  Separately true: {len(acceptance)} retained posting(s) from employer(s)")
            print("  absent from the registry. That witness stands on its own and is not withdrawn")
            print("  by the gap above, but it does not close the reconciliation.")
            for row in acceptance:
                print(f"    {row['employer']} — {row['title']} ({row['job_id']})")
        return 1
    if acceptance:
        print(f"ACCEPTANCE_MET — {len(acceptance)} retained posting(s) from employer(s) absent from")
        print("  the registry. This is the live positive condition, and every stored posting is")
        print("  reconciled to a disposition the report itself states.")
        for row in acceptance:
            print(f"    {row['employer']} — {row['title']} ({row['job_id']})")
        return 0
    retained_discovery = [
        row for row in retained.values() if row.get("source_kind") == "DISCOVERY_FEED"
    ]
    if retained_discovery:
        print(f"INTEGRATION_OK — {len(retained_discovery)} discovery posting(s) reached the shortlist,")
        print("  but every one names an employer already in the registry, so the OPEN-MARKET")
        print("  condition specifically is not evidenced. Monitoring could have surfaced these.")
        for row in retained_discovery:
            print(f"    already monitored: {row.get('employer')} — {row.get('title')}")
    else:
        print("INTEGRATION_OK — discovery postings were consumed and reconciled, and none qualified")
        print("  for the shortlist today. A legitimate zero-fit discovery day, not a broken")
        print("  connection: the dispositions above account for every stored posting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
