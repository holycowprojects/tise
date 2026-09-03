/**
 * When `visit_engaged` may switch on, answered from this device's own store.
 *
 * `analysis/engagement_gate.py` is the mirror. Neither computes anything fitted: both count,
 * and the counts would be identical if no model existed. That is D88's rule — a data
 * sufficiency gate is measured from quantities carrying no score information, so there is
 * nothing available to bias it with.
 *
 * **The three thresholds are D99's, and this file did not choose them.** They were declared
 * before the D100 replication ran, to decide whether one of 2,148 strangers had enough data
 * to fit this exact model on; 822 of those people were excluded by them. A threshold picked
 * now, with this profile's numbers already on screen, would be the failure pre-registration
 * exists to prevent. `engagement.test.ts` reads the Python file and asserts the two agree,
 * because a copy that can drift is a copy that will.
 *
 * **Why this runs in the extension at all**, rather than living only in the research tier:
 * D101. Attention collection shipped in D96 gated on a permission Chrome never grants at
 * install, so the store stayed empty for two days while every note described collection as
 * running — and the count that would have exposed it existed nowhere a person could see. A
 * gate whose progress is invisible is indistinguishable from a gate that is broken. So this
 * is computed on the device, over the real store, and shown.
 *
 * It also means the label path is *exercised*. `attachDwell` and `attentionExamples` run
 * here every time the popup opens, weeks before any model is trained on their output. Code
 * that cannot run until the day it matters is code nobody has watched work.
 */
import { attachDwell } from "../features/dwell";
import { attentionExamples } from "../features/attention";
import type { AttentionSpan, TiseEvent } from "../types";

/**
 * D99's eligibility rule, unchanged. Mirrored from `analysis/engagement_gate.py`, which
 * mirrors `analysis/replication.py`, which declared them.
 */
export const MIN_VISITS = 1_000;
export const MIN_SESSIONS = 20;
export const MIN_LABELS = 200;

export interface Criterion {
  /** In the person's words. This reaches the popup unchanged. */
  readonly name: string;
  readonly observed: number;
  readonly required: number;
  readonly met: boolean;
}

export interface EngagementGate {
  readonly criteria: readonly Criterion[];
  readonly met: boolean;
  /** Dwell-carrying visits. Not all visits — imported history can never have dwell (D35). */
  readonly dwelledVisits: number;
  readonly sessionsWithLabels: number;
  readonly labels: number;
  /** Labels per category, so a person can see *why* it is not ready, not only that it is not. */
  readonly byCategory: ReadonlyMap<string, number>;
}

/**
 * Where this profile stands.
 *
 * Two translations, both of which could go on meaning something plausible after they stop
 * being right, so both are named here as they are in the Python mirror:
 *
 * *Visits* means **dwell-carrying** visits. Every visit in the corpus D99 was declared on
 * had a duration, so there "a visit" and "a visit that can be labelled" were one number.
 * Here imported history has no dwell and never will, so counting all events would clear a
 * 1,000-visit bar on data that cannot answer the question.
 *
 * *Sessions* means sessions **holding at least one label**. The bootstrap clusters on
 * sessions, and a cluster with no rows in it is not a cluster.
 */
export function engagementGate(
  events: readonly TiseEvent[],
  spans: readonly AttentionSpan[],
  timeoutSeconds: number,
): EngagementGate {
  const joined = attachDwell(events, spans);
  const dwelledVisits = joined.filter((event) => event.dwellSeconds !== null).length;

  const examples = attentionExamples(joined, { timeoutSeconds });
  const sessions = new Set(examples.map((example) => example.label.sessionId));

  const byCategory = new Map<string, number>();
  for (const example of examples) {
    const subject = example.label.subject;
    byCategory.set(subject, (byCategory.get(subject) ?? 0) + 1);
  }

  const criteria: Criterion[] = [
    { name: "visits with measured attention", observed: dwelledVisits, required: MIN_VISITS },
    { name: "sittings holding a label", observed: sessions.size, required: MIN_SESSIONS },
    { name: "labelled visits", observed: examples.length, required: MIN_LABELS },
  ].map((criterion) => ({ ...criterion, met: criterion.observed >= criterion.required }));

  return {
    criteria,
    met: criteria.every((criterion) => criterion.met),
    dwelledVisits,
    sessionsWithLabels: sessions.size,
    labels: examples.length,
    byCategory,
  };
}

/**
 * The gate as one sentence, for the popup.
 *
 * Derived rather than written, because the sentence it replaces was written: *"Predictions
 * need roughly ten measured visits per topic before they begin"* shipped in D101 and was
 * wrong by more than an order of magnitude. Ten per topic is when a *label* becomes
 * possible — `DEFAULT_MIN_PRIOR_VISITS` — and it says nothing about when a model may be
 * trusted. Same defect as D114's popup subtitle: a number typed next to a system that keeps
 * the real one somewhere else.
 */
export function gateSentence(gate: EngagementGate): string {
  if (gate.met) {
    return (
      `Ready — ${gate.labels.toLocaleString()} labelled visits across ` +
      `${gate.sessionsWithLabels} sittings.`
    );
  }
  const furthest = [...gate.criteria]
    .filter((criterion) => !criterion.met)
    .sort((a, b) => a.observed / a.required - b.observed / b.required)[0];
  if (furthest === undefined) return "Ready.";
  const short = (furthest.required - furthest.observed).toLocaleString();
  return (
    `Not yet — ${furthest.observed.toLocaleString()} of ${furthest.required.toLocaleString()} ` +
    `${furthest.name}, so ${short} to go.`
  );
}
