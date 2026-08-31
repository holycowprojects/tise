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
 * Predictions are created for **every** category in a closed session. See
 * `storage/predictions.ts` for why.
 *
 * **Abstention no longer gates anything, and removing it was owed since D88.**
 *
 * Until now this file asked `shouldAnswer(model.policy, …)` before marking a prediction
 * shown. D70 measured that **no confidence threshold certified the 90% target on any
 * fold** — certifying a margin that thin needed >12,800 answered rows against calibration
 * slices of 61-133 — so the policy reported `targetMet: false` and the extension withheld
 * *everything*, by design and forever. D88 retired abstention for that reason and replaced
 * it with **show everything, always with its denominator**. The replacement shipped in
 * `model/nextCategory.ts`; this half was never done, and it was found by checking what the
 * product actually shows rather than by any test failing.
 *
 * `abstained` is therefore **always false on new rows**. The field stays because it is a
 * true record of rows written under the old policy, and because a stored prediction is the
 * scorecard: D72 makes every prediction resolve itself from the event stream whether or not
 * anything ever displayed it. What changed is that nothing is withheld any more.
 *
 * **`abstain.ts` is not deleted.** D88 keeps the accuracy-versus-coverage curve as a
 * published result; it is no longer a gate. `selectThreshold` still runs at training time
 * so the curve stays measurable, and `shouldAnswer` survives with no caller in the shipped
 * path — `research/tise_research/eval/abstain.py` is its parity mirror and the pair is what
 * makes the published curve reproducible.
 */
import { sessionise } from "../features/sessions";
import { computeFeatures, FEATURE_SET } from "../features/vector";
import { DEFAULT_HORIZON_HOURS } from "../features/labels";
import type { TiseEvent } from "../types";
import { applyCalibration } from "./calibrate";
import { predictProba } from "./logreg";
import { evidenceFor, type Prediction } from "./prediction";
import { transform } from "./prep";
import { MODEL_NAME, type TrainedModel } from "./train";

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
        // D88: nothing is withheld on confidence. Always false on new rows; see above.
        abstained: false,
        modelName: MODEL_NAME,
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
