"""Optional narrator — FEATURE-FLAGGED OFF in V1. Not on the V1 report path.

The LLM is a narrator, never the authority (SCORING §4, PANEL_DISSENT M2):
  - It MAY paraphrase an already-computed scorecard + supplied ChangeEvents.
  - It MAY NOT invent/adjust any date or number, decide state, or set a score.
  - Enforcement is TWO gates:
      1. M2 slot-fill: output is constrained to a fixed set of pre-approved behavioral sentence
         frames; the model only selects/orders frames + fills evidence-ref slots.
      2. post-check: every date/number in the output must appear in the supplied evidence set,
         AND the never-fake vocabulary guard must pass — else reject and fall back to the
         deterministic template. A no-banned-token accusatory paraphrase still fails gate 1
         (it is not one of the approved frames) and gate 2's vocab scan.
"""

from __future__ import annotations

import re

from src.llm.bedrock_client import BedrockClient
from src.report.handler import assert_no_banned_vocab

# Master switch. OFF for V1 (the deterministic template is authoritative). Enable only at the P8 gate.
NARRATOR_ENABLED = False

# pre-approved behavioral sentence frames (M2). {slots} are filled ONLY from supplied evidence.
APPROVED_FRAMES = (
    "First observed {first_seen_date}.",
    "Edited {n_changes} time(s); last edit {last_change_date}.",
    "Live for {days_live} days.",
    "Reposted {n_reposts} time(s) in the reopen window (confidence {repost_confidence}).",
    "Application priority band {priority_band} (confidence {priority_confidence}).",
)

_NUMBER_RE = re.compile(r"\d[\d,]*\.?\d*")


def extract_numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "") for m in _NUMBER_RE.finditer(text)}


def post_check(narration: str, evidence_values: set[str]) -> tuple[bool, str | None]:
    """Return (ok, reason). ok=False => caller must fall back to the deterministic template."""
    # gate 2a: no banned vocabulary
    try:
        assert_no_banned_vocab(narration)
    except ValueError as e:
        return False, f"banned vocabulary: {e}"
    # gate 2b: every number token in the output must appear among the evidence's number tokens
    # (evidence values are tokenized the same way so "2026-07-24" supplies 2026/07/24)
    allowed: set[str] = set()
    for v in evidence_values:
        allowed |= extract_numbers(str(v))
    for num in extract_numbers(narration):
        if num not in allowed:
            return False, f"unsupported number/date not in evidence: {num!r}"
    return True, None


def narrate(payload: dict, *, client: BedrockClient | None = None, template_fallback: str = "") -> str:
    """V1: returns the deterministic template. The LLM path is gated OFF.

    `payload` carries the already-computed scorecard + evidence. `evidence_values` is the closed set
    of numbers/dates the narration is permitted to contain.
    """
    if not NARRATOR_ENABLED:
        return template_fallback

    client = client or BedrockClient()  # pragma: no cover - gated off in V1
    evidence_values = set(payload.get("evidence_values", []))  # pragma: no cover
    prompt = _build_prompt(payload)  # pragma: no cover
    raw = client.run_small(prompt, stub=template_fallback)  # pragma: no cover
    ok, _reason = post_check(raw, evidence_values)  # pragma: no cover
    return raw if ok else template_fallback  # pragma: no cover


def _build_prompt(payload: dict) -> str:  # pragma: no cover - gated off in V1
    frames = "\n".join(f"- {f}" for f in APPROVED_FRAMES)
    return (
        "You are a narrator, not an authority. Select and order ONLY from these exact sentence "
        "frames, filling slots strictly from the supplied evidence. Do not invent any date, number, "
        "or judgment. Do not use the words fake/real/ghost/scam.\n\n"
        f"Approved frames:\n{frames}\n\nEvidence:\n{payload}\n"
    )
