"""k-means, a silhouette, and the two things that stop a clustering from being a Rorschach.

**k-means always returns k clusters.** Hand it pure noise and it partitions the noise, the
silhouette comes out positive, and the cluster profiles can be read as types by anyone
willing to read them that way. Nothing in the algorithm can tell you whether the structure
was there. So this module ships the clustering together with the two checks that can:

* **A null.** Each feature column is permuted independently across rows, which keeps every
  marginal distribution exactly and destroys the correlations between them. Re-clustering
  that gives the silhouette a *structureless* corpus of the same shape and size produces.
  A real silhouette is only interesting relative to that band. This is D24's mandatory
  baseline in the only form it takes for an unsupervised method.
* **Stability.** "Recurring types" is a claim that the same groups come back, not that a
  partition exists. Subsampling and re-clustering measures how often two sessions that
  landed together land together again — which is the property the word *type* asserts and
  the silhouette does not test.

**The seed is declared and never tuned**, exactly as `BOOTSTRAP_SEED` is (D80), and
`test_clustering.py` asserts the reported numbers barely move across other seeds. If that
ever stops holding, the restart count is too low and the seed is doing real work.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "CLUSTER_SEED",
    "DEFAULT_NULL_RUNS",
    "DEFAULT_RESTARTS",
    "DEFAULT_STABILITY_RUNS",
    "Clustering",
    "gaussian_null_band",
    "kmeans",
    "null_silhouette_band",
    "silhouette",
    "stability",
    "standardise",
]

#: Declared, committed, never tuned. See the module docstring.
CLUSTER_SEED = 20260902

#: Random restarts per fit. k-means is initialisation-sensitive; the best-inertia run wins.
DEFAULT_RESTARTS = 10

DEFAULT_NULL_RUNS = 50

DEFAULT_STABILITY_RUNS = 25

#: Share of rows kept in each stability subsample.
STABILITY_FRACTION = 0.8

_MAX_ITERATIONS = 100


@dataclass(frozen=True, slots=True)
class Clustering:
    k: int
    #: Cluster index per row, aligned with the input matrix.
    assignments: tuple[int, ...]
    centroids: tuple[tuple[float, ...], ...]
    inertia: float


def standardise(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Z-score each column. A column that never varies becomes zeros, not a divide by zero.

    That is the honest outcome: a constant column carries no information and must not be
    allowed to dominate a distance simply because its scale was small.
    """
    if not matrix:
        return []
    width = len(matrix[0])
    means: list[float] = []
    scales: list[float] = []
    for index in range(width):
        column = [row[index] for row in matrix]
        mean = sum(column) / len(column)
        variance = sum((value - mean) ** 2 for value in column) / len(column)
        deviation = math.sqrt(variance)
        means.append(mean)
        scales.append(deviation if deviation > 0.0 else 1.0)
    return [
        [(value - mean) / scale for value, mean, scale in zip(row, means, scales, strict=True)]
        for row in matrix
    ]


def _distance_squared(left: Sequence[float], right: Sequence[float]) -> float:
    return sum((a - b) ** 2 for a, b in zip(left, right, strict=True))


def _kmeans_plus_plus(
    matrix: Sequence[Sequence[float]], k: int, rng: random.Random
) -> list[list[float]]:
    centroids = [list(matrix[rng.randrange(len(matrix))])]
    while len(centroids) < k:
        weights = [
            min(_distance_squared(row, centroid) for centroid in centroids)
            for row in matrix
        ]
        total = sum(weights)
        if total <= 0.0:
            # Every remaining point coincides with a centroid. Duplicating one is honest —
            # the alternative is an empty cluster reported as if it held something.
            centroids.append(list(matrix[rng.randrange(len(matrix))]))
            continue
        target = rng.random() * total
        running = 0.0
        for row, weight in zip(matrix, weights, strict=True):
            running += weight
            if running >= target:
                centroids.append(list(row))
                break
    return centroids


def _one_fit(
    matrix: Sequence[Sequence[float]], k: int, rng: random.Random
) -> Clustering:
    centroids = _kmeans_plus_plus(matrix, k, rng)
    assignments = [0] * len(matrix)
    for _ in range(_MAX_ITERATIONS):
        moved = False
        for index, row in enumerate(matrix):
            best = min(
                range(k), key=lambda c: _distance_squared(row, centroids[c])
            )
            if best != assignments[index]:
                assignments[index] = best
                moved = True

        for cluster in range(k):
            members = [
                row for row, assigned in zip(matrix, assignments, strict=True)
                if assigned == cluster
            ]
            if not members:
                # An emptied cluster is re-seeded on the point furthest from its centroid,
                # rather than dropped: returning k-1 clusters under the name k would make
                # every comparison across k dishonest.
                furthest = max(
                    range(len(matrix)),
                    key=lambda i: _distance_squared(matrix[i], centroids[assignments[i]]),
                )
                centroids[cluster] = list(matrix[furthest])
                continue
            centroids[cluster] = [
                sum(values) / len(members) for values in zip(*members, strict=True)
            ]
        if not moved:
            break

    inertia = sum(
        _distance_squared(row, centroids[assigned])
        for row, assigned in zip(matrix, assignments, strict=True)
    )
    return Clustering(
        k=k,
        assignments=tuple(assignments),
        centroids=tuple(tuple(centroid) for centroid in centroids),
        inertia=inertia,
    )


def kmeans(
    matrix: Sequence[Sequence[float]],
    k: int,
    *,
    restarts: int = DEFAULT_RESTARTS,
    seed: int = CLUSTER_SEED,
) -> Clustering:
    """Best-of-`restarts` k-means. Deterministic for a given seed."""
    if k < 2:
        raise ValueError(f"k must be at least 2, got {k}")
    if len(matrix) < k:
        raise ValueError(f"{len(matrix)} rows cannot support {k} clusters")

    rng = random.Random(seed)
    best = _one_fit(matrix, k, rng)
    for _ in range(restarts - 1):
        candidate = _one_fit(matrix, k, rng)
        if candidate.inertia < best.inertia:
            best = candidate
    return best


def silhouette(
    matrix: Sequence[Sequence[float]], assignments: Sequence[int]
) -> float | None:
    """Mean silhouette width. None when fewer than two clusters actually hold rows.

    Returning None rather than 0.0 for a degenerate partition matters: 0.0 reads as "no
    structure was found" and the truth is that nothing was measured.
    """
    clusters: dict[int, list[int]] = {}
    for index, assigned in enumerate(assignments):
        clusters.setdefault(assigned, []).append(index)
    if len(clusters) < 2:
        return None

    scores: list[float] = []
    for index, assigned in enumerate(assignments):
        own = clusters[assigned]
        if len(own) == 1:
            # A singleton has no within-cluster distance to speak of. Scored 0 by the usual
            # convention: neither well placed nor badly.
            scores.append(0.0)
            continue
        cohesion = sum(
            math.sqrt(_distance_squared(matrix[index], matrix[other]))
            for other in own
            if other != index
        ) / (len(own) - 1)
        separation = min(
            sum(
                math.sqrt(_distance_squared(matrix[index], matrix[other]))
                for other in members
            )
            / len(members)
            for cluster, members in clusters.items()
            if cluster != assigned
        )
        widest = max(cohesion, separation)
        scores.append(0.0 if widest == 0.0 else (separation - cohesion) / widest)
    return sum(scores) / len(scores)


def null_silhouette_band(
    matrix: Sequence[Sequence[float]],
    k: int,
    *,
    runs: int = DEFAULT_NULL_RUNS,
    restarts: int = DEFAULT_RESTARTS,
    seed: int = CLUSTER_SEED,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """`(median, low, high)` silhouette on column-permuted copies of the same matrix.

    Permuting each column independently keeps every marginal exactly and destroys the
    joint structure — so this is what a silhouette looks like when a corpus of this shape
    and size contains **no** types at all. A clustering is only interesting above this band.
    """
    rng = random.Random(seed)
    width = len(matrix[0]) if matrix else 0
    scores: list[float] = []
    for _ in range(runs):
        columns = []
        for index in range(width):
            column = [row[index] for row in matrix]
            rng.shuffle(column)
            columns.append(column)
        shuffled = [list(row) for row in zip(*columns, strict=True)]
        fit = kmeans(shuffled, k, restarts=restarts, seed=rng.randrange(1 << 30))
        score = silhouette(shuffled, fit.assignments)
        if score is not None:
            scores.append(score)

    scores.sort()
    tail = (1.0 - level) / 2.0
    return (
        _percentile(scores, 0.5),
        _percentile(scores, tail),
        _percentile(scores, 1.0 - tail),
    )


def _cholesky(matrix: list[list[float]], ridge: float = 1e-9) -> list[list[float]]:
    """Lower-triangular L with L·Lᵀ = matrix. A ridge keeps a singular covariance usable.

    A constant or perfectly collinear column makes the covariance singular, which is a real
    possibility on a small corpus and must not crash the null out of existence — a missing
    null is a report with no baseline, which is the thing D24 forbids.
    """
    size = len(matrix)
    lower = [[0.0] * size for _ in range(size)]
    for row in range(size):
        for column in range(row + 1):
            total = sum(lower[row][k] * lower[column][k] for k in range(column))
            if row == column:
                lower[row][column] = math.sqrt(max(matrix[row][row] - total, ridge))
            else:
                lower[row][column] = (matrix[row][column] - total) / lower[column][column]
    return lower


def gaussian_null_band(
    matrix: Sequence[Sequence[float]],
    k: int,
    *,
    runs: int = DEFAULT_NULL_RUNS,
    restarts: int = DEFAULT_RESTARTS,
    seed: int = CLUSTER_SEED,
    level: float = 0.95,
) -> tuple[float, float, float]:
    """The stronger null: **one** cluster, with the observed correlations kept.

    `null_silhouette_band` permutes each column independently, which destroys the
    correlations between features. That turns out to be too weak a comparison on real
    session data, where visits, domains and duration all move together: correlated features
    concentrate the points near a lower-dimensional surface, which raises the silhouette on
    its own, **with no discrete types anywhere**. A clustering can clear that band by being
    correlated rather than by being clustered, and on Akash's corpora every k did.

    So this draws from a single multivariate normal matching the observed mean and
    covariance — one mode, same shape, same correlations. Excess silhouette above *this*
    band is evidence of more than one mode, which is the claim a "session type" makes. It
    is the Gap statistic's reference distribution, used here for a silhouette.

    Both bands are reported. The permutation band answers "are these features related?"
    and this one answers "is there more than one group?", and they are different questions
    that a single number would conflate.
    """
    rows = len(matrix)
    width = len(matrix[0]) if matrix else 0
    if rows == 0 or width == 0:
        return (0.0, 0.0, 0.0)

    means = [sum(row[index] for row in matrix) / rows for index in range(width)]
    covariance = [
        [
            sum(
                (row[i] - means[i]) * (row[j] - means[j]) for row in matrix
            )
            / rows
            for j in range(width)
        ]
        for i in range(width)
    ]
    lower = _cholesky(covariance)

    rng = random.Random(seed)
    scores: list[float] = []
    for _ in range(runs):
        drawn = []
        for _ in range(rows):
            standard = [rng.gauss(0.0, 1.0) for _ in range(width)]
            drawn.append(
                [
                    means[i] + sum(lower[i][j] * standard[j] for j in range(i + 1))
                    for i in range(width)
                ]
            )
        fit = kmeans(drawn, k, restarts=restarts, seed=rng.randrange(1 << 30))
        score = silhouette(drawn, fit.assignments)
        if score is not None:
            scores.append(score)

    scores.sort()
    tail = (1.0 - level) / 2.0
    return (
        _percentile(scores, 0.5),
        _percentile(scores, tail),
        _percentile(scores, 1.0 - tail),
    )


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = fraction * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    weight = position - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def stability(
    matrix: Sequence[Sequence[float]],
    k: int,
    *,
    runs: int = DEFAULT_STABILITY_RUNS,
    restarts: int = DEFAULT_RESTARTS,
    seed: int = CLUSTER_SEED,
) -> float:
    """How often two rows that co-cluster once co-cluster again, over subsamples.

    Averaged over every pair present in both of two independent subsamples: 1.0 means the
    partition is reproduced exactly, 0.5 is what a coin would give on a two-cluster split.
    **This is the number that tests the word "type"** — a silhouette says a partition is
    tight, and only this says it comes back.
    """
    rng = random.Random(seed)
    size = max(k, int(len(matrix) * STABILITY_FRACTION))
    if size > len(matrix):
        return 0.0

    agreements: list[float] = []
    for _ in range(runs):
        first = _co_assignment(matrix, k, size, rng, restarts)
        second = _co_assignment(matrix, k, size, rng, restarts)
        shared = set(first) & set(second)
        if not shared:
            continue
        agree = sum(1 for pair in shared if first[pair] == second[pair])
        agreements.append(agree / len(shared))
    return sum(agreements) / len(agreements) if agreements else 0.0


def _co_assignment(
    matrix: Sequence[Sequence[float]],
    k: int,
    size: int,
    rng: random.Random,
    restarts: int,
) -> dict[tuple[int, int], bool]:
    indices = rng.sample(range(len(matrix)), size)
    fit = kmeans(
        [matrix[index] for index in indices], k, restarts=restarts, seed=rng.randrange(1 << 30)
    )
    label = dict(zip(indices, fit.assignments, strict=True))
    ordered = sorted(indices)
    return {
        (left, right): label[left] == label[right]
        for position, left in enumerate(ordered)
        for right in ordered[position + 1 :]
    }
