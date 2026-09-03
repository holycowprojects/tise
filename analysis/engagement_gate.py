"""Does this profile have enough measured attention to ship `visit_engaged` yet?

**This script fits nothing.** It computes counts and stops. That is deliberate and it is
D88's rule: a data-sufficiency gate is set from quantities that carry no score information,
*before* anything is fitted, so there is nothing available to bias the bar with. Every
number here would be identical if the model did not exist.

**The gate is not invented here.** D99 fixed one before the D100 replication ran — at least
**1,000 visits, 20 sessions and 200 labels** — to decide whether one person had enough data
to fit this exact model on. It was declared on 2,148 strangers, months before this profile
had a single attention span, and 822 of those people were excluded by it. Reusing it means
the threshold this profile is measured against was chosen by someone who could not have
seen this profile's numbers. Inventing a fresh one now, with the answer already on screen,
is the failure the pre-registration discipline exists to stop.

**Two translations, both stated because both could quietly mean something else.**

*Visits.* D99 counted `len(events)` for a panelist. Every visit in the GESIS corpus carries
a duration, so there "a visit" and "a visit we can label" were the same thing. Here they are
not: imported history has no dwell and never will (D35, the duration trap), so only
attention-carrying visits can produce a label. The faithful analogue is **dwell-carrying
visits**, and counting all 3,918 events instead would clear a 1,000-visit bar on data that
cannot answer the question.

*Sessions.* Same divergence. The panel's sessions all held labels; here most hold none. The
bootstrap clusters on sessions and a cluster with no rows in it is not a cluster, so the
analogue is **sessions containing at least one label**. Both readings are printed, because
the looser one passes and saying so is the point.

Aggregates only. Categories, never domains. No path outside `data/` is written.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from tise_research.data.load import TiseExport, load_export
from tise_research.features.attention import (
    DEFAULT_MIN_PRIOR_VISITS,
    ENGAGED_FEATURE_SET,
    attention_examples,
)

#: D99's eligibility rule, unchanged. See the module docstring for why it is not re-derived.
MIN_VISITS = 1_000
MIN_SESSIONS = 20
MIN_LABELS = 200


def measure(export: TiseExport) -> dict[str, object]:
    """Every quantity the gate needs, and nothing that depends on a fitted model."""
    events = export.events_with_dwell()
    dwelled = [event for event in events if event.dwell_seconds is not None]

    examples = attention_examples(
        events,
        timeout_seconds=export.session_timeout_seconds,
        feature_set=ENGAGED_FEATURE_SET,
    )
    label_sessions = Counter(item.label.session_id for item in examples)
    by_category = Counter(item.label.subject for item in examples)
    named = {k: v for k, v in by_category.items() if k != "unknown"}

    from tise_research.features.sessions import sessionise

    # Collection rate, over the window attention has actually been recorded in — not since
    # install. Spans began at D96; anything before that is history import, which produces
    # no dwell and would halve the rate by dilution.
    moments = sorted(event.occurred_at for event in dwelled)
    span_days = (moments[-1] - moments[0]).total_seconds() / 86_400 if len(moments) > 1 else 0.0

    return {
        "events": len(events),
        "collection_days": span_days,
        "visits_per_day": (len(dwelled) / span_days) if span_days > 0 else 0.0,
        "spans": len(export.attention),
        "dwelled_visits": len(dwelled),
        "sessions_all": len(sessionise(events, timeout_seconds=export.session_timeout_seconds)),
        "sessions_with_labels": len(label_sessions),
        "labels": len(examples),
        "positives": sum(1 for item in examples if item.label.outcome),
        "by_category": by_category,
        "labels_excluding_unknown": sum(named.values()),
        "largest_category_share": (max(named.values()) / sum(named.values())) if named else 0.0,
        "largest_session_share": (
            max(label_sessions.values()) / len(examples) if examples else 0.0
        ),
    }


def verdicts(measured: dict[str, object]) -> list[tuple[str, int, int, bool]]:
    """`(criterion, observed, required, met)` for each of D99's three."""
    return [
        ("dwell-carrying visits", int(measured["dwelled_visits"]), MIN_VISITS, False),
        (
            "sessions holding a label",
            int(measured["sessions_with_labels"]),
            MIN_SESSIONS,
            False,
        ),
        ("labels", int(measured["labels"]), MIN_LABELS, False),
    ]


def report(measured: dict[str, object]) -> str:
    lines: list[str] = []
    rows = [
        (name, observed, required, observed >= required)
        for name, observed, required, _ in verdicts(measured)
    ]
    passed = all(met for *_, met in rows)

    lines.append("D99's eligibility rule, applied to this profile")
    lines.append("")
    for name, observed, required, met in rows:
        mark = "PASS" if met else "no  "
        share = observed / required
        lines.append(f"  {mark}  {name:<26} {observed:>6,} / {required:,}   ({share:.0%})")
    lines.append("")
    lines.append(f"  GATE: {'PASSES' if passed else 'does not pass'}")
    lines.append("")

    by_category: Counter[str] = measured["by_category"]  # type: ignore[assignment]
    lines.append("Where the labels are")
    lines.append("")
    for category, count in by_category.most_common():
        note = "   (excluded from headlines, D27)" if category == "unknown" else ""
        lines.append(f"  {count:>5,}  {category}{note}")
    lines.append("")
    lines.append(
        f"  {measured['labels_excluding_unknown']:,} labels outside `unknown`, "
        f"{measured['largest_category_share']:.0%} of them in one category"
    )
    lines.append(
        f"  largest single session holds {measured['largest_session_share']:.0%} of all labels"
    )
    lines.append("")

    lines.append("Supporting counts (none of these is the gate)")
    lines.append("")
    lines.append(f"  events stored              {measured['events']:>6,}")
    lines.append(f"  attention spans            {measured['spans']:>6,}")
    per_visit = int(measured["spans"]) / max(1, int(measured["dwelled_visits"]))
    lines.append(
        f"  dwell-carrying visits      {measured['dwelled_visits']:>6,}"
        f"   ({per_visit:.1f} spans each)"
    )
    lines.append(
        f"  sessions, all              {measured['sessions_all']:>6,}"
        f"   ({measured['sessions_with_labels']} hold a label)"
    )
    positives = int(measured["positives"])
    total = int(measured["labels"])
    if total:
        rate = positives / total
        lines.append(f"  base rate                  {rate:>6.1%}   ({positives}/{total})")
    lines.append("")
    lines.append(
        f"  A category needs {DEFAULT_MIN_PRIOR_VISITS} dwelled visits before its "
        f"{DEFAULT_MIN_PRIOR_VISITS + 1}th produces a label, so dwelled visits and labels"
    )
    lines.append("  are not the same count and never will be.")

    rate = float(measured["visits_per_day"])
    if not passed and rate > 0:
        short = MIN_VISITS - int(measured["dwelled_visits"])
        lines.append("")
        lines.append("How far off, at the rate attention is currently arriving")
        lines.append("")
        lines.append(
            f"  {rate:.0f} dwell-carrying visits/day over "
            f"{float(measured['collection_days']):.1f} days of collection"
        )
        lines.append(
            f"  {short:,} short of the visit criterion -> about {short / rate:.0f} days"
        )
        lines.append("")
        lines.append("  Labels are NOT projected here, and the omission is deliberate: they")
        lines.append("  arrive faster than linearly while categories are still crossing their")
        lines.append(
            f"  {DEFAULT_MIN_PRIOR_VISITS}-visit threshold, and a straight line through that "
            "would be a forecast, not a count."
        )
    return "\n".join(lines)


def newest_export(directory: Path) -> Path:
    candidates = sorted(directory.glob("tise-export-*.json"))
    if not candidates:
        raise SystemExit(f"no export in {directory}; export one from the dashboard first")
    return candidates[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "export",
        nargs="?",
        type=Path,
        help="path to a v3 export; defaults to the newest in data/",
    )
    args = parser.parse_args()

    path = args.export if args.export is not None else newest_export(Path("data"))
    export = load_export(path)
    print(f"{path.name}   exported {export.exported_at.isoformat(timespec='seconds')}")
    print()
    print(report(measure(export)))


if __name__ == "__main__":
    main()
