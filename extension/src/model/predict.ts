/**
 * Making predictions, and the two rules about when not to.
 *
 * **Only for sessions that have closed.** A session is closed once the timeout has elapsed
 * since its last event. Predicting from a session still in progress would use a window
 * that is still growing, so the same prediction would change every few minutes and the
 * `dataCutoff` written on it would be a lie the moment the person clicked another link.
 *
 * **Only when a model exists.** Before the first training run there is nothing to predict
 * with, and a prediction of 0.5 from an untrained model is not a modest prediction — it is
 * a made-up number wearing the same schema as a measured one. No model, no rows.
 *
 * Predictions are created for **every** category in a closed session, including the ones
 * the abstention policy will refuse to show. See `storage/predictions.ts` for why.
 */
import { sessionise } from "../features/sessions";
import { computeFeatures, FEATURE_SET } from "../features/vector";
import { DEFAULT_HORIZON_HOURS } from "../features/labels";
import type { TiseEvent } from "../types";
import { shouldAnswer } from "./abstain";
import { applyCalibration } from "./calibrate";
import { predictProba } from "./logreg";
import { evidenceFor, type Prediction } from "./prediction";
import { transform } from "./prep";
import type { TrainedModel } from "./train";

export const TARGET = "return_24h";

export interface PredictOptions {
  readonly timeoutSeconds: number;
  readonly horizonHours?: number;
  readonly now: number;
}

/**
 * One prediction per (category, closed session).
 *
 * `windowStart` is the session's end — the same instant a `Label` calls its `windowEnd`.
 * The two names meet here and nowhere else; `prediction.ts` explains the collision.
 */
export function buildPredictions(
  events: readonly TiseEvent[],
  model: TrainedModel,
  options: PredictOptions,
): Prediction[] {
  const horizonHours = options.horizonHours ?? DEFAULT_HORIZON_HOURS;
  const horizonMs = horizonHours * 3_600_000;
  const timeoutMs = options.timeoutSeconds * 1000;
  const createdAt = new Date(options.now).toISOString();

  const predictions: Prediction[] = [];
  for (const session of sessionise(events, options.timeoutSeconds)) {
    const closedAt = Date.parse(session.endedAt);
    // Still open: the timeout has not elapsed, so more events may still join it.
    if (options.now - closedAt < timeoutMs) continue;

    for (const subject of [...session.categories].sort()) {
      const row = computeFeatures(events, subject, closedAt, {
        timeoutSeconds: options.timeoutSeconds,
        horizonHours,
      });
      const raw = predictProba(model.state, transform(model.preprocessor, row));
      const probability = applyCalibration(model.calibrator, raw);

      predictions.push({
        predictionId: `${TARGET}:${subject}:${session.endedAt}`,
        createdAt,
        target: TARGET,
        subject,
        probability,
        windowStart: session.endedAt,
        windowEnd: new Date(closedAt + horizonMs).toISOString(),
        abstained: !shouldAnswer(model.policy, probability),
        modelName: "logreg_fs2",
        // The instant of the fit identifies it uniquely, which is what makes a stored
        // prediction reproducible: two models trained on different days are different
        // models even when every hyperparameter matches.
        modelVersion: `${model.calibrator.version}@${model.trainedAt}`,
        featureSet: FEATURE_SET,
        // Equal to windowStart by construction, and asserted on every write. A prediction
        // that used data from inside its own window is not a prediction.
        dataCutoff: session.endedAt,
        evidence: evidenceFor(row),
        outcome: "pending",
        resolvedAt: null,
      });
    }
  }
  return predictions;
}
