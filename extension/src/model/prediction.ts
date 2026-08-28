/**
 * The prediction record. Schema fixed by SPEC.md; this file adds the parts SPEC left open.
 *
 * **A warning about `windowEnd`, because two things in this codebase share the name and
 * mean opposite ends of the same day.**
 *
 * - A `Label` and a `FeatureRow` have a `windowEnd`: the instant the label became
 *   *decidable*, which is when a session closed. Features look strictly *before* it.
 * - A `Prediction` has `windowStart` and `windowEnd`: the span the prediction is *about*.
 *   `windowStart` is that same session close; `windowEnd` is 24 hours later.
 *
 * So `prediction.windowStart === label.windowEnd`, and they are the same instant under two
 * names. Nothing enforces this at the type level — both are strings — so `predictionFor`
 * below is the only place that makes the conversion, and it is spelled out there.
 *
 * **`outcome` is written automatically** by matching later events against the window. There
 * is no user confirmation button anywhere in this loop (D6). A person asked "did you mean
 * to do that?" will answer to be agreeable, and a benchmark built on agreeable answers
 * measures politeness.
 */
import {
  FIRST_SEEN_SCALE_HOURS,
  PRIOR_SESSION_RATE_SCALE,
  unsaturate,
  type FeatureName,
  type FeatureRow,
} from "../features/vector";

/**
 * `pending` — the window is still open.
 * `hit` — the subject recurred inside the window.
 * `miss` — the window closed with no recurrence, **and Tise was watching throughout**.
 * `expired` — the window closed but Tise could not tell. Scored by nobody. See
 * `storage/coverage.ts` for why this is a separate outcome rather than a miss.
 */
export type PredictionOutcome = "pending" | "hit" | "miss" | "expired";

export type PredictionTarget = "return_24h" | "next_session_category";

export interface Prediction {
  readonly predictionId: string;
  readonly createdAt: string;
  readonly target: PredictionTarget;
  /** The topic being predicted about. */
  readonly subject: string;
  /** Calibrated, 0..1. Never the raw score — see `calibrate.ts`. */
  readonly probability: number;
  readonly windowStart: string;
  readonly windowEnd: string;
  /** True when below the abstention threshold. Recorded, and not displayed. */
  readonly abstained: boolean;
  readonly modelName: string;
  readonly modelVersion: string;
  readonly featureSet: string;
  /** Nothing at or after this instant was used. Equal to `windowStart` by construction. */
  readonly dataCutoff: string;
  readonly evidence: readonly string[];
  readonly outcome: PredictionOutcome;
  readonly resolvedAt: string | null;
}

/** The exact field set SPEC.md defines. A test asserts nothing else is ever stored. */
export const PREDICTION_FIELDS = [
  "predictionId",
  "createdAt",
  "target",
  "subject",
  "probability",
  "windowStart",
  "windowEnd",
  "abstained",
  "modelName",
  "modelVersion",
  "featureSet",
  "dataCutoff",
  "evidence",
  "outcome",
  "resolvedAt",
] as const;

/**
 * Runs on **every write**, like `assertStorable` does for events.
 *
 * A prediction is exported and shown to the user, so it is a second surface where a URL
 * could escape. `evidence` is the risk: it is free text assembled from features, and free
 * text is where a path or a query string would end up if anyone ever built one there.
 */
const URL_STRUCTURE = /[/?#]|https?:/i;

export function assertStorablePrediction(prediction: Prediction): void {
  const unexpected = Object.keys(prediction).filter(
    (key) => !(PREDICTION_FIELDS as readonly string[]).includes(key),
  );
  if (unexpected.length > 0) {
    throw new Error(`refusing to store unexpected fields: ${unexpected.join(", ")}`);
  }
  if (prediction.probability < 0 || prediction.probability > 1) {
    throw new Error(`probability must be in [0, 1]: ${prediction.probability}`);
  }
  for (const instant of [prediction.createdAt, prediction.windowStart, prediction.windowEnd]) {
    if (!instant.endsWith("Z")) throw new Error(`refusing a non-UTC timestamp: ${instant}`);
  }
  if (Date.parse(prediction.windowEnd) <= Date.parse(prediction.windowStart)) {
    throw new Error("a prediction window must end after it starts");
  }
  if (prediction.dataCutoff !== prediction.windowStart) {
    throw new Error(
      "dataCutoff must equal windowStart: a prediction that used data from inside its " +
        "own window is not a prediction",
    );
  }
  for (const line of prediction.evidence) {
    if (URL_STRUCTURE.test(line)) {
      throw new Error(`evidence looks like it contains a URL: ${line}`);
    }
  }
  if ((prediction.outcome === "pending") !== (prediction.resolvedAt === null)) {
    throw new Error(
      `outcome ${prediction.outcome} and resolvedAt ${prediction.resolvedAt} disagree`,
    );
  }
}

function plural(count: number, one: string, many: string): string {
  return `${count} ${count === 1 ? one : many}`;
}

/**
 * Turn a feature row into sentences a person can check against their own memory.
 *
 * This is the "showing the evidence behind every prediction" half of SPEC's opening
 * sentence. It deliberately describes **features, not raw browsing**: "seen on 4 days in
 * the last week" is checkable, carries no URL, and says what the model actually used.
 *
 * Null features are skipped rather than described. "We have never seen this before" is
 * true but is not evidence *for* anything, and a list padded with absences reads as though
 * the model knew more than it did.
 */
/**
 * Recover the raw prior-session count from an `fs_3` row.
 *
 * `priorSessionRate` saturates `count / max(observedDays, 1)`, and `firstSeenSaturation`
 * saturates the hours. Both are invertible, so the count is arithmetic rather than an
 * estimate — and returning it keeps the evidence line able to say what a rate rests on,
 * which is the difference between honest evidence and an overstated one.
 *
 * Null when the category was never seen before the window, which is when there are no
 * prior sessions to count.
 */
export function priorSessionsFrom(row: FeatureRow): number | null {
  const saturatedRate = row.values.priorSessionRate;
  const saturatedHours = row.values.firstSeenSaturation;
  if (saturatedRate === null || saturatedHours === null) return null;

  const hours = unsaturate(saturatedHours, FIRST_SEEN_SCALE_HOURS);
  const perDay = unsaturate(saturatedRate, PRIOR_SESSION_RATE_SCALE);
  if (!Number.isFinite(hours) || !Number.isFinite(perDay)) return null;
  return Math.round(perDay * Math.max(hours / 24, 1));
}

export function evidenceFor(row: FeatureRow): string[] {
  const value = (name: FeatureName): number | null => row.values[name];
  const lines: string[] = [];

  const lastSeen = value("hoursSinceLastSeen");
  if (lastSeen !== null) {
    lines.push(
      lastSeen < 1
        ? "last seen within the hour"
        : `last seen ${plural(Math.round(lastSeen), "hour", "hours")} ago`,
    );
  }

  const days = value("daysSeen7d");
  if (days !== null && days > 0) {
    lines.push(`seen on ${plural(days, "day", "days")} in the last week`);
  }

  const count30 = value("eventCount30d");
  if (count30 !== null && count30 > 0) {
    lines.push(`${plural(count30, "visit", "visits")} in the last 30 days`);
  }

  const share = value("categoryShare30d");
  if (share !== null && share > 0) {
    lines.push(`${(share * 100).toFixed(0)}% of browsing in the last 30 days`);
  }

  // The strongest feature in the set (D52), so it is named explicitly along with how much
  // it rests on. A rate built on two sessions has to read differently from one built on
  // forty, or the evidence overstates itself.
  //
  // `fs_3` stores a saturated rate rather than the raw count (D82), so the count is
  // recovered by inverting the two transforms. That is arithmetic on values the row
  // already holds, not a reconstruction: it is exactly what `fs_2` used to store.
  const rate = value("priorReturnRate");
  const priors = priorSessionsFrom(row);
  if (rate !== null && priors !== null && priors > 0) {
    lines.push(
      `returned within a day after ${(rate * 100).toFixed(0)}% of the last ` +
        `${plural(priors, "session", "sessions")}`,
    );
  }

  return lines;
}
