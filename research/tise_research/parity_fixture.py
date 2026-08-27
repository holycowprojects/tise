"""Build the parity fixture — the oracle TypeScript must reproduce exactly.

    uv run python -m tise_research.parity_fixture

Writes `research/fixtures/parity_events.json` (input) and `parity_expected.json`
(Python's answer). At T9 the TypeScript implementation runs over the same input and its
output is compared to the same expected file. If they disagree, one of them is wrong and
the build stops.

**The events are synthetic and hand-designed, never real browsing.** Two reasons: this
file is committed and public, and a fixture must exercise the exact boundaries a real
history rarely contains — a gap landing precisely on the session timeout, a recurrence
landing precisely on the horizon. SPEC.md permits synthetic data as a test fixture and
forbids it as a benchmark; this is the permitted use.

Every case below is here on purpose:

* a gap of exactly the timeout, which must **not** split a session
* a gap one second longer, which must
* several categories inside one session
* a domain resolved by the map, one by a keyword rule, one overridden by the user, and
  one that resolves to `unknown`
* a recurrence inside the horizon and one outside it
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tise_research.categories import load_category_map
from tise_research.eval.abstain import (
    DEFAULT_TARGET_ACCURACY,
    accuracy_coverage_curve,
    select_threshold,
    wilson_lower_bound,
)
from tise_research.features.events import Event
from tise_research.features.labels import return_24h_labels
from tise_research.features.resolver import resolve
from tise_research.features.sessions import sessionise
from tise_research.features.vector import FEATURE_NAMES, FEATURE_SET, compute_features
from tise_research.models.calibrate import (
    CALIBRATION_METHOD,
    CALIBRATION_SPEC,
    CALIBRATION_VERSION,
    apply_calibration,
    fit_platt,
    logit,
)
from tise_research.models.logreg import (
    DEFAULT_SPEC,
    predict_proba,
    step_size,
    train,
)
from tise_research.models.prep import design_columns, fit_preprocessor
from tise_research.models.transition import fit_transition_table, primary_category

#: research/tise_research/parity_fixture.py -> repo root is three parents up.
REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "research" / "fixtures"

TIMEOUT_SECONDS = 1800.0
HORIZON_HOURS = 24.0

#: `nothing-here.example` would resolve to `unknown`; the override must win.
OVERRIDES = {"nothing-here.example": "work"}


def _at(day: int, hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 6, day, hour, minute, second, tzinfo=UTC)


#: (occurred_at, domain). Order is deliberate; the pipeline sorts anyway.
RAW_EVENTS: list[tuple[datetime, str]] = [
    # --- session 1: three events, including a gap of EXACTLY the timeout -------------
    (_at(1, 9, 0), "youtube.com"),          # map -> video
    (_at(1, 9, 20), "youtube.com"),         # +20m, same session
    (_at(1, 9, 50), "google.com"),          # +30m exactly -> still the same session
    # --- session 2: starts one second past the timeout ------------------------------
    (_at(1, 10, 20, 1), "github.com"),      # +30m01s -> new session
    (_at(1, 10, 25), "someministry.gov.in"),  # keyword rule -> government
    (_at(1, 10, 30), "nothing-here.example"),  # override -> work
    (_at(1, 10, 35), "personal-site.example"),  # nothing matches -> unknown
    # --- session 3: next day, inside the 24h horizon of session 1 -------------------
    (_at(2, 9, 0), "youtube.com"),
    (_at(2, 9, 5), "google.com"),
    # --- session 4: two days later, OUTSIDE the horizon of session 2 ----------------
    (_at(3, 12, 0), "github.com"),
    # --- T10 extension: a run of `dev` sessions, so `priorReturnRate` has something to
    # average over. Everything below is strictly more than 24 hours after session 4
    # closed, so **no existing session or label changes** — the freeze holds and the diff
    # is additive. Mixed outcomes on purpose: a rate of 0 or 1 would not distinguish a
    # correct implementation from one that returns a constant.
    (_at(4, 13, 0), "github.com"),   # no return inside 24h of session 4 -> a miss
    (_at(5, 9, 0), "github.com"),    # inside 24h of the above -> a hit
    (_at(6, 20, 0), "github.com"),   # outside 24h of the above -> a miss
    (_at(7, 8, 0), "github.com"),    # inside 24h of the above -> a hit
    (_at(9, 15, 0), "github.com"),   # a gap, so the last session's horizon is unresolved
    (_at(10, 16, 0), "youtube.com"),
    (_at(10, 16, 5), "github.com"),
    # --- T11 extension: a recurrence landing EXACTLY on the horizon -----------------
    # Found by breaking the label boundary from `<=` to `<` and watching the whole suite
    # stay green. The header above has always claimed to cover "a recurrence inside the
    # horizon and one outside it", and it does — but never one *on* it, so the boundary
    # itself was unobservable and either language could have had it wrong.
    #
    # Both events are more than 24 hours after the day-10 session closed, so no existing
    # label changes: the day-10 `video` and `dev` labels stay negative, and the diff is
    # additive exactly as the T10 extension was.
    (_at(12, 10, 0), "youtube.com"),  # a one-event session closing at 10:00
    (_at(13, 10, 0), "youtube.com"),  # +24h to the second -> positive only if `<=`
]


def build_events() -> list[Event]:
    category_map = load_category_map()
    events: list[Event] = []
    for index, (occurred_at, domain) in enumerate(RAW_EVENTS):
        resolution = resolve(domain, category_map=category_map, overrides=OVERRIDES)
        events.append(
            Event(
                event_id=f"evt-{index:03d}",
                occurred_at=occurred_at,
                domain=domain,
                category=resolution.category,
                transition="link",
                dwell_seconds=None,
                source="import",
            )
        )
    return events


def build_input_document() -> dict:
    """The input side. Deliberately carries **no category** — resolving the domain is
    part of what parity checks, so handing TypeScript the answer would defeat it."""
    return {
        "note": [
            "Parity fixture INPUT. Synthetic, hand-designed, never real browsing.",
            "TypeScript must reproduce parity_expected.json from exactly this.",
            "Events carry no category: resolving the domain is part of what is compared.",
            "Regenerate with: uv run python -m tise_research.parity_fixture",
        ],
        "categoryMapVersion": load_category_map().version,
        "timeoutSeconds": TIMEOUT_SECONDS,
        "horizonHours": HORIZON_HOURS,
        "overrides": OVERRIDES,
        "events": [
            {
                "eventId": f"evt-{index:03d}",
                "occurredAt": occurred_at.isoformat(),
                "domain": domain,
                "transition": "link",
                "dwellSeconds": None,
                "source": "import",
            }
            for index, (occurred_at, domain) in enumerate(RAW_EVENTS)
        ],
    }


def build_expected_document() -> dict:
    category_map = load_category_map()
    events = build_events()

    resolutions = []
    for _, domain in RAW_EVENTS:
        resolution = resolve(domain, category_map=category_map, overrides=OVERRIDES)
        entry = {
            "domain": domain,
            "category": resolution.category,
            "source": resolution.source,
        }
        if entry not in resolutions:
            resolutions.append(entry)

    sessions = [
        {
            "sessionId": session.session_id,
            "startedAt": session.started_at.isoformat(),
            "endedAt": session.ended_at.isoformat(),
            "durationSeconds": session.duration_seconds,
            "eventIds": [event.event_id for event in session.events],
            "categories": sorted(session.categories),
        }
        for session in sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    ]

    labels = [
        {
            "target": label.target,
            "subject": label.subject,
            "windowEnd": label.window_end.isoformat(),
            "outcome": label.outcome,
            "horizonHours": label.horizon_hours,
            "sessionId": label.session_id,
        }
        for label in return_24h_labels(
            events, timeout_seconds=TIMEOUT_SECONDS, horizon_hours=HORIZON_HOURS
        )
    ]

    # One feature row per label, aligned by index. This is the shape the model consumes:
    # a vector computed at the instant its label became decidable, and never after.
    label_objects = return_24h_labels(
        events, timeout_seconds=TIMEOUT_SECONDS, horizon_hours=HORIZON_HOURS
    )
    feature_rows = [
        compute_features(
            events,
            label.subject,
            window_end=label.window_end,
            timeout_seconds=TIMEOUT_SECONDS,
            horizon_hours=HORIZON_HOURS,
        )
        for label in label_objects
    ]
    features = [
        {
            "subject": row.subject,
            "windowEnd": row.window_end.isoformat(),
            "compat": row.compat,
            # Written in FEATURE_NAMES order. The order is part of the contract: it
            # is the column order of any matrix built from these rows.
            "values": {name: row.values[name] for name in FEATURE_NAMES},
        }
        for row in feature_rows
    ]

    unknown_count = sum(1 for event in events if event.category == "unknown")

    return {
        "note": [
            "Parity fixture EXPECTED OUTPUT, produced by the Python implementation.",
            "TypeScript must match this exactly. A mismatch means one side is wrong;",
            "it is never a reason to regenerate this file without understanding why.",
        ],
        "categoryMapVersion": category_map.version,
        "timeoutSeconds": TIMEOUT_SECONDS,
        "horizonHours": HORIZON_HOURS,
        "featureSet": FEATURE_SET,
        "featureNames": list(FEATURE_NAMES),
        "resolutions": resolutions,
        "sessions": sessions,
        "labels": labels,
        "features": features,
        "model": build_model_section(
            events, feature_rows, [label.outcome for label in label_objects]
        ),
        "summary": {
            "eventCount": len(events),
            "sessionCount": len(sessions),
            "labelCount": len(labels),
            "positiveCount": sum(1 for label in labels if label["outcome"]),
            "unknownEventCount": unknown_count,
        },
    }


def _calibration_section(raw: list[float], outcomes: list[bool]) -> dict:
    """The T12 oracle: Platt scaling and the abstention threshold.

    Fitted on the same rows the model was fitted on, which would be indefensible as a
    benchmark and is exactly right here: this section compares arithmetic between two
    languages, not the quality of a calibrator. The real split lives in
    `eval/calibrate.py` and in the extension's trainer.

    Both branches of the threshold rule are exercised. At the default `min_answered` the
    eighteen fixture labels cannot qualify, so `policy` carries `targetMet: false` — the
    "answer nothing" path, which is the one the author's own browsing actually takes. A
    second policy with a lower floor exercises the qualifying path so neither is left
    untested.
    """
    calibrator = fit_platt(raw, outcomes)
    calibrated = [apply_calibration(calibrator, p) for p in raw]

    strict = select_threshold(outcomes, calibrated)
    lenient = select_threshold(
        outcomes, calibrated, target_accuracy=0.60, min_answered=5
    )
    naive = select_threshold(
        outcomes, calibrated, target_accuracy=0.60, min_answered=5, confidence_z=0.0
    )

    def as_dict(policy) -> dict | None:
        if policy is None:
            return None
        return {
            "threshold": policy.threshold,
            "targetAccuracy": policy.target_accuracy,
            "accuracy": policy.accuracy,
            "accuracyLowerBound": policy.accuracy_lower_bound,
            "coverage": policy.coverage,
            "nValidation": policy.n_validation,
            "confidenceZ": policy.confidence_z,
            "targetMet": policy.target_met,
        }

    return {
        "method": CALIBRATION_METHOD,
        "version": CALIBRATION_VERSION,
        "spec": {
            "iterations": CALIBRATION_SPEC.iterations,
            "l2": CALIBRATION_SPEC.l2,
            "chunkIterations": CALIBRATION_SPEC.chunk_iterations,
            "stepScale": CALIBRATION_SPEC.step_scale,
        },
        # Written out so a logit bug and an optimiser bug stay distinguishable.
        "logits": [logit(p) for p in raw],
        # The clamp is unobservable through `logits` alone: a fitted model never emits a
        # raw 0 or 1, so removing the clamp broke exactly one TypeScript unit test and no
        # parity test at all. The same gap D61 found at the horizon boundary, so it is
        # closed the same way — by putting the boundary in the fixture.
        "logitCases": [
            {"probability": p, "logit": logit(p)}
            for p in (0.0, 1e-15, 0.5, 1.0 - 1e-15, 1.0)
        ],
        "calibrator": {
            "a": calibrator.a,
            "b": calibrator.b,
            "nCalibration": calibrator.n_calibration,
            "nPositive": calibrator.n_positive,
            "gradientNorm": calibrator.gradient_norm,
        },
        "calibrated": calibrated,
        "targetAccuracy": DEFAULT_TARGET_ACCURACY,
        "policy": as_dict(strict),
        "lenientPolicy": as_dict(lenient),
        "lenientNaivePolicy": as_dict(naive),
        "coverageCurve": [
            {
                "threshold": point.threshold,
                "coverage": point.coverage,
                "answered": point.answered,
                "accuracy": point.accuracy,
                "abstainedAccuracy": point.abstained_accuracy,
            }
            for point in accuracy_coverage_curve(outcomes, calibrated)
        ],
        # A handful of bounds, so the Wilson arithmetic is compared directly rather than
        # only through whichever thresholds happen to be selected.
        "wilsonCases": [
            {"successes": s, "total": n, "z": z, "bound": wilson_lower_bound(s, n, z=z)}
            for s, n, z in (
                (90, 100, 1.645),
                (18, 20, 1.645),
                (450, 500, 1.645),
                (20, 20, 1.645),
                (0, 20, 1.645),
                (90, 100, 0.0),
                (0, 0, 1.645),
            )
        ],
    }


def build_model_section(events: list[Event], feature_rows: list, outcomes: list[bool]) -> dict:
    """The T11 oracle: preprocessing, coefficients, probabilities and the transition table.

    Fitted on all thirteen fixture rows with no train/test split, which would be
    indefensible as a benchmark and is exactly right as a parity target: the question here
    is whether two implementations do the same arithmetic, not whether the arithmetic
    generalises. The real evaluation runs on real browsing through
    `tise_research.eval.backtest`, where the folds are chronological.

    The intermediate matrix is written out as well as the final weights. If only the
    weights were compared, a preprocessing bug and an optimiser bug would be
    indistinguishable — and one thousand gradient steps is a long way to bisect by hand.
    """
    preprocessor = fit_preprocessor(feature_rows)
    matrix = preprocessor.matrix(feature_rows)
    state = train(matrix, outcomes, spec=DEFAULT_SPEC, n_columns=len(design_columns()))

    sessions = sessionise(events, timeout_seconds=TIMEOUT_SECONDS)
    table = fit_transition_table(sessions)

    return {
        "note": [
            "Fitted on every row, with no split. That is deliberate: this section",
            "compares arithmetic between two languages, and is not a benchmark.",
        ],
        "designColumns": list(design_columns()),
        "preprocessor": {
            "fills": list(preprocessor.fills),
            "means": list(preprocessor.means),
            "scales": list(preprocessor.scales),
        },
        "matrix": matrix,
        "outcomes": outcomes,
        "spec": {
            "iterations": DEFAULT_SPEC.iterations,
            "l2": DEFAULT_SPEC.l2,
            "chunkIterations": DEFAULT_SPEC.chunk_iterations,
            "stepScale": DEFAULT_SPEC.step_scale,
        },
        # Derived from the matrix rather than declared, so it is part of what parity
        # compares: a mirror that reproduced the weights with a different step would be
        # agreeing by coincidence.
        "stepSize": step_size(matrix, DEFAULT_SPEC),
        "logreg": {
            "weights": list(state.weights),
            "bias": state.bias,
            "iterationsDone": state.iterations_done,
            "gradientNorm": state.gradient_norm,
        },
        "predictions": [predict_proba(state, row) for row in matrix],
        "calibration": _calibration_section(
            [predict_proba(state, row) for row in matrix], outcomes
        ),
        "transition": {
            "primaries": [primary_category(session) for session in sessions],
            "vocabulary": list(table.vocabulary),
            "counts": table.counts,
            "marginal": table.marginal,
            "smoothing": table.smoothing,
            # One distribution per known starting category, plus the fallback a category
            # nobody has ever started from must fall back to.
            "distributions": {
                category: table.distribution(category) for category in table.vocabulary
            },
            "unseenDistribution": table.distribution("__never-seen__"),
        },
    }


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {path.relative_to(REPO_ROOT)}")


def main() -> int:
    _write(FIXTURE_DIR / "parity_events.json", build_input_document())
    expected = build_expected_document()
    _write(FIXTURE_DIR / "parity_expected.json", expected)

    summary = expected["summary"]
    print(
        f"  {summary['eventCount']} events -> {summary['sessionCount']} sessions -> "
        f"{summary['labelCount']} labels ({summary['positiveCount']} positive)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
