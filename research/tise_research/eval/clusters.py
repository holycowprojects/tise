"""Can `unknown` be split into clusters worth naming? (T19, for D88's T10b.)

`unknown` holds roughly a fifth of Chrome's labels and is discarded from every published
number, because a card reading "unknown · 71%" is unpresentable. It is large *by design*:
the shipped map excludes employer, school, council and neighbourhood domains, because that
file is public and a domain list is a profile. So the user's actual life lands there.

The only route that can shrink it is on-device clustering, and this measures whether that
route exists at all before anything is built on it.

**Deliberately simple, and stdlib only.** Session co-occurrence, Jaccard similarity, a
threshold, connected components. No scikit-learn, even though it is now installed for the
tournament: whatever is measured here has to run in a browser service worker in TypeScript
with one runtime dependency, so measuring with an algorithm that cannot ship would answer a
question about a different system. It is also deterministic, which a k-means with a random
init would not be.

**Stability is the number that matters, not cluster count.** Any threshold produces
clusters. The question is whether the same domains group together on data the clustering
did not see — so the corpus is halved chronologically, clustered independently, and the two
partitions compared. A clustering that reorganises itself every fortnight cannot be shown
to a user and asked for a name.

No domain is ever written to a published report. Aggregates only (SPEC.md invariant 2).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from tise_research.features.events import Event
from tise_research.features.sessions import sessionise

__all__ = [
    "DEFAULT_MIN_SESSIONS",
    "DEFAULT_THRESHOLD",
    "ClusterStats",
    "cluster_domains",
    "cluster_stats",
    "partition_agreement",
]

#: Jaccard similarity two domains need before they are joined. Declared, not tuned: it is
#: the midpoint of the range, and T19 reports the sensitivity around it rather than
#: searching for the value that produces the nicest answer.
DEFAULT_THRESHOLD = 0.5

#: A domain seen in fewer sessions than this cannot be clustered reliably and is left out.
DEFAULT_MIN_SESSIONS = 3

UNKNOWN = "unknown"


def _sessions_by_domain(
    events: Sequence[Event], *, timeout_seconds: float, only_unknown: bool
) -> dict[str, set[int]]:
    """Which sessions each domain appeared in."""
    membership: dict[str, set[int]] = defaultdict(set)
    for index, session in enumerate(sessionise(events, timeout_seconds=timeout_seconds)):
        for event in session.events:
            if only_unknown and event.category != UNKNOWN:
                continue
            membership[event.domain].add(index)
    return membership


def cluster_domains(
    events: Sequence[Event],
    *,
    timeout_seconds: float,
    threshold: float = DEFAULT_THRESHOLD,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
    only_unknown: bool = True,
) -> list[set[str]]:
    """Group domains that keep turning up in the same sessions.

    Connected components rather than a similarity-ordered merge: it is order-independent,
    so the result cannot depend on which domain happened to be processed first, and it is
    about fifteen lines in any language.
    """
    membership = {
        domain: sessions
        for domain, sessions in _sessions_by_domain(
            events, timeout_seconds=timeout_seconds, only_unknown=only_unknown
        ).items()
        if len(sessions) >= min_sessions
    }

    adjacency: dict[str, set[str]] = {domain: set() for domain in membership}
    for left, right in combinations(sorted(membership), 2):
        a, b = membership[left], membership[right]
        union = len(a | b)
        if union and len(a & b) / union >= threshold:
            adjacency[left].add(right)
            adjacency[right].add(left)

    seen: set[str] = set()
    clusters: list[set[str]] = []
    for domain in sorted(adjacency):
        if domain in seen:
            continue
        stack = [domain]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        seen |= component
        if len(component) > 1:
            clusters.append(component)
    return sorted(clusters, key=lambda item: (-len(item), sorted(item)[0]))


def partition_agreement(left: Sequence[set[str]], right: Sequence[set[str]]) -> float | None:
    """Rand-style agreement over domain pairs the two partitions both saw.

    For every pair of domains present in both halves, do the two partitions agree on
    whether they belong together? Restricted to the shared domains, because a domain that
    only exists in one half says nothing about stability.
    """
    shared = {d for cluster in left for d in cluster} & {
        d for cluster in right for d in cluster
    }
    if len(shared) < 2:
        return None

    def lookup(partition: Sequence[set[str]]) -> dict[str, int]:
        return {
            domain: index
            for index, cluster in enumerate(partition)
            for domain in cluster
        }

    a, b = lookup(left), lookup(right)
    agree = total = 0
    for one, two in combinations(sorted(shared), 2):
        total += 1
        if (a.get(one) == a.get(two)) == (b.get(one) == b.get(two)):
            agree += 1
    return agree / total if total else None


@dataclass(frozen=True, slots=True)
class ClusterStats:
    unknown_domains: int
    unknown_events: int
    clusterable_domains: int
    clusters: int
    clustered_domains: int
    #: Share of `unknown` **events** that a cluster would now name. This is the number
    #: that says how much of the bucket is recoverable — domain count overweights the
    #: long tail of sites visited twice.
    events_covered: float | None
    largest_cluster: int
    #: Pair agreement between the two chronological halves. The stability number.
    half_agreement: float | None


def cluster_stats(
    events: Sequence[Event],
    *,
    timeout_seconds: float,
    threshold: float = DEFAULT_THRESHOLD,
    min_sessions: int = DEFAULT_MIN_SESSIONS,
) -> ClusterStats:
    unknown = [event for event in events if event.category == UNKNOWN]
    domains = {event.domain for event in unknown}

    membership = _sessions_by_domain(
        events, timeout_seconds=timeout_seconds, only_unknown=True
    )
    clusterable = sum(1 for sessions in membership.values() if len(sessions) >= min_sessions)

    clusters = cluster_domains(
        events,
        timeout_seconds=timeout_seconds,
        threshold=threshold,
        min_sessions=min_sessions,
    )
    clustered = {domain for cluster in clusters for domain in cluster}
    covered = sum(1 for event in unknown if event.domain in clustered)

    ordered = sorted(events, key=lambda event: event.occurred_at)
    midpoint = len(ordered) // 2
    agreement = None
    if midpoint > 1:
        first = cluster_domains(
            ordered[:midpoint],
            timeout_seconds=timeout_seconds,
            threshold=threshold,
            min_sessions=min_sessions,
        )
        second = cluster_domains(
            ordered[midpoint:],
            timeout_seconds=timeout_seconds,
            threshold=threshold,
            min_sessions=min_sessions,
        )
        agreement = partition_agreement(first, second)

    return ClusterStats(
        unknown_domains=len(domains),
        unknown_events=len(unknown),
        clusterable_domains=clusterable,
        clusters=len(clusters),
        clustered_domains=len(clustered),
        events_covered=(covered / len(unknown)) if unknown else None,
        largest_cluster=max((len(c) for c in clusters), default=0),
        half_agreement=agreement,
    )
