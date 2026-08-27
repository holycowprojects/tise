/**
 * Training, chunked so that MV3 killing the worker costs one chunk and never the run.
 *
 * A service worker gets roughly thirty seconds of idle before Chrome may terminate it,
 * and there is no warning and no callback. Anything that must finish therefore cannot be
 * one long call — it has to be a sequence of short calls, each of which leaves a complete
 * state behind. That is the shape here: an alarm fires, one chunk of gradient steps runs,
 * the state is written, the worker is free to die. The next alarm picks it up.
 *
 * **No offscreen document.** The plan named one, on the reasoning that training is
 * long-running. Chunking removes the premise: no single call is long. The `offscreen`
 * permission was withdrawn from the manifest at T11 (D63), and `manifest.test.ts` asserts
 * it stays out — so if anything here ever does need a document that outlives the worker,
 * it fails loudly rather than silently reaching for a capability nobody re-justified.
 *
 * **The training set is pinned when a job starts.** Chunk seven must train on exactly
 * what chunk one did, or the run is not one fit — it is several fits averaged by
 * accident, and nothing about the result would look wrong. So a job records the window it
 * covers and how many rows were in it, and if either stops matching, the job **restarts**
 * rather than continuing over different data. Restarting is visible and cheap; continuing
 * is invisible and wrong.
 */
import { return24hLabels, type Label } from "../features/labels";
import { computeFeatures, FEATURE_SET, type FeatureRow } from "../features/vector";
import { allEvents } from "../storage/events";
import { allFeatureRows, putFeatureRows } from "../storage/features";
import { allLabels, putLabels } from "../storage/labels";
import { readMeta, writeMeta, deleteMeta } from "../storage/db";
import { joinStored } from "./dataset";
import {
  DEFAULT_SPEC,
  initialState,
  trainChunk,
  type LogRegSpec,
  type LogRegState,
} from "./logreg";
import { fitPreprocessor, DESIGN_COLUMNS, buildMatrix, type Preprocessor } from "./prep";
import { fitTransitionTable, type TransitionTable } from "./transition";
import { sessionise } from "../features/sessions";

export const TRAINING_ALARM = "tise:train";

/**
 * Six hours, matching retention. Training is not urgent — a model an afternoon out of
 * date is not a worse model in any way a user can perceive — and a frequent alarm on a
 * battery-powered machine is a cost with no matching benefit.
 */
export const TRAINING_PERIOD_MINUTES = 6 * 60;

const JOB_KEY = "training:return_24h";
const MODEL_KEY = "model:return_24h";

/** A job in flight. Persisted after every chunk, so it is deliberately small. */
export interface TrainingJob {
  readonly featureSet: string;
  readonly spec: LogRegSpec;
  readonly startedAt: string;
  /** Latest `windowEnd` included. Rows after it are not in this job. */
  readonly cutoff: string;
  /** Rows inside the cutoff when the job started. A change means the set moved. */
  readonly rowCount: number;
  readonly preprocessor: Preprocessor;
  readonly state: LogRegState;
}

/** A finished model, and everything needed to say what produced it. */
export interface TrainedModel {
  readonly target: "return_24h";
  readonly featureSet: string;
  readonly trainedAt: string;
  readonly rowCount: number;
  readonly positiveCount: number;
  readonly spec: LogRegSpec;
  readonly preprocessor: Preprocessor;
  readonly state: LogRegState;
  readonly transition: TransitionTable;
}

export interface ChunkOutcome {
  readonly state: "idle" | "training" | "done";
  readonly iterationsDone: number;
  readonly iterations: number;
  readonly rowCount: number;
  /** Set when a job was abandoned because its training set moved underneath it. */
  readonly restarted?: boolean;
  readonly reason?: "no-data" | "set-changed";
}

/**
 * Recompute rows and labels from whatever events are currently stored, and persist them.
 *
 * Both stores replace on their key, so this is idempotent over the same events. It is the
 * step that turns browsing into training data, and it is separate from training because
 * an outcome is provisional until its horizon elapses: yesterday's label is rewritten by
 * today's pass, while yesterday's feature row is rewritten with the identical values.
 *
 * Events that have already expired are not revisited — their rows and labels were written
 * when they still existed and stay in the stores (D11). This adds to what is there; it
 * never prunes it.
 */
export async function refreshDataset(options: {
  timeoutSeconds: number;
  horizonHours: number;
}): Promise<{ rows: number; labels: number }> {
  const events = await allEvents();
  if (events.length === 0) return { rows: 0, labels: 0 };

  const labels: Label[] = return24hLabels(
    events,
    options.timeoutSeconds,
    options.horizonHours,
  );
  const rows: FeatureRow[] = labels.map((label) =>
    computeFeatures(events, label.subject, Date.parse(label.windowEnd), options),
  );

  await putFeatureRows(rows);
  await putLabels(labels);
  return { rows: rows.length, labels: labels.length };
}

async function readTrainingSet(cutoff: string | null): Promise<{
  rows: FeatureRow[];
  outcomes: boolean[];
}> {
  const [storedRows, storedLabels] = await Promise.all([allFeatureRows(), allLabels()]);
  const limit = cutoff === null ? Number.POSITIVE_INFINITY : Date.parse(cutoff);
  const rows = storedRows.filter(
    (row) => row.featureSet === FEATURE_SET && Date.parse(row.windowEnd) <= limit,
  );
  const labels = storedLabels.filter((label) => Date.parse(label.windowEnd) <= limit);
  const joined = joinStored(rows, labels);
  return { rows: joined.rows, outcomes: joined.outcomes };
}

export async function readJob(): Promise<TrainingJob | undefined> {
  return readMeta<TrainingJob>(JOB_KEY);
}

export async function readModel(): Promise<TrainedModel | undefined> {
  return readMeta<TrainedModel>(MODEL_KEY);
}

async function startJob(spec: LogRegSpec): Promise<TrainingJob | null> {
  const { rows } = await readTrainingSet(null);
  if (rows.length === 0) return null;

  // The cutoff is the newest window in the set. Anything that arrives later — live
  // browsing, or a backdated import — lands outside this job and is picked up by the
  // next one, rather than joining a fit that is already half-run.
  let cutoff = (rows[0] as FeatureRow).windowEnd;
  for (const row of rows) {
    if (Date.parse(row.windowEnd) > Date.parse(cutoff)) cutoff = row.windowEnd;
  }

  return {
    featureSet: FEATURE_SET,
    spec,
    startedAt: new Date().toISOString(),
    cutoff,
    rowCount: rows.length,
    preprocessor: fitPreprocessor(rows),
    state: initialState(DESIGN_COLUMNS.length),
  };
}

/**
 * Advance training by one chunk. Safe to call at any time, from any wake-up.
 *
 * Returns what happened rather than throwing on the ordinary cases — no data yet, or a
 * job that had to restart — because every one of those is a normal state for a profile
 * that has only just been installed.
 */
export interface TrainingOptions {
  readonly spec?: LogRegSpec;
  /** Needed only for the transition table, which is session-shaped. */
  readonly timeoutSeconds: number;
}

export async function runTrainingChunk(options: TrainingOptions): Promise<ChunkOutcome> {
  const spec = options.spec ?? DEFAULT_SPEC;
  let job = await readJob();

  // A job from an older feature set is not resumable: its preprocessor has the wrong
  // number of columns and its coefficients mean something else.
  if (job !== undefined && job.featureSet !== FEATURE_SET) job = undefined;

  let restarted = false;
  if (job === undefined) {
    const started = await startJob(spec);
    if (started === null) {
      return {
        state: "idle",
        iterationsDone: 0,
        iterations: spec.iterations,
        rowCount: 0,
        reason: "no-data",
      };
    }
    job = started;
  }

  let set = await readTrainingSet(job.cutoff);
  if (set.rows.length !== job.rowCount) {
    // Backdated rows landed inside a window this job had already fixed. Continuing would
    // silently blend two training sets, so the job starts again on the current one.
    await deleteMeta(JOB_KEY);
    const started = await startJob(job.spec);
    if (started === null) {
      return {
        state: "idle",
        iterationsDone: 0,
        iterations: job.spec.iterations,
        rowCount: 0,
        reason: "no-data",
      };
    }
    job = started;
    restarted = true;
    set = await readTrainingSet(job.cutoff);
  }

  const matrix = buildMatrix(job.preprocessor, set.rows);
  const advanced = trainChunk(job.state, matrix, set.outcomes, job.spec);

  if (advanced.iterationsDone < job.spec.iterations) {
    await writeMeta(JOB_KEY, { ...job, state: advanced } satisfies TrainingJob);
    return {
      state: "training",
      iterationsDone: advanced.iterationsDone,
      iterations: job.spec.iterations,
      rowCount: set.rows.length,
      ...(restarted ? { restarted: true, reason: "set-changed" as const } : {}),
    };
  }

  // Finished. The transition table is fitted here rather than incrementally because it is
  // counting, not optimising — it costs one pass and cannot be interrupted usefully.
  const events = await allEvents();
  const model: TrainedModel = {
    target: "return_24h",
    featureSet: FEATURE_SET,
    trainedAt: new Date().toISOString(),
    rowCount: set.rows.length,
    positiveCount: set.outcomes.filter(Boolean).length,
    spec: job.spec,
    preprocessor: job.preprocessor,
    state: advanced,
    transition: fitTransitionTable(sessionise(events, options.timeoutSeconds)),
  };
  await writeMeta(MODEL_KEY, model);
  await deleteMeta(JOB_KEY);

  return {
    state: "done",
    iterationsDone: advanced.iterationsDone,
    iterations: job.spec.iterations,
    rowCount: set.rows.length,
    ...(restarted ? { restarted: true, reason: "set-changed" as const } : {}),
  };
}

/** Abandon any job in flight. The trained model, if there is one, is left alone. */
export async function cancelTraining(): Promise<void> {
  await deleteMeta(JOB_KEY);
}
