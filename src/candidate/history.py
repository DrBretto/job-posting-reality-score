"""Application history — read, never written.

JPRS reads the Career Factory's application packages so it can stop re-announcing work already done.
It has no write path into them, so it *cannot* invent a submission even if a bug tried to.

The five states are not interchangeable, and the default is the weak one:

  SUBMITTED  an explicit line says it was submitted / applied / sent, or the operator confirmed it
  REJECTED   an explicit rejection or closure
  SKIPPED    explicitly considered and passed on, or declined by the operator
  PREPARED   materials exist and nothing says it was submitted  <-- the default
  NEW        no history at all

A folder, a tailored resume PDF, a FORM_ANSWERS.md, or a complete package is PREPARED. The central
workflow says "Prepare the package and leave the status blank", so a blank status means PREPARED and
an upgrade requires a quoted line. Nothing here promotes a status by inference.

Conflicts are PRESERVED. The real corpus contains cases where a package's own note says "NOT
SUBMITTED" while a later day's prose back-references "already applied". That ambiguity is a fact
about the record, so it is recorded as a conflict with both pieces of evidence and surfaced to the
operator — resolving it silently in either direction would be the system inventing a status.

Privacy: the projection keeps employer, role, requisition URL, status, and a pointer to the
evidence. No resume content, no personal circumstances, no contact details.

WHY THERE ARE TWO CONFIDENCE LEVELS
-----------------------------------
The history lives in three successive markdown formats across two months of freeform prose. A regex
scan of it was built, run against the real corpus, and compared to a careful line-by-line reading:
it mis-assigned several statuses in both directions — it called a submitted role skipped because a
later day's prose mentioned the employer in a different context, and it invented employer names out
of folder-name fragments.

That matters asymmetrically. A false SUBMITTED/REJECTED/SKIPPED **hides a live opportunity**, which
is the exact harm this system exists to prevent. A false PREPARED merely files a row in the wrong
report section.

So the scanner is not the authority, and the invariant below is enforced in code:

  reviewed entries  may carry any status, including the suppressing ones. They come from the
                    committed projection, each with a quoted line of evidence.
  parsed entries    are CAPPED at PREPARED. A scan can add a row and can say "materials exist",
                    but it can never conclude on its own that something was submitted, rejected
                    or skipped.

The scanner's real job is drift detection: telling the operator which folders on disk are missing
from the reviewed projection, so a refresh is a visible decision rather than a silent guess.

THE SECOND EVIDENCE SOURCE, AND WHY IT IS ALLOWED TO CONCLUDE
------------------------------------------------------------
The cap above is a statement about *folder prose*, not about all evidence. An application run also
writes an append-only `SUBMISSION_LOG.md`: one numbered section per target, the requisition and URL
recorded before Submit is pressed, and the employer's own acceptance text quoted verbatim after.
A folder says materials exist. A submission log says the employer answered.

So there is a third confidence level, `submission_log`, and its promotion rule is deliberately
narrow — every clause below is load-bearing rather than defensive:

  * the file must be named exactly `SUBMISSION_LOG.md`;
  * the record must sit under a numbered target heading naming BOTH an employer and a role
    (`## 3. Employer — Role`); a numbered narrative heading is not a record;
  * the section must carry an acceptance marker ON ITS OWN LINE, carrying its own bullet, bold or
    heading markup — `Result: SUBMITTED` exactly, or a `Confirmation:`/`Acceptance:` line whose
    value (or the employer's words quoted directly beneath it) actually records an acceptance;
  * anything the section QUOTES — a fenced block, a blockquoted line — is another run speaking, not
    this record, and cannot promote. The one exception is the employer's own words quoted under an
    acceptance marker, which are the evidence itself;
  * a section carrying an acceptance marker AND a not-submitted claim is HELD, never promoted, and
    so is one whose result is BLOCKED, HELD, NOT SUBMITTED, or SUBMITTED-with-a-qualifier.

**A posting URL is NOT required, and that is deliberate rather than an omission.** Seven real
submissions record their requisition id in prose and never write a `URL:` line. Holding them would
re-announce seven applications that were sent and confirmed, so they are promoted and match on
normalized employer+title — the granularity at which distinct requisitions differ in this corpus
(Machinify's two, Mozilla's four, Fieldguide's two, Syllo's two all differ by title). The cost is
real and bounded: two genuinely different requisitions sharing one employer AND one normalized title
would collapse. Where a URL is known it is carried as an alias on the committed row instead.

Held records do not vanish — they land on `ApplicationHistory.unresolved` with their reason and
evidence, and the report prints the count. Ambiguity is a fact about the record, not a gap to close
by guessing. A section whose format the reader does not recognise is held too, by name, so the next
new acceptance format surfaces on the page instead of being skipped in silence.

CUTOFF IS NOT COMPLETENESS
--------------------------
`built_at` says when this file was written. It says nothing about how far the evidence reached, and
a reader who treats it as coverage is reading a completeness claim nobody made. `cutoff` is the
separate, explicit statement: the latest evidence date this projection actually read. Anything
submitted after it is not represented here, and that stays true no matter how recent `built_at` is —
a concurrent application run may be writing its log while this one reads.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.common.models import HistoryStatus
from src.common.normalize import canonical_url, normalize_employer, normalize_title_for_matching

DEFAULT_HISTORY_PATH = "config/application_history.json"
DEFAULT_HISTORY_ROOT = "../Infotropy Book/INBOX/Employment Search"
# Where the application runs write their append-only submission logs. Read-only, like the Inbox.
DEFAULT_SUBMISSION_LOG_ROOT = (
    "../Infotropy Book/career-factory/outputs/candidates/brett-westerlund/applications"
)

CONFIDENCE_REVIEWED = "reviewed"
CONFIDENCE_SUBMISSION_LOG = "submission_log"
CONFIDENCE_PARSED = "parsed"
# The two that may carry a suppressing status. `parsed` is absent on purpose; see the module
# docstring. Adding a level here is the one edit in this file that can hide a live opening.
PROMOTING_CONFIDENCES = frozenset({CONFIDENCE_REVIEWED, CONFIDENCE_SUBMISSION_LOG})

# Explicit submission evidence. Deliberately narrow: each alternative is a literal claim that the
# application left the building.
_SUBMITTED_RE = re.compile(
    r"\b(status\s*:?\s*\**\s*submitted|submitted (?:on |august|september|july|october|november|"
    r"december|january|\d)|application submitted|submitted\s*\(operator confirmed|"
    r"operator confirmed[^.]{0,40}submit|was submitted|i submitted|confirmed by brett[^.]{0,30}"
    r"submit|rtr sent|profile submitted)\b",
    re.I,
)
_REJECTED_RE = re.compile(
    r"\b(reject(?:ed|ion)|not (?:moving|proceeding) forward|declined by (?:the )?(?:company|employer)|"
    r"closed after (?:the )?final|position (?:was )?filled|no longer under consideration)\b",
    re.I,
)
_SKIPPED_RE = re.compile(
    r"\b(skip(?:ped)?\b|do not apply|declined by brett|not carried into this round|"
    r"removed after preference|pulled\s*/?\s*no longer available|operator decision[^.]{0,20}skip|"
    r"held until|do not resurface)\b",
    re.I,
)
_NOT_SUBMITTED_RE = re.compile(
    r"\b(not (?:yet )?submitted|not submitted|ready for brett|ready to review|"
    r"no application (?:has been|was) (?:represented as )?submitted|submission not yet confirmed|"
    r"ready;? not submitted|leave the status blank|status stays blank|awaiting (?:brett|operator))\b",
    re.I,
)
_STATUS_LINE_RE = re.compile(r"^\s*\**\s*status\s*\**\s*:\s*(.+)$", re.I | re.M)
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(r"https?://[^\s)<>\"'\]]+")

# Local-business website-repair outreach shares these folders but is NOT a job application. Feeding
# it to a job deduper would suppress real openings, so it is excluded by marker.
_OUTREACH_MARKERS = re.compile(
    r"\b(outreach|proposal card|first[- ]touch|website repair|cold email|target dossier)\b", re.I
)


class HistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "reviewed"       = a human/agent read the evidence and quoted it; may carry a suppressing status.
    # "submission_log" = an append-only submission log's explicit Result marker; SUBMITTED only.
    # "parsed"         = produced by the folder scanner; capped at PREPARED by `enforce_confidence_cap`.
    confidence: str = CONFIDENCE_PARSED
    employer_name: str
    employer_key: str
    role_title: str
    title_key: str
    status: HistoryStatus
    posting_url: str | None = None
    posting_url_key: str | None = None
    # Other URLs that name this SAME requisition — an aggregator row and the employer's own ATS are
    # different URLs for one opening, and before this list they never met: the feed carries the
    # aggregator URL, the application was submitted on the ATS URL, and the lookup fell through to
    # employer+title, which misses whenever the aggregator's title differs from the requisition's.
    # Aliases are recorded from evidence that resolved one to the other, never inferred from a name.
    posting_urls: list[str] = Field(default_factory=list)
    posting_url_keys: list[str] = Field(default_factory=list)
    folder: str | None = None
    evidence_path: str | None = None
    evidence_quote: str | None = None
    # Preserved ambiguity, never resolved by this code.
    status_conflict: bool = False
    conflict_detail: str | None = None
    observed_at: datetime | None = None

    def all_url_keys(self) -> list[str]:
        keys = [self.posting_url_key] if self.posting_url_key else []
        keys += [k for k in self.posting_url_keys if k]
        seen, out = set(), []
        for k in keys:
            if k not in seen:
                seen.add(k)
                out.append(k)
        return out


class UnresolvedRecord(BaseModel):
    """A target the evidence NAMES but does not settle. Held, never guessed into a status.

    A blocked submission, a held one, an abandoned attempt and a section claiming both submitted and
    not-submitted all land here. They are not PREPARED (that would understate a possible submission)
    and not SUBMITTED (that would hide a live opening). They are visible instead.
    """

    model_config = ConfigDict(extra="forbid")
    employer_name: str
    role_title: str
    posting_url: str | None = None
    reason: str
    evidence_path: str | None = None
    evidence_quote: str | None = None


class ApplicationHistory(BaseModel):
    """Privacy-minimized, job-related history projection. Committed so production can read it."""

    model_config = ConfigDict(extra="forbid")
    built_at: datetime
    source_root: str
    # The latest evidence date this projection actually read. NOT a completeness claim: anything
    # submitted after it is not represented here, and `built_at` cannot say that on its own.
    cutoff: datetime | None = None
    # What was read to build this, so the refresh is reproducible from the file itself.
    evidence_sources: list[str] = Field(default_factory=list)
    entries: list[HistoryEntry] = Field(default_factory=list)
    # Named by the evidence, settled by none of it. See `UnresolvedRecord`.
    unresolved: list[UnresolvedRecord] = Field(default_factory=list)
    note: str = (
        "Read-only projection of application history for deduplication only. JPRS never writes "
        "application history. A prepared package is never recorded as submitted without an explicit "
        "quoted line. Conflicting evidence is preserved as a conflict, not resolved. Only entries "
        "marked confidence=reviewed may carry a suppressing status; scanner output is capped at "
        "PREPARED."
    )

    def reviewed_entries(self) -> list[HistoryEntry]:
        return [e for e in self.entries if e.confidence == CONFIDENCE_REVIEWED]

    # ---- lookup -------------------------------------------------------------------------------
    def by_url(self) -> dict[str, HistoryEntry]:
        """Every URL that names a requisition, primary and alias alike, keyed canonically."""
        index: dict[str, HistoryEntry] = {}
        for entry in self.entries:
            for key in entry.all_url_keys():
                prior = index.get(key)
                # Two entries claiming one URL is a corpus defect, not a choice to make silently.
                # Keep the STRONGER status so a stale PREPARED row cannot displace a recorded
                # submission and re-announce it as a fresh opening.
                if prior is None or _rank(entry.status) > _rank(prior.status):
                    index[key] = entry
        return index

    def by_employer_title(self) -> dict[tuple[str, str], HistoryEntry]:
        return {(e.employer_key, e.title_key): e for e in self.entries}

    def lookup(self, *, employer_name: str, title: str, url: str | None) -> HistoryEntry | None:
        """Requisition URL wins over employer+title.

        This ordering is load-bearing: the real corpus has one employer with two genuinely different
        requisitions, so matching on employer+title alone would suppress a live opening.
        """
        if url:
            hit = self.by_url().get(canonical_url(url))
            if hit is not None:
                return hit
        return self.by_employer_title().get(
            (normalize_employer(employer_name), normalize_title_for_matching(title))
        )

    def status_for(self, *, employer_name: str, title: str, url: str | None) -> HistoryStatus:
        entry = self.lookup(employer_name=employer_name, title=title, url=url)
        return entry.status if entry else HistoryStatus.NEW


# --------------------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------------------
def _classify(text: str) -> tuple[HistoryStatus, str | None, bool, str | None]:
    """Classify one blob. Returns (status, quote, conflict, conflict_detail).

    Order matters. A negation ("not submitted", "ready for Brett") beats a bare submission keyword,
    because the corpus is full of packages whose status line literally says both words.
    """
    not_sub = _NOT_SUBMITTED_RE.search(text)
    skipped = _SKIPPED_RE.search(text)
    rejected = _REJECTED_RE.search(text)
    submitted = _SUBMITTED_RE.search(text)

    if rejected:
        return HistoryStatus.REJECTED, _quote(text, rejected), False, None
    if skipped:
        return HistoryStatus.SKIPPED, _quote(text, skipped), False, None
    if submitted and not_sub:
        # Both claims present in the same document. Keep the WEAKER status and flag the conflict.
        return (
            HistoryStatus.PREPARED,
            _quote(text, not_sub),
            True,
            "document contains both a submission claim and a not-submitted claim: "
            f"{_quote(text, submitted)!r} vs {_quote(text, not_sub)!r}",
        )
    if submitted:
        return HistoryStatus.SUBMITTED, _quote(text, submitted), False, None
    return HistoryStatus.PREPARED, _quote(text, not_sub) if not_sub else None, False, None


def _quote(text: str, match: re.Match, width: int = 120, pre: int = 30) -> str:
    """Quote around a match. `pre=0` starts AT the match.

    The backward window is useful when the match is a bare keyword inside a package note. It is
    actively harmful on a submission log, where the prose immediately before a `Result:` line is the
    form-answer readback — so a 30-character look-back drags work-authorization and sponsorship
    answers into a projection whose whole contract is that it carries no personal circumstances.
    """
    start = max(0, match.start() - pre)
    end = min(len(text), match.end() + width)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _split_folder_name(name: str) -> tuple[str, str]:
    """`<Employer> - <Role>` / `<Employer> — <Role>` / `<Employer> Application` -> (employer, role)."""
    cleaned = re.sub(r"\s+", " ", name).strip()
    for dash in ("—", " - ", " – "):
        if dash in cleaned:
            employer, _, role = cleaned.partition(dash)
            return employer.strip(), role.strip()
    cleaned = re.sub(
        r"\s+(application|contract|recruiter|interview prep)$", "", cleaned, flags=re.I
    ).strip()
    return cleaned, ""


def _first_url(text: str) -> str | None:
    m = _MD_LINK_RE.search(text) or _BARE_URL_RE.search(text)
    return m.group(1) if (m and m.lastindex) else (m.group(0) if m else None)


def build_history(
    root: str | Path = DEFAULT_HISTORY_ROOT, *, now: datetime | None = None
) -> tuple[ApplicationHistory, list[str]]:
    """Walk the dated application folders and build the projection.

    Local operator command only; opens files read-only and writes nothing under `root`.
    Returns (history, warnings).
    """
    base = Path(root)
    now = now or datetime.now(timezone.utc)
    warnings: list[str] = []
    if not base.is_dir():
        return ApplicationHistory(built_at=now, source_root=str(root)), [
            f"history root not found: {root}"
        ]

    entries: dict[tuple[str, str], HistoryEntry] = {}

    day_dirs = sorted(
        d for d in base.iterdir()
        if d.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}", d.name)
    )
    for day in day_dirs:
        day_blob = ""
        for index_name in ("DAILY_LOG.md", "START_HERE.md", "APPLICATIONS.md"):
            index_file = day / index_name
            if index_file.is_file():
                try:
                    day_blob += "\n" + index_file.read_text(errors="replace")
                except OSError as exc:  # pragma: no cover - unreadable file
                    warnings.append(f"{index_file}: {exc}")

        for role_dir in sorted(p for p in day.iterdir() if p.is_dir()):
            notes = role_dir / "APPLICATION_NOTES.md"
            blob = ""
            if notes.is_file():
                try:
                    blob = notes.read_text(errors="replace")
                except OSError as exc:  # pragma: no cover
                    warnings.append(f"{notes}: {exc}")
            # A folder with no notes and no application shape is not a job package.
            has_package = notes.is_file() or any(
                (role_dir / f).exists() for f in ("FORM_ANSWERS.md",)
            ) or any(role_dir.glob("*.pdf"))
            if not has_package:
                continue
            if _OUTREACH_MARKERS.search(blob[:2000]) and not notes.is_file():
                continue
            if _OUTREACH_MARKERS.search(role_dir.name):
                continue

            employer, role = _split_folder_name(role_dir.name)
            if not employer:
                continue
            # A recruiter-resume-only folder with no employer is not dedup material.
            if re.match(r"^(generic|new resources)\b", employer, re.I) and not role:
                continue

            status_text = "\n".join(_STATUS_LINE_RE.findall(blob)) or blob[:4000]
            status, quote, conflict, detail = _classify(status_text)

            # Day-level index prose can carry an explicit correction ("X was submitted on ...").
            # It can UPGRADE to submitted/rejected/skipped, and when it disagrees with the folder's
            # own note the disagreement is recorded rather than smoothed away.
            emp_pattern = re.escape(employer.split()[0]) if employer else None
            if emp_pattern and day_blob:
                for line in day_blob.splitlines():
                    if not re.search(emp_pattern, line, re.I):
                        continue
                    line_status, line_quote, _c, _d = _classify(line)
                    if line_status in (
                        HistoryStatus.SUBMITTED, HistoryStatus.REJECTED, HistoryStatus.SKIPPED
                    ) and line_status != status:
                        if status == HistoryStatus.PREPARED and line_status == HistoryStatus.SUBMITTED:
                            conflict = True
                            detail = (
                                f"package note reads not-submitted while the day index states a "
                                f"submission: {line_quote!r}"
                            )
                            # Ambiguous by construction: keep PREPARED, flag it, let the operator
                            # decide. Upgrading here is exactly how a system invents a submission.
                        else:
                            status, quote = line_status, line_quote
                        break

            url = _first_url(blob) or None
            key = (normalize_employer(employer), normalize_title_for_matching(role or employer))
            entry = HistoryEntry(
                employer_name=employer,
                employer_key=normalize_employer(employer),
                role_title=role,
                title_key=normalize_title_for_matching(role or employer),
                status=status,
                posting_url=url,
                posting_url_key=canonical_url(url) if url else None,
                folder=str(role_dir.relative_to(base)),
                evidence_path=str(notes.relative_to(base)) if notes.is_file() else None,
                evidence_quote=(quote or None),
                status_conflict=conflict,
                conflict_detail=detail,
                observed_at=now,
            )
            prior = entries.get(key)
            # A later folder for the same employer+role is a repeat engagement. Keep the STRONGER
            # terminal status (submitted/rejected/skipped outrank prepared) so a re-prepared package
            # cannot erase a recorded submission — that exact case exists in the corpus.
            if prior is None or _rank(entry.status) > _rank(prior.status):
                if prior is not None and prior.posting_url_key and not entry.posting_url_key:
                    entry.posting_url = prior.posting_url
                    entry.posting_url_key = prior.posting_url_key
                entries[key] = entry
            elif prior.status_conflict is False and entry.status_conflict:
                prior.status_conflict = True
                prior.conflict_detail = entry.conflict_detail

    scanned = enforce_confidence_cap(
        sorted(entries.values(), key=lambda e: (e.employer_key, e.title_key))
    )
    return (
        ApplicationHistory(built_at=now, source_root=str(root), entries=scanned),
        warnings,
    )


# --------------------------------------------------------------------------------------------------
# Submission logs — the evidence a folder scan cannot produce
# --------------------------------------------------------------------------------------------------
# `## 3. Pivotal Health — Senior Software Engineer, Case Execution`, with the trailing `· SUBMITTED`
# some runs append stripped off — the heading's decoration is never the evidence, the Result is.
_LOG_SECTION_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.M)
# The protocol's own acceptance markers. Both are written only after the employer's page answered,
# which is why they are the only lines allowed to conclude. The runs use two formats and neither is
# more authoritative than the other: a `Result:` verdict, or a `Confirmation:` line carrying the
# employer's own confirmation URL and its acceptance text verbatim.
# Line-anchored, and a blockquote is NOT this record's own line. This corpus quotes other runs'
# result lines verbatim as house style, so an unanchored match promoted a record that said in its
# own prose that nothing was sent. `>` is excluded from the leading run for exactly that reason;
# fenced blocks are stripped before matching (`_strip_quoted_regions`).
# The marker must also carry its OWN markup — a bullet, bold, or a heading. Every real occurrence in
# this corpus does (`- **Result:`, `**Result:`, `### Result:`); a bare `Result:` at the start of a
# line is a wrapped prose sentence, and one of those talked about a DIFFERENT employer's application.
_LOG_RESULT_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]+|\#{1,6}[ \t]+)?(?:\*\*|(?<=[-*] )|(?<=\# ))[ \t]*"
    r"\*{0,2}Result:\*{0,2}[ \t]*\**[ \t]*([A-Z][A-Z \-]{2,40})",
    re.M,
)
_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~).*?^[ \t]*(?:```|~~~)[ \t]*$", re.M | re.S)
_BLOCKQUOTE_RE = re.compile(r"^[ \t]*>.*$", re.M)


def _strip_quoted_regions(section: str) -> str:
    """Blank out fenced blocks and blockquotes, preserving line structure.

    Everything a section QUOTES — another run's log line, a template, the employer's own page — is
    not this record speaking. Kept as blank lines rather than deleted so offsets and line anchoring
    still behave.
    """
    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    return _BLOCKQUOTE_RE.sub(blank, _FENCE_RE.sub(blank, section))


# What an acceptance actually SAYS, not merely that a line is labelled one. A `Confirmation:` whose
# value is "still pending" and an `Acceptance:` whose value is "refused" are both refusals wearing an
# acceptance label, and the label alone used to conclude SUBMITTED.
_ACCEPTANCE_EVIDENCE_RE = re.compile(
    r"(/confirmation|/applied\b|/Success/|/thanks\b|thank you for applying|"
    r"application (?:has been )?received|application submitted|successfully submitted|"
    r"success(?:fully)? (?:submitted|applied)|all done|we(?:'|’)ll contact you|"
    r"thanks (?:so much )?for applying|applied\s*[✓✔])",
    re.I,
)
# A refusal in the marker's own value. Any of these and the label concludes nothing.
_ACCEPTANCE_NEGATION_RE = re.compile(
    r"\b(pending|refused|blocked|held|failed|none|not (?:yet )?(?:received|submitted|sent)|"
    r"nothing|awaiting|unavailable|no confirmation)\b",
    re.I,
)
# `Confirmation:` and `Acceptance …:` are the same act in different words — the employer's own page
# quoted back. Three formats exist because three runs wrote them, and a fourth will appear; the
# heading guard below is what stops the fourth from being lost in silence.
# Tight on purpose. `Acceptance criteria:` and `Confirmation URL for this flow. Captures:` are both
# plausible line starts in this corpus — "acceptance criteria" already appears dozens of times in
# quoted resume and cover-letter text — and neither is an employer saying yes. Only the bare keyword,
# optionally carrying one short parenthetical and a `, verbatim`, is the marker.
#
# Every gap is `[ \t]`, never `\s`. `\s` matches newlines, and with it the value group skipped the
# blockquote holding the employer's words and captured the NEXT bullet instead — so the negation
# check ran against an unrelated sentence and held two genuine submissions. The value is whatever
# remains on the marker's OWN line, and it may be empty when the acceptance follows underneath.
_LOG_CONFIRMATION_RE = re.compile(
    r"^[ \t]*(?:[-*][ \t]*)?\*{0,2}(?:Confirmation|Acceptance)"
    r"(?:[ \t]*\([^)\n]{0,40}\))?(?:,[ \t]*verbatim)?[ \t]*:\*{0,2}[ \t]*(.*)$",
    re.M | re.I,
)
# A heading may decorate itself with its own outcome. That is NOT evidence — the corpus contains
# `· PREPARED, NOT SUBMITTED` headings too — but a heading claiming SUBMITTED while the section
# carries no acceptance marker means the reader has met a format it does not know. That is reported
# as unresolved rather than dropped, because a silently skipped section is a submission the next
# round announces as a fresh opportunity.
# The decoration is BOLD as often as it is bare, and it carries a qualifier as often as it stands
# alone — `· **SUBMITTED, employer-confirmed**` and `· **SENT**` are both real headings from the
# 2026-09-28 live-pool log. Anchoring on a bare word at end-of-heading matched neither, so all four
# of that log's sections fell past this guard and past the unsent one below and were dropped in
# SILENCE: two employer-confirmed submissions, still open on their employers' own boards, invisible
# to the projection that exists to stop them being re-announced. Match the claim wherever it starts
# and whatever follows it. Widening here can only make a section VISIBLE — it is read under
# `if not marker`, so it adds to `unresolved` and can never promote anything to SUBMITTED.
_LOG_HEADING_CLAIMS_SUBMITTED_RE = re.compile(r"[·|]\s*\*{0,2}(?:SUBMITTED|SENT)\b", re.I)
# A heading decoration that claims anything OTHER than submitted. It establishes nothing either, but
# it does mean the section is a target record with a stated outcome, so it is held and counted
# rather than dropped — otherwise "held, not settled" undercounts and the record is invisible.
# Same bold tolerance, and for the same measured reason: `· **HELD, unchanged**` was dropped.
# This alternation is tried BEFORE the submitted-claim above, so `NOT SENT` and `NOT SUBMITTED`
# still resolve here and never reach it.
_LOG_HEADING_CLAIMS_UNSENT_RE = re.compile(
    r"[·|]\s*\*{0,2}(PREPARED|HELD|NOT\s+SENT|NOT\s+SUBMITTED|BLOCKED)", re.I
)
# The record's own statement of which requisition it is. Deliberately NOT "any URL in the section":
# these sections also cite requisitions that were considered and NOT applied to — the closed Evolve
# Staff row, the hybrid Fieldguide requisition ruled out on location — and treating a narrative
# mention as this record's URL would suppress an opening nobody applied to.
_LOG_URL_LINE_RE = re.compile(r"^\s*[-*]?\s*\*{0,2}URL:\*{0,2}\s*(\S+)", re.M)
_LOG_EMDASH_SPLIT = re.compile(r"\s+[—–]\s+|\s+-\s+")
# Decoration some logs put on the heading itself. Stripped before the employer/role split so a
# heading's own status word can never be mistaken for a role title.
# Bold-wrapped decoration left unstripped does not merely look untidy: the role title then becomes
# `Operations Engineer II · **SUBMITTED, employer-confirmed**`, whose title key matches no feed row
# and no other record of the same application, so even a section that IS read cannot be matched or
# settled. Strip the decoration whether or not it is bold and whatever qualifier trails it.
_LOG_HEADING_DECORATION_RE = re.compile(
    r"\s*[·|]\s*\*{0,2}(?:SUBMITTED|SENT|PREPARED|NOT\s+SUBMITTED|NOT\s+SENT|BLOCKED|HELD)[^#]*$",
    re.I,
)
_LOG_ITALIC_NOTE_RE = re.compile(r"\s*\*\(.*?\)\*\s*$")
# A trailing ATS name in a heading is where the form lives, not part of the role title. Left in, it
# would stop "Software Engineer, Quality & Automation (Ashby)" matching the feed's own title.
_LOG_ATS_SUFFIX_RE = re.compile(
    r"\s*\((?:ashby|greenhouse|lever|workable|recruitee|paylocity|trakstar)\)\s*$", re.I
)


def _split_log_heading(heading: str) -> tuple[str, str]:
    cleaned = _LOG_HEADING_DECORATION_RE.sub("", heading).strip()
    cleaned = _LOG_ITALIC_NOTE_RE.sub("", cleaned).strip()
    parts = _LOG_EMDASH_SPLIT.split(cleaned, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), _LOG_ATS_SUFFIX_RE.sub("", parts[1]).strip()
    return cleaned, ""


def _declared_url(section: str) -> str | None:
    """The URL this record declares for itself, or None.

    Only the `URL:` line counts. A URL anywhere else in the section is narrative — and in this
    corpus the narrative genuinely names requisitions that were NOT applied to.
    """
    match = _LOG_URL_LINE_RE.search(section)
    if not match:
        return None
    url = match.group(1).strip().strip("`<>").rstrip(".,;:`'\"\\")
    return url if url.lower().startswith(("http://", "https://")) else None


def read_submission_logs(
    root: str | Path = DEFAULT_SUBMISSION_LOG_ROOT,
) -> tuple[list[HistoryEntry], list[UnresolvedRecord], list[str], datetime | None]:
    """Read the append-only submission logs.

    Returns (submitted_entries, unresolved, files_read, latest_evidence_date).

    Promotion is narrow by construction and the narrowness is the point — see the module docstring.
    A section that does not clear every clause is HELD, which is a visible answer, not a silent one.
    """
    base = Path(root)
    entries: list[HistoryEntry] = []
    unresolved: list[UnresolvedRecord] = []
    files: list[str] = []
    # Days on which this reader actually SETTLED something. The cutoff is derived from these, not
    # from which files were opened: a log the reader could not understand would otherwise advance
    # the cutoff and flip the report to `current` while covering nothing — which is precisely what
    # happened the morning a fourth acceptance format arrived.
    settled_days: list[datetime] = []
    if not base.is_dir():
        return entries, unresolved, files, None

    for log in sorted(base.rglob("SUBMISSION_LOG.md")):
        try:
            text = log.read_text(errors="replace")
        except OSError:  # pragma: no cover - unreadable file
            continue
        rel = str(log.relative_to(base))
        files.append(rel)

        day = re.match(r"(\d{4}-\d{2}-\d{2})", log.parent.name)
        observed = (
            datetime.strptime(day.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if day else None
        )

        bounds = [(m.start(), m.group(2)) for m in _LOG_SECTION_RE.finditer(text)]
        for index, (start, heading) in enumerate(bounds):
            end = bounds[index + 1][0] if index + 1 < len(bounds) else len(text)
            raw_section = text[start:end]
            # Everything this section QUOTES is not this section speaking.
            section = _strip_quoted_regions(raw_section)
            employer, role = _split_log_heading(heading)
            # A target record names an employer AND a role. A numbered narrative heading ("0. The
            # permission refusal did not recur") names neither, and is not a record.
            if not employer or not role:
                continue

            result = _LOG_RESULT_RE.search(section)
            confirmation = _LOG_CONFIRMATION_RE.search(section)
            verdict = (result.group(1).strip().upper() if result else "")
            url = _declared_url(section)
            not_sub = _NOT_SUBMITTED_RE.search(section)
            marker = result or confirmation
            # Quote FROM the marker, never from before it. A backward window reaches into the
            # form-answer prose that precedes it and drags work-authorization and sponsorship
            # answers into a projection that promises to carry none.
            quote = _quote(section, marker, pre=0) if marker else None
            # `SUBMITTED PENDING VERIFICATION` is not SUBMITTED. Exact match, not a prefix.
            accepted = verdict == "SUBMITTED"
            if not result and confirmation is not None:
                # A label is not an acceptance. The value has to SAY the employer answered, and must
                # not be a refusal wearing an acceptance label ("Confirmation: still pending").
                #
                # The window is read from the RAW section on purpose. `_strip_quoted_regions` blanks
                # quotes because a quoted `Result:` line is another run speaking — but the blockquote
                # under an acceptance marker is the EMPLOYER speaking, quoted verbatim, and that is
                # the evidence itself. Blanking it held two genuine submissions. Offsets are
                # preserved by the blanking, so the marker's position maps onto the raw text.
                # Two different scopes, and the difference is load-bearing:
                #   evidence  — the marker's line PLUS what it introduces, because the employer's
                #               words are often on the next lines as a blockquote;
                #   negation  — the marker's OWN line only. A later sentence in the same section
                #               ("the screenshot was refused by the permission layer") is about
                #               something else entirely, and scoping the negation to the window held
                #               two genuine submissions on a word that was never about them.
                line = confirmation.group(0)
                window = raw_section[confirmation.start():confirmation.end() + 400]
                # `group(1)` may legitimately be empty — the employer's words then sit in the
                # blockquote underneath, which the window covers.
                accepted = bool(
                    _ACCEPTANCE_EVIDENCE_RE.search(window)
                    and not _ACCEPTANCE_NEGATION_RE.search(line)
                )

            # A section carrying BOTH claims is HELD, whichever marker fired. An append-only log's
            # natural shape is a correction appended under the same heading, and that is exactly the
            # case where promoting hides a live opening. Only applies when the marker CLAIMED an
            # acceptance — a `Result: BLOCKED` beside "not submitted" is not ambiguous, it agrees.
            if marker and not_sub and accepted:
                unresolved.append(UnresolvedRecord(
                    employer_name=employer, role_title=role, posting_url=url,
                    reason="submission log section carries an acceptance marker and a "
                           "not-submitted claim; held rather than resolved",
                    evidence_path=rel, evidence_quote=_quote(section, not_sub, pre=0),
                ))
                settled_days.append(observed)
                continue

            if not marker:
                if not_sub:
                    # Named, prepared, explicitly not sent. A real fact, and not a submission.
                    unresolved.append(UnresolvedRecord(
                        employer_name=employer, role_title=role, posting_url=url,
                        reason="submission log records this target as prepared and not submitted",
                        evidence_path=rel, evidence_quote=_quote(section, not_sub, pre=0),
                    ))
                    settled_days.append(observed)
                    continue
                head = heading.strip()
                if _LOG_HEADING_CLAIMS_UNSENT_RE.search(head):
                    # The section states its outcome only in its heading. That establishes nothing,
                    # but it does mean a target was named and not sent — visible, not dropped.
                    unresolved.append(UnresolvedRecord(
                        employer_name=employer, role_title=role, posting_url=url,
                        reason="this section records a target as prepared, held or not sent; it is "
                               "not a submission and it is not settled",
                        evidence_path=rel, evidence_quote=head,
                    ))
                    settled_days.append(observed)
                    continue
                # An unrecognised format. The heading may or may not decorate itself; what makes
                # this a RECORD rather than prose is that it names a requisition. Reported, never
                # dropped — a silently skipped section is a submission the next round re-announces.
                if url or _LOG_HEADING_CLAIMS_SUBMITTED_RE.search(head):
                    unresolved.append(UnresolvedRecord(
                        employer_name=employer, role_title=role, posting_url=url,
                        reason="this section names a target but carries no recognised acceptance "
                               "or not-submitted marker (Result:/Confirmation:/Acceptance:); the "
                               "submission-log reader needs teaching this format",
                        evidence_path=rel, evidence_quote=heading.strip(),
                    ))
                    settled_days.append(observed)
                continue
            if not accepted:
                unresolved.append(UnresolvedRecord(
                    employer_name=employer, role_title=role, posting_url=url,
                    reason=(f"submission log records {verdict.strip()}, not a submission"
                            if result else
                            "the acceptance marker's value does not record an employer "
                            "acceptance, so this section does not establish a submission"),
                    evidence_path=rel, evidence_quote=quote,
                ))
                settled_days.append(observed)
                continue

            # A submission with no declared URL is still a submission — only its URL is absent. It
            # matches on employer+title, which is the granularity distinct requisitions differ at.
            entries.append(HistoryEntry(
                confidence=CONFIDENCE_SUBMISSION_LOG,
                employer_name=employer,
                employer_key=normalize_employer(employer),
                role_title=role,
                title_key=normalize_title_for_matching(role or employer),
                status=HistoryStatus.SUBMITTED,
                posting_url=url,
                posting_url_key=canonical_url(url) if url else None,
                evidence_path=rel,
                evidence_quote=quote,
                observed_at=observed,
            ))
            settled_days.append(observed)

    # A target held on one day and submitted on a later one is settled, not unresolved. The held
    # record stays true of its own day and is not a live question, so it does not reach the report.
    settled = {(e.employer_key, e.title_key) for e in entries}
    # One target, one held row. Two runs recording the same unsent target on the same day is the
    # ordinary shape of an append-only corpus — the contracts log and the live-pool log both name
    # the Catalyst Lead seat — and listing it twice on the operator's page says nothing the first
    # row did not. The FIRST occurrence is kept, so the earliest evidence stays the cited one.
    deduped: list[UnresolvedRecord] = []
    seen: set[tuple[str, str]] = set()
    for u in unresolved:
        key = (normalize_employer(u.employer_name),
               normalize_title_for_matching(u.role_title or u.employer_name))
        if key in settled or key in seen:
            continue
        seen.add(key)
        deduped.append(u)
    unresolved = deduped
    latest = max((d for d in settled_days if d is not None), default=None)
    return entries, unresolved, files, latest


def merge_entries(*groups: list[HistoryEntry]) -> list[HistoryEntry]:
    """Merge entry groups on employer+title, keeping the stronger status and unioning URLs.

    Later groups do not overwrite earlier ones — status rank decides, and every URL either side
    knows about survives on the winner as an alias. That is what lets one submission answer for the
    aggregator row and the ATS row at once.
    """
    merged: dict[tuple[str, str], HistoryEntry] = {}
    for group in groups:
        for entry in group:
            key = (entry.employer_key, entry.title_key)
            prior = merged.get(key)
            if prior is None:
                merged[key] = entry.model_copy(deep=True)
                continue
            winner, loser = (
                (entry, prior) if _rank(entry.status) > _rank(prior.status) else (prior, entry)
            )
            if winner is entry:
                winner = entry.model_copy(deep=True)
                merged[key] = winner
            for url, url_key in _url_pairs(loser) + _url_pairs(winner):
                if url_key and url_key != winner.posting_url_key \
                        and url_key not in winner.posting_url_keys:
                    winner.posting_urls.append(url)
                    winner.posting_url_keys.append(url_key)
            if winner.posting_url is None and loser.posting_url:
                winner.posting_url = loser.posting_url
                winner.posting_url_key = loser.posting_url_key
            if loser.status_conflict and not winner.status_conflict:
                # A submission-log win is the one case where the conflict is ANSWERED rather than
                # merely outranked. That confidence class carries the employer's own recorded
                # acceptance against a named requisition — the same reason `enforce_confidence_cap`
                # exempts it — and every conflict in this corpus is some version of "the local note
                # and the evidence disagree about whether this was sent". Bjak is the worked case:
                # its reviewed row said "Needs operator confirmation", and Bjak's own applicant
                # tracking system had acknowledged the application on 2026-07-22. Carrying that flag
                # onto the confirmed row would keep asking a question the employer already answered.
                #
                # Nothing is lost by dropping it: the winner's own `evidence_quote` and
                # `evidence_path` point at the record that resolved it, and the stale note is
                # described in full in the confirmation log rather than paraphrased here.
                if not (winner.confidence == CONFIDENCE_SUBMISSION_LOG
                        and winner.status is HistoryStatus.SUBMITTED):
                    winner.status_conflict = True
                    winner.conflict_detail = loser.conflict_detail
    return sorted(merged.values(), key=lambda e: (e.employer_key, e.title_key))


def _url_pairs(entry: HistoryEntry) -> list[tuple[str, str]]:
    pairs = []
    if entry.posting_url and entry.posting_url_key:
        pairs.append((entry.posting_url, entry.posting_url_key))
    pairs += list(zip(entry.posting_urls, entry.posting_url_keys))
    return pairs


def refresh_history(
    *,
    projection_path: str | Path = DEFAULT_HISTORY_PATH,
    inbox_root: str | Path = DEFAULT_HISTORY_ROOT,
    submission_log_root: str | Path = DEFAULT_SUBMISSION_LOG_ROOT,
    now: datetime | None = None,
) -> tuple[ApplicationHistory, dict]:
    """Rebuild the projection from evidence. Repeatable, and read-only against every source.

    Two inputs become entries: the committed reviewed projection and the submission logs. Nothing is
    deleted — a reviewed entry the evidence no longer mentions survives, because its absence from a
    log is not proof of anything.

    **The folder scan is drift, not entries, and that is deliberate.** Its rows are capped at
    PREPARED, and a PREPARED row is not harmless: the report moves anything that is not NEW out of
    the candidate sections, so a scanner row for a folder that was only ever considered would demote
    a live opening on the strength of a folder name. The scan's output is reported as drift — which
    folders the reviewed projection does not know about — and stays the operator's decision to act
    on, exactly as `history-scan` already treats it.
    """
    now = now or datetime.now(timezone.utc)
    existing = load_history(projection_path)
    reviewed = list(existing.entries) if existing else []

    submitted, unresolved, log_files, latest_log = read_submission_logs(submission_log_root)
    scanned, warnings = build_history(inbox_root, now=now)

    merged = enforce_confidence_cap(merge_entries(reviewed, submitted))
    known = {(e.employer_key, e.title_key) for e in merged}
    scan_drift = sorted(
        f"{e.employer_name} — {e.role_title}".rstrip(" —")
        for e in scanned.entries if (e.employer_key, e.title_key) not in known
    )

    # The cutoff is the latest evidence date actually read, never `now` — dating a projection by
    # when it ran would assert coverage it does not have.
    cutoff = latest_log
    sources = [str(projection_path), str(submission_log_root), str(inbox_root)]

    history = ApplicationHistory(
        built_at=now,
        source_root=str(inbox_root),
        cutoff=cutoff,
        evidence_sources=sources,
        entries=merged,
        unresolved=unresolved,
    )
    before = {(e.employer_key, e.title_key): e.status for e in reviewed}
    changes = {
        "entries_before": len(reviewed),
        "entries_after": len(merged),
        "added": sorted(
            f"{e.employer_name} — {e.role_title}" for e in merged
            if (e.employer_key, e.title_key) not in before
        ),
        "status_changed": sorted(
            f"{e.employer_name} — {e.role_title}: "
            f"{before[(e.employer_key, e.title_key)].value} -> {e.status.value}"
            for e in merged
            if (e.employer_key, e.title_key) in before
            and before[(e.employer_key, e.title_key)] != e.status
        ),
        "unresolved": len(unresolved),
        "submission_logs_read": log_files,
        "cutoff": cutoff.date().isoformat() if cutoff else None,
        # Folders on disk the projection does not know about. Reported, never merged — see the
        # docstring. This is the drift signal, and acting on it is an operator decision.
        "scan_drift": scan_drift,
        "warnings": warnings,
    }
    return history, changes


SUPPRESSING_STATUSES = frozenset({
    HistoryStatus.SUBMITTED, HistoryStatus.REJECTED, HistoryStatus.SKIPPED,
})


def enforce_confidence_cap(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """Cap scanner-derived entries at PREPARED.

    This is the code-level guarantee behind the module docstring: no amount of regex cleverness lets
    a *folder scan* conclude that an application was submitted, rejected or skipped. A
    `submission_log` entry is exempt because it is not a scan of prose — it carries the employer's
    own recorded answer against a named requisition — and it can only ever say SUBMITTED.
    """
    for entry in entries:
        if entry.confidence == CONFIDENCE_SUBMISSION_LOG and entry.status != HistoryStatus.SUBMITTED:
            # Belt and braces: the reader cannot produce this, and if it ever did, the wrong
            # direction here is a hidden opening.
            entry.conflict_detail = (
                f"submission-log entry carried {entry.status.value}, which that reader may not "
                "conclude; reduced to PREPARED"
            )
            entry.status_conflict = True
            entry.status = HistoryStatus.PREPARED
            continue
        if entry.confidence not in PROMOTING_CONFIDENCES and entry.status in SUPPRESSING_STATUSES:
            entry.conflict_detail = (
                f"scanner read this as {entry.status.value} from "
                f"{entry.evidence_quote!r}, but unreviewed scans are capped at PREPARED; "
                "needs operator review before it can suppress a posting"
            )
            entry.status_conflict = True
            entry.status = HistoryStatus.PREPARED
    return entries


_STATUS_RANK = {
    HistoryStatus.NEW: 0,
    HistoryStatus.PREPARED: 1,
    HistoryStatus.SKIPPED: 2,
    HistoryStatus.REJECTED: 3,
    HistoryStatus.SUBMITTED: 4,
}


def _rank(status: HistoryStatus) -> int:
    return _STATUS_RANK.get(status, 0)


def load_history(path: str | Path = DEFAULT_HISTORY_PATH) -> ApplicationHistory | None:
    """Load the committed projection, and enforce the confidence cap ON THE READ PATH.

    The cap used to run only inside the builders, which made the module's headline guarantee true of
    the code that WRITES the projection and false of the artifact production actually READS. The
    file is hand-edited — the alias rows in it cannot be produced by `refresh_history` — so a
    `parsed` row carrying SUBMITTED would have suppressed a live opening with nothing in its way.
    This is the last gate before a status can hide a posting, so the cap belongs here too.
    """
    p = Path(path)
    if not p.is_file():
        return None
    history = ApplicationHistory.model_validate(json.loads(p.read_text()))
    enforce_confidence_cap(history.entries)
    return history


def save_history(history: ApplicationHistory, path: str | Path = DEFAULT_HISTORY_PATH) -> None:
    Path(path).write_text(json.dumps(history.model_dump(mode="json"), indent=2) + "\n")


def empty_history(now: datetime | None = None) -> ApplicationHistory:
    return ApplicationHistory(
        built_at=now or datetime.now(timezone.utc), source_root="<none>", entries=[]
    )
