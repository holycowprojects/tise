/**
 * Join attention spans onto events. The step that makes `as_2` computable in the browser.
 *
 * PARITY-CRITICAL: `TiseExport.dwell_by_event` and `events_with_dwell` in
 * `research/tise_research/data/load.py` are the mirror, and both sides are checked against
 * `research/fixtures/export_v3.json`.
 *
 * **The join happens in memory and never reaches disk.** An event is final when written and
 * carries `dwellSeconds: null` on every row storage will accept — `assertStorable` throws
 * otherwise, and D35 is why. A span is opened, extended and closed later, which is exactly
 * why D96 gave spans their own store rather than a field on the event. This module puts the
 * two together for the length of one feature computation and throws the result away.
 *
 * Two decisions live here, and both would be invisible if wrong.
 *
 * **Attention is summed across spans, not taken from the last one.** One visit produces
 * several spans when the person switches away and comes back — that is what `tab-switch`
 * and `blur` end reasons mean. Keeping only the most recent would silently halve the dwell
 * of every revisited page, and a revisited page is precisely the kind this target is about.
 *
 * **An event with no span keeps `null`, never zero.** No measurement is not a measurement of
 * none (D51). A zero would enter the trailing median as a genuinely short visit and drag
 * every threshold down, which makes the label wrong for every *other* visit in that
 * category — the damage is not local to the row that was missing.
 */
import type { AttentionSpan, TiseEvent } from "../types";

/**
 * Total attention per event id, summed across that event's spans.
 *
 * Events with no span are **absent from the map** rather than present at zero, so a caller
 * cannot accidentally read a missing measurement as a short one.
 */
export function dwellByEvent(spans: readonly AttentionSpan[]): Map<string, number> {
  const totals = new Map<string, number>();
  for (const span of spans) {
    totals.set(span.eventId, (totals.get(span.eventId) ?? 0) + span.activeSeconds);
  }
  return totals;
}

/**
 * Events with attention attached, ready for `attentionExamples`.
 *
 * Returns new objects; the inputs are not mutated, because the same event array is read by
 * `fs_3` feature code that must continue to see `dwellSeconds: null`.
 */
export function attachDwell(
  events: readonly TiseEvent[],
  spans: readonly AttentionSpan[],
): TiseEvent[] {
  const totals = dwellByEvent(spans);
  return events.map((event) => ({
    ...event,
    dwellSeconds: totals.get(event.eventId) ?? null,
  }));
}

/**
 * How many events have any measured attention at all.
 *
 * The number that says whether `visit_engaged` can be trained yet — and the one nothing in
 * the extension could answer before D101, because spans had no reader.
 */
export function measuredCount(
  events: readonly TiseEvent[],
  spans: readonly AttentionSpan[],
): number {
  const totals = dwellByEvent(spans);
  let count = 0;
  for (const event of events) if (totals.has(event.eventId)) count += 1;
  return count;
}
