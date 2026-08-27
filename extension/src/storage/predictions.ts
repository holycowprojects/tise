/**
 * The prediction registry.
 *
 * Every prediction Tise makes is written here with enough metadata to reproduce it — the
 * model, the feature set, the calibration, the instant beyond which no data was used.
 * That is what turns a prediction into an evaluated claim rather than a display element
 * (D6), and it is the difference between this project and a demo.
 *
 * **Abstained predictions are stored too.** They are not shown, and they are recorded
 * precisely because they are not shown: the only way to learn whether abstaining was the
 * right call is to write down what would have been said and check it against what
 * happened. On the author's own browsing (D70) *every* prediction is abstained, so a
 * registry that kept only the displayed ones would currently be empty and would have
 * nothing to say about whether that silence was justified.
 */
import type { Prediction } from "../model/prediction";
import { assertStorablePrediction } from "../model/prediction";
import { openTiseDb } from "./db";

/**
 * Write predictions, replacing any with the same (target, subject, windowStart).
 *
 * Every row is validated **before the transaction opens**, so a batch containing one bad
 * prediction writes none of it rather than half of it.
 */
export async function putPredictions(predictions: readonly Prediction[]): Promise<void> {
  if (predictions.length === 0) return;
  for (const prediction of predictions) assertStorablePrediction(prediction);
  const db = await openTiseDb();
  const tx = db.transaction("predictions", "readwrite");
  await Promise.all([...predictions.map((row) => tx.store.put(row)), tx.done]);
}

export async function countPredictions(): Promise<number> {
  const db = await openTiseDb();
  return db.count("predictions");
}

/** Every prediction, oldest window first. */
export async function allPredictions(): Promise<Prediction[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("predictions", "windowEnd");
}

/** The ones still waiting on their window to close. What the resolver reads. */
export async function pendingPredictions(): Promise<Prediction[]> {
  const db = await openTiseDb();
  return db.getAllFromIndex("predictions", "outcome", "pending");
}

/** Counts by outcome, for the developer surface and for the export's summary. */
export async function predictionCounts(): Promise<Record<string, number>> {
  const counts: Record<string, number> = {};
  for (const prediction of await allPredictions()) {
    counts[prediction.outcome] = (counts[prediction.outcome] ?? 0) + 1;
  }
  return counts;
}

export async function clearPredictions(): Promise<number> {
  const db = await openTiseDb();
  const count = await db.count("predictions");
  await db.clear("predictions");
  return count;
}
