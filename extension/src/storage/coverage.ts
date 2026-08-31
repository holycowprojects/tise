/**
 * When Tise was *not* watching. The record that makes `expired` mean something.
 *
 * A `return_24h` prediction resolves to `miss` when its window closed with no return. That
 * is a claim about the world, and it is only true if Tise was watching for the whole
 * window. If collection was paused for six of those hours, "no return was seen" is not
 * evidence that no return happened — it is the absence of evidence, and recording it as a
 * miss would put a fabricated negative into the reliability curve.
 *
 * That is D52's mistake in a new place. There, prior sessions whose horizon had not
 * elapsed were excluded from both sides of the ratio rather than counted as misses,
 * because "counting them as misses" is the tempting shortcut that looks conservative and
 * is wrong. Same here: a window Tise did not watch resolves to `expired` and is **scored
 * by nobody**.
 *
 * Gaps are recorded rather than uptime because gaps are rare — most of this list is empty
 * most of the time, and an empty list is the honest representation of "always watching".
 *
 * **A closed browser is not a gap.** If the person was not browsing, no return genuinely
 * happened, and that is a real miss. What counts as a gap is Tise being unable to observe
 * browsing that may have occurred: paused, or consent withdrawn.
 */
import { readMeta, writeMeta } from "./db";

const GAPS_KEY = "coverage:gaps";

/** `to` is `null` while the gap is still open — collection is off right now. */
export interface CoverageGap {
  readonly from: string;
  readonly to: string | null;
}

export async function coverageGaps(): Promise<CoverageGap[]> {
  return (await readMeta<CoverageGap[]>(GAPS_KEY)) ?? [];
}

/**
 * Note that collection stopped. Idempotent: calling twice does not open a second gap.
 *
 * Idempotence matters because the service worker is killed and restarted constantly, and a
 * settings write that happens to run twice must not corrupt the record.
 */
export async function recordCollectionStopped(at: number): Promise<void> {
  const gaps = await coverageGaps();
  if (gaps.some((gap) => gap.to === null)) return;
  gaps.push({ from: new Date(at).toISOString(), to: null });
  await writeMeta(GAPS_KEY, gaps);
}

/** Note that collection resumed. Idempotent when no gap is open. */
export async function recordCollectionStarted(at: number): Promise<void> {
  const gaps = await coverageGaps();
  const open = gaps.findIndex((gap) => gap.to === null);
  if (open === -1) return;
  gaps[open] = { from: (gaps[open] as CoverageGap).from, to: new Date(at).toISOString() };
  await writeMeta(GAPS_KEY, gaps);
}

/**
 * Was Tise watching for the whole of `[from, to]`?
 *
 * `consentGrantedAt` is part of the answer: before consent Tise stores nothing at all, so
 * any window opening before that instant is unwatched by definition. A window that starts
 * before Tise ever existed cannot be a miss.
 *
 * An open gap (`to === null`) extends to `now`, so a window inside a live pause is
 * correctly reported as uncovered rather than silently treated as watched.
 */
export function isFullyCovered(
  from: number,
  to: number,
  gaps: readonly CoverageGap[],
  consentGrantedAt: string | null,
  now: number,
): boolean {
  if (consentGrantedAt === null) return false;
  if (Date.parse(consentGrantedAt) > from) return false;

  for (const gap of gaps) {
    const gapFrom = Date.parse(gap.from);
    // `== null` catches both null and undefined, deliberately. A gap written without a
    // `to` at all would otherwise take the `Date.parse(undefined)` branch, produce NaN,
    // and every comparison against NaN is false — so the gap would silently stop
    // disqualifying anything and Tise would score windows it never watched. That is the
    // D107 defect in a second place, found by the D110 seam audit.
    const gapTo = gap.to == null ? now : Date.parse(gap.to);
    // Any overlap at all disqualifies the window. A partial gap is still a hole, and a
    // rule that tolerated "mostly watched" would need a threshold nobody measured.
    if (gapFrom < to && gapTo > from) return false;
  }
  return true;
}

/** Used by delete-all's accounting; the gaps live in `meta` and are cleared with it. */
export async function clearCoverage(): Promise<void> {
  await writeMeta(GAPS_KEY, []);
}
