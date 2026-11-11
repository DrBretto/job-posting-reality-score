"""Diff two disposition audits by job id, so every changed verdict is named rather than counted.

A count can move by coincidence: one role excluded and one retained nets to zero. This names each
identity whose bucket, screening outcome or rule set changed, with the reason on both sides.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def delta(before: dict, after: dict) -> dict:
    b, a = before["dispositions"], after["dispositions"]
    changed = []
    for job_id in sorted(set(b) | set(a)):
        bd, ad = b.get(job_id), a.get(job_id)
        if bd is None or ad is None:
            changed.append({
                "job_id": job_id,
                "change": "absent_before" if bd is None else "absent_after",
                "employer": (ad or bd)["employer"], "title": (ad or bd)["title"],
            })
            continue
        keys = ("bucket", "screen_outcome", "exclusion_rules", "pending_rules", "suppressed_rules")
        if all(bd[k] == ad[k] for k in keys):
            continue
        changed.append({
            "job_id": job_id,
            "employer": ad["employer"],
            "title": ad["title"],
            "before": {k: bd[k] for k in keys} | {"reason": bd["reason"]},
            "after": {k: ad[k] for k in keys} | {"reason": ad["reason"]},
            "evidence_spans_after": ad["evidence_spans"],
        })

    def direction(row):
        if "change" in row:
            return row["change"]
        was, now = row["before"]["bucket"], row["after"]["bucket"]
        if now == "policy_excluded" and was != "policy_excluded":
            return "newly_excluded"
        if was == "policy_excluded" and now != "policy_excluded":
            return "no_longer_excluded"
        if was == "retained" and now != "retained":
            return "lost_from_report"
        if now == "retained" and was != "retained":
            return "newly_retained"
        return "reason_or_state_changed"

    for row in changed:
        row["direction"] = direction(row)

    return {
        "totals_before": before["totals"],
        "totals_after": after["totals"],
        "ruleset_before": before.get("ruleset_version"),
        "ruleset_after": after.get("ruleset_version"),
        "changed_count": len(changed),
        "by_direction": {
            d: sum(1 for r in changed if r["direction"] == d)
            for d in sorted({r["direction"] for r in changed})
        },
        "changed": changed,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    result = delta(json.loads(Path(args.before).read_text()),
                   json.loads(Path(args.after).read_text()))
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "changed"}, indent=2))
    for row in result["changed"]:
        print(f"\n[{row['direction']}] {row.get('title')} @ {row.get('employer')}")
        if "before" in row:
            print(f"   before: {row['before']['bucket']}/{row['before']['screen_outcome']} "
                  f"excl={row['before']['exclusion_rules']} pend={row['before']['pending_rules']}")
            print(f"   after:  {row['after']['bucket']}/{row['after']['screen_outcome']} "
                  f"excl={row['after']['exclusion_rules']} pend={row['after']['pending_rules']}")
            print(f"   why:    {row['after']['reason'][:260]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
