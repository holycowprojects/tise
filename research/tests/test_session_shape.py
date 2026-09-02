"""T-E — session shape features and the clustering that consumes them (D95).

The claim worth testing is not that k-means runs. It is that the two checks around it can
**fail**: a null band that never sits below a real silhouette, or a stability number that
comes out high on noise, would make the whole analysis unfalsifiable. So the tests here run
both against corpora built to have structure and corpora built to have none.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest
from tise_research.features.events import Event
from tise_research.features.session_shape import (
    SESSION_FEATURES,
    session_shapes,
)
from tise_research.features.sessions import sessionise
from tise_research.models.clustering import (
    kmeans,
    null_silhouette_band,
    silhouette,
    stability,
    standardise,
)

START = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)
TIMEOUT = 1800.0


def event(
    minutes: float,
    domain: str = "a.example",
    category: str = "video",
    transition: str = "link",
) -> Event:
    return Event(
        event_id=f"e-{minutes}-{domain}-{category}",
        occurred_at=START + timedelta(minutes=minutes),
        domain=domain,
        category=category,
        transition=transition,
        dwell_seconds=None,
        source="import",
    )


# --------------------------------------------------------------------------------------
# The features
# --------------------------------------------------------------------------------------


def test_one_shape_per_session_in_order() -> None:
    events = [event(0), event(5), event(600), event(605)]
    sessions = sessionise(events, timeout_seconds=TIMEOUT)
    shapes = session_shapes(sessions)

    assert len(shapes) == len(sessions) == 2
    assert [shape.session_id for shape in shapes] == [s.session_id for s in sessions]
    assert all(len(shape.values) == len(SESSION_FEATURES) for shape in shapes)


def test_every_feature_is_bounded() -> None:
    """Everything unbounded is saturated (D81), so a long session cannot dominate a distance."""
    events = [event(index * 0.5, domain=f"d{index}.example") for index in range(200)]
    shapes = session_shapes(sessionise(events, timeout_seconds=TIMEOUT))
    for shape in shapes:
        assert all(0.0 <= value <= 1.0 for value in shape.values)


def test_repeat_rate_separates_reloading_from_wandering() -> None:
    reloading = session_shapes(
        sessionise([event(i, domain="a.example") for i in range(10)], timeout_seconds=TIMEOUT)
    )[0]
    wandering = session_shapes(
        sessionise(
            [event(i, domain=f"d{i}.example") for i in range(10)], timeout_seconds=TIMEOUT
        )
    )[0]
    index = SESSION_FEATURES.index("domainRepeatRate")

    assert reloading.values[index] == pytest.approx(0.9)
    assert wandering.values[index] == pytest.approx(0.0)


def test_evenness_is_zero_for_one_category_and_one_for_a_balanced_split() -> None:
    index = SESSION_FEATURES.index("categoryEvenness")

    single = session_shapes(
        sessionise([event(i, category="video") for i in range(8)], timeout_seconds=TIMEOUT)
    )[0]
    assert single.values[index] == 0.0

    balanced = session_shapes(
        sessionise(
            [event(i, category="video" if i % 2 else "news") for i in range(8)],
            timeout_seconds=TIMEOUT,
        )
    )[0]
    assert balanced.values[index] == pytest.approx(1.0)


def test_evenness_and_category_count_are_different_questions() -> None:
    """A lopsided three-category session is diverse and uneven; collapsing them loses that."""
    events = [event(i, category="video") for i in range(10)]
    events += [event(11, category="news"), event(12, category="dev")]
    shape = session_shapes(sessionise(events, timeout_seconds=TIMEOUT))[0]

    evenness = shape.values[SESSION_FEATURES.index("categoryEvenness")]
    count = shape.values[SESSION_FEATURES.index("categoryCount")]
    assert 0.0 < evenness < 0.7
    assert count > 0.0


def test_transition_shares_are_shares() -> None:
    events = [event(i, transition="typed" if i < 3 else "link") for i in range(10)]
    shape = session_shapes(sessionise(events, timeout_seconds=TIMEOUT))[0]

    assert shape.values[SESSION_FEATURES.index("typedShare")] == pytest.approx(0.3)
    assert shape.values[SESSION_FEATURES.index("linkShare")] == pytest.approx(0.7)


def test_time_of_day_is_carried_but_not_a_clustering_feature() -> None:
    """Held out deliberately — see the module docstring. A clustering handed the clock
    recovers morning-versus-evening and presents it as a discovery about session types."""
    shape = session_shapes(sessionise([event(0), event(4)], timeout_seconds=TIMEOUT))[0]

    assert shape.started_hour == 9
    assert shape.is_weekend is False
    assert "hourSin" not in SESSION_FEATURES
    assert "isWeekend" not in SESSION_FEATURES


def test_raw_counts_are_carried_for_the_report() -> None:
    """A saturated 0.71 means nothing to a reader; "17 visits" does."""
    events = [event(i, domain=f"d{i % 3}.example") for i in range(9)]
    shape = session_shapes(sessionise(events, timeout_seconds=TIMEOUT))[0]

    assert shape.visits == 9
    assert shape.domains == 3
    assert shape.duration_minutes == pytest.approx(8.0)


def test_no_sessions_produces_nothing() -> None:
    assert session_shapes([]) == []


# --------------------------------------------------------------------------------------
# The clustering, and the checks that have to be able to fail
# --------------------------------------------------------------------------------------


def two_blobs(n: int = 60, spread: float = 0.05) -> list[list[float]]:
    rng = random.Random(7)
    return [
        [rng.gauss(0.0 if index < n // 2 else 4.0, spread) for _ in range(3)]
        for index in range(n)
    ]


def noise(n: int = 60) -> list[list[float]]:
    rng = random.Random(11)
    return [[rng.random() for _ in range(3)] for _ in range(n)]


def test_kmeans_recovers_two_obvious_blobs() -> None:
    matrix = two_blobs()
    fit = kmeans(matrix, 2)

    assert len(set(fit.assignments)) == 2
    first_half = set(fit.assignments[:30])
    second_half = set(fit.assignments[30:])
    assert len(first_half) == 1 and len(second_half) == 1
    assert first_half != second_half


def test_kmeans_is_deterministic_for_a_seed() -> None:
    matrix = noise()
    assert kmeans(matrix, 3).assignments == kmeans(matrix, 3).assignments


def test_the_seed_is_not_doing_real_work() -> None:
    """Mirrors `test_intervals.py`'s seed check. If this fails, restarts are too few."""
    matrix = two_blobs()
    scores = [
        silhouette(matrix, kmeans(matrix, 2, seed=seed).assignments)
        for seed in (1, 20260902, 999, 41234)
    ]
    assert all(score is not None for score in scores)
    assert max(scores) - min(scores) < 0.01  # type: ignore[type-var]


def test_kmeans_refuses_more_clusters_than_rows() -> None:
    with pytest.raises(ValueError, match="cannot support"):
        kmeans([[0.0], [1.0]], 3)


def test_kmeans_refuses_k_below_two() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        kmeans(noise(), 1)


def test_silhouette_is_high_on_blobs_and_low_on_noise() -> None:
    blobs = two_blobs()
    flat = noise()

    separated = silhouette(blobs, kmeans(blobs, 2).assignments)
    unstructured = silhouette(flat, kmeans(flat, 2).assignments)

    assert separated is not None and unstructured is not None
    assert separated > 0.9
    assert unstructured < 0.5
    assert separated > unstructured


def test_silhouette_is_none_when_only_one_cluster_holds_rows() -> None:
    """None rather than 0.0 — zero reads as "no structure found" when nothing was measured."""
    assert silhouette([[0.0], [1.0], [2.0]], [0, 0, 0]) is None


def test_the_null_band_sits_below_real_structure_and_beside_noise() -> None:
    """The check that makes the whole analysis falsifiable.

    On blobs the observed silhouette must clear the null's upper bound. On noise it must
    not — a null that is always beaten would certify any clustering whatsoever.
    """
    blobs = two_blobs()
    observed = silhouette(blobs, kmeans(blobs, 2).assignments)
    _, _, high = null_silhouette_band(blobs, 2, runs=15)
    assert observed is not None and observed > high

    flat = noise()
    flat_observed = silhouette(flat, kmeans(flat, 2).assignments)
    _, flat_low, flat_high = null_silhouette_band(flat, 2, runs=15)
    assert flat_observed is not None
    assert flat_low <= flat_observed <= flat_high, (
        "noise clustered against a null built from noise must land inside the band"
    )


def test_stability_is_high_on_blobs_and_lower_on_noise() -> None:
    blobs = two_blobs()
    flat = noise()

    assert stability(blobs, 2, runs=6) > 0.95
    assert stability(flat, 2, runs=6) < stability(blobs, 2, runs=6)


def test_standardise_leaves_a_constant_column_as_zeros() -> None:
    """Not a divide by zero, and not a column that dominates a distance for having no scale."""
    matrix = standardise([[1.0, 5.0], [2.0, 5.0], [3.0, 5.0]])
    assert [row[1] for row in matrix] == [0.0, 0.0, 0.0]
    assert [row[0] for row in matrix] != [0.0, 0.0, 0.0]
