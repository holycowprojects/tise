/**
 * `visit_engaged` — will this visit hold you? One label and one `as_2` row per visit.
 *
 * PARITY-CRITICAL: `research/tise_research/features/attention.py` is the mirror, and the
 * two must produce identical labels and identical feature maps within 1e-9.
 *
 * > Given a page you have just opened, will you stay longer than you usually stay on pages
 * > of this category?
 *
 * Adopted in D97 on the author's own browsing, then **replicated across 1,326 other
 * people** in D100, where it beat a constant for 88.6% of them individually.
 *
 * **Dwell arrives here and is never stored.** `TiseEvent.dwellSeconds` is `null` on every
 * row the storage layer will accept — `assertStorable` throws otherwise, and D35 is why.
 * D96 put attention spans in their own store precisely because an event is final when
 * written while a span is opened, extended and closed later. So dwell is joined onto events
 * **in memory**, immediately before features are computed, and the joined value never goes
 * back to disk. The type permits it, storage forbids it, and this module requires it.
 *
 * **Leakage is structural, not checked.** A visit's label and features are emitted *before*
 * that visit joins any state, so a visit can never appear in its own median. The same shape
 * as `block_labels.py`, and the reason no `windowEnd` filter is needed here.
 *
 * **A visit with no dwell is skipped, never imputed.** A missing duration is not a short
 * one, and inventing a value is the defect D51 forbids.
 */
import type { TiseEvent } from "../types";
import { sessionise } from "./sessions";
import { AS2_FEATURE_NAMES, type CompatClass, type FeatureRow, saturate } from "./vector";

/** The target's name. Matches `Prediction.target` in SPEC.md and Python's constant. */
export const VISIT_ENGAGED_TARGET = "visit_engaged";

export const AS2_FEATURE_SET = "as_2";

/** Visits of the same category the median is taken over. */
export const DEFAULT_TRAILING_VISITS = 20;

/** Visits of a category before it can be predicted at all. */
export const DEFAULT_MIN_PRIOR_VISITS = 10;

/**
 * Dwell at which `dwellLevel` reaches 0.5, in seconds. Thirty seconds is an ordinary page
 * read. **Declared, not fitted** (D81), and it does not move per corpus: D100 kept it at 30
 * against a panel whose median dwell was 8s, because a declared constant re-tuned per
 * dataset is a fitted one.
 */
export const DWELL_SCALE_SECONDS = 30;

/** Session position saturation, in visits. Declared. */
export const POSITION_SCALE = 10;

/**
 * Prior visits at which `domainVisits` reaches 0.5. Twenty, matching the trailing window
 * the median is taken over, so there is one notion of "enough history" and not two.
 */
export const DOMAIN_VISIT_SCALE = 20;

/**
 * Visits `domainShare` is taken over. A hundred is a few days of browsing — long enough
 * that a share is not one visit's worth of noise, short enough that a domain abandoned last
 * month has left it.
 */
export const DOMAIN_SHARE_WINDOW = 100;

/** `isDailyDomain` looks back this many days and fires at this many of them. */
export const DAILY_DOMAIN_WINDOW_DAYS = 7;
export const DAILY_DOMAIN_MIN_DAYS = 4;

export interface AttentionLabel {
  readonly target: string;
  readonly subject: string;
  readonly windowEnd: string;
  readonly outcome: boolean;
  readonly horizonHours: number;
  readonly sessionId: string;
  /**
   * Unique per example. Consumers map a label back to its feature row, and keying that on
   * `(subject, windowEnd)` is unique on one person's browsing and **not** in general —
   * 0.02% of the D100 panel's rows are a second visit by one person in the same second.
   */
  readonly labelId: string;
}

export interface AttentionExample {
  readonly label: AttentionLabel;
  readonly row: FeatureRow;
  /**
   * Carried so a per-domain baseline can be fitted, which D24 makes mandatory once four
   * features read the domain. Never displayed and never stored.
   */
  readonly domain: string;
}

export interface AttentionOptions {
  readonly timeoutSeconds: number;
  readonly trailing?: number;
  readonly minPrior?: number;
}

/**
 * Median of a list, mirroring Python's `statistics.median` exactly.
 *
 * For an even count Python averages the two middle values; taking the lower would shift
 * every threshold by half a step and no test on odd-length data would notice.
 */
export function median(values: readonly number[]): number {
  if (values.length === 0) throw new Error("median of no values");
  const ordered = [...values].sort((a, b) => a - b);
  const middle = Math.floor(ordered.length / 2);
  if (ordered.length % 2 === 1) return ordered[middle] as number;
  return ((ordered[middle - 1] as number) + (ordered[middle] as number)) / 2;
}

/**
 * How the person arrived. The one genuinely *conditional* fact each visit carries.
 *
 * `typed` and `auto_bookmark` are deliberate acts; `link` is incidental. The distinction
 * entered the project in D93 and immediately became the second-largest coefficient.
 */
function transitionFlags(transition: string): Record<string, number> {
  const core = transition.toLowerCase();
  return {
    arrivedTyped: core === "typed" || core === "generated" || core === "keyword" ? 1 : 0,
    arrivedBookmark: core.includes("bookmark") ? 1 : 0,
    arrivedLink: core === "link" ? 1 : 0,
  };
}

/**
 * UTC calendar day, as `YYYY-MM-DD`.
 *
 * **UTC, like every other calendar feature in this project** (`context.ts` sets the
 * convention and says what it costs). Python's mirror reads the datetime's own zone, and
 * the events on both sides of the parity fixture are UTC, so the two agree. Using local
 * time here would have shifted `isDailyDomain` and the hour features by the machine's
 * offset and failed nothing except the fixture.
 */
function dayKey(at: Date): string {
  const year = at.getUTCFullYear();
  const month = `${at.getUTCMonth() + 1}`.padStart(2, "0");
  const day = `${at.getUTCDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function daysBefore(at: Date, days: number): string {
  const shifted = new Date(at.getTime());
  shifted.setUTCDate(shifted.getUTCDate() - days);
  return dayKey(shifted);
}

/**
 * One example per visit that has enough history of its own category.
 *
 * `events` must carry `dwellSeconds` joined from the attention store; a visit whose dwell
 * is `null` contributes to history but never receives a label.
 */
export function attentionExamples(
  events: readonly TiseEvent[],
  options: AttentionOptions,
): AttentionExample[] {
  const trailing = options.trailing ?? DEFAULT_TRAILING_VISITS;
  const minPrior = options.minPrior ?? DEFAULT_MIN_PRIOR_VISITS;
  const sessions = sessionise(events, options.timeoutSeconds);

  const history = new Map<string, number[]>();
  const domainDwell = new Map<string, number[]>();
  const domainVisits = new Map<string, number>();
  const domainDays = new Map<string, Set<string>>();
  const recentDomains: string[] = [];

  const examples: AttentionExample[] = [];
  const seen = new Set<string>();
  let previousCategory: string | null = null;
  let previousDomain: string | null = null;
  let previousDwell: number | null = null;

  for (const session of sessions) {
    session.events.forEach((event, position) => {
      const dwell = event.dwellSeconds;
      const prior = history.get(event.category) ?? [];
      const window = prior.slice(-trailing);

      if (dwell !== null && dwell !== undefined && prior.length >= minPrior) {
        const threshold = median(window);
        const at = new Date(event.occurredAt);
        const hourAngle = (2 * Math.PI * at.getUTCHours()) / 24;

        // Domain state, all of it strictly before this visit.
        const domainWindow = (domainDwell.get(event.domain) ?? []).slice(-trailing);
        const firstDay = daysBefore(at, DAILY_DOMAIN_WINDOW_DAYS - 1);
        let daysRecently = 0;
        for (const day of domainDays.get(event.domain) ?? []) {
          if (day >= firstDay) daysRecently += 1;
        }
        if (recentDomains.length === 0) {
          throw new Error("a labelled visit always has prior visits");
        }
        let sameDomainRecently = 0;
        for (const name of recentDomains) {
          if (name === event.domain) sameDomainRecently += 1;
        }

        let windowTotal = 0;
        for (const value of window) windowTotal += value;

        const values: Record<string, number | null> = {
          dwellLevel: saturate(threshold, DWELL_SCALE_SECONDS),
          lastDwellRatio: (window[window.length - 1] as number) / (threshold + 1),
          meanRatio: windowTotal / window.length / (threshold + 1),
          sessionPosition: saturate(position, POSITION_SCALE),
          isSessionStart: position === 0 ? 1 : 0,
          sameAsPrevious: previousCategory === event.category ? 1 : 0,
          hourSin: Math.sin(hourAngle),
          hourCos: Math.cos(hourAngle),
          isWeekend: (at.getUTCDay() + 6) % 7 >= 5 ? 1 : 0,
          ...transitionFlags(event.transition),
          domainVisits: saturate(domainVisits.get(event.domain) ?? 0, DOMAIN_VISIT_SCALE),
          domainShare: sameDomainRecently / recentDomains.length,
          isDailyDomain: daysRecently >= DAILY_DOMAIN_MIN_DAYS ? 1 : 0,
          domainDwellLevel:
            domainWindow.length > 0
              ? saturate(median(domainWindow), DWELL_SCALE_SECONDS)
              : null,
          prevSameDomain: previousDomain === event.domain ? 1 : 0,
          prevDwellRatio: previousDwell === null ? null : previousDwell / (threshold + 1),
        };

        if (seen.has(event.eventId)) {
          throw new Error(
            `duplicate event id ${event.eventId}. Feature rows are indexed by it, so one ` +
              "row would be scored against two labels and nothing would report it.",
          );
        }
        seen.add(event.eventId);

        const selected: Record<string, number | null> = {};
        for (const name of AS2_FEATURE_NAMES) selected[name] = values[name] ?? null;

        examples.push({
          domain: event.domain,
          label: {
            target: VISIT_ENGAGED_TARGET,
            subject: event.category,
            windowEnd: event.occurredAt,
            outcome: dwell > threshold,
            horizonHours: 0,
            sessionId: session.sessionId,
            labelId: event.eventId,
          },
          row: {
            subject: event.category,
            windowEnd: event.occurredAt,
            featureSet: AS2_FEATURE_SET,
            compat: "full" satisfies CompatClass,
            values: selected,
          },
        });
      }

      // Only now does this visit become history.
      if (dwell !== null && dwell !== undefined) {
        const forCategory = history.get(event.category);
        if (forCategory) forCategory.push(dwell);
        else history.set(event.category, [dwell]);

        const forDomain = domainDwell.get(event.domain);
        if (forDomain) forDomain.push(dwell);
        else domainDwell.set(event.domain, [dwell]);
      }
      domainVisits.set(event.domain, (domainVisits.get(event.domain) ?? 0) + 1);
      const days = domainDays.get(event.domain);
      const key = dayKey(new Date(event.occurredAt));
      if (days) days.add(key);
      else domainDays.set(event.domain, new Set([key]));

      recentDomains.push(event.domain);
      if (recentDomains.length > DOMAIN_SHARE_WINDOW) recentDomains.shift();

      previousCategory = event.category;
      previousDomain = event.domain;
      previousDwell = dwell ?? null;
    });
  }

  return examples;
}
