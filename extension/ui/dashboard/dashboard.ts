/**
 * The dashboard. **The first page of Tise written for a person rather than for me.**
 *
 * The popup stays a developer surface; this is what T14 asked for. Three things differ
 * from the plan T14 was written under, and all three follow decisions taken since:
 *
 * **It does not list predictions.** T14 said "every prediction shows probability, window
 * and evidence". Those predictions belong to `return_24h`, which D88 retired as the
 * product target — showing them would put a retired question in front of the person as
 * though it were advice. They are kept and scored, and the scorecard below says so.
 *
 * **Nothing is hidden for being unconfident.** T14 said abstained predictions are absent
 * rather than greyed out. D88 retired abstention and D103 implemented the replacement, so
 * the only thing withheld anywhere is a number with too little behind it, and the page
 * says how much is missing.
 *
 * **Purchase intent is absent, not labelled.** T14 and D6 wanted it shown with a visible
 * "not evaluated" tag. On reflection that is worse than leaving it out: confirming it
 * would mean reading checkout pages, which the privacy design forbids outright, so it
 * could never move off that label. A permanent placeholder next to measured numbers
 * teaches the reader that the labels are decorative. The reason is stated instead.
 *
 * Every value is written with `textContent`, never `innerHTML` — the T5 spike rendered
 * `<all_urls>` as an HTML tag and reported its own configuration wrongly.
 */
import { sessionise } from "../../src/features/sessions";
import { categoryTransitions } from "../../src/features/transitions";
import {
  boardReadiness,
  browsingSummary,
  hubTopic,
  scorecard,
  topicBoard,
  type BrowsingSummary,
  type Scorecard,
  type TopicBoardEntry,
} from "../../src/model/overview";
import { MIN_CONDITIONAL_CHANGES } from "../../src/model/nextCategory";
import { PURCHASE_INTENT_NOTE, TARGET_STATUS } from "../../src/model/status";
import { allEvents } from "../../src/storage/events";
import { allPredictions } from "../../src/storage/predictions";
import { allSpans } from "../../src/storage/spans";
import { loadSettings } from "../../src/storage/settings";

function element(id: string): HTMLElement {
  const found = document.getElementById(id);
  if (!found) throw new Error(`missing element: ${id}`);
  return found;
}

function clear(host: HTMLElement): HTMLElement {
  host.textContent = "";
  return host;
}

function note(host: HTMLElement, text: string): void {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = text;
  host.append(p);
}

function factRow(host: HTMLTableElement, key: string, value: string): void {
  const tr = host.insertRow();
  const k = tr.insertCell();
  k.className = "k";
  k.textContent = key;
  const v = tr.insertCell();
  v.className = "v";
  v.textContent = value;
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Whole numbers, always (D88). A card reading 47.3% invites unearned precision. */
function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

function renderBoard(entries: readonly TopicBoardEntry[], transitions: number): void {
  const host = clear(element("board"));
  const lede = element("board-lede");

  if (entries.length === 0) {
    const readiness = boardReadiness([]);
    lede.textContent =
      "Nothing here yet. This needs one topic you have left at least " +
      `${MIN_CONDITIONAL_CHANGES} times before it can answer for that topic on its own.`;
    note(
      host,
      transitions === 0
        ? "No topic changes recorded."
        : `${transitions.toLocaleString()} topic changes so far, none of them concentrated ` +
          `enough on a single topic yet. Closest: ${readiness.closest}.`,
    );
    return;
  }

  const base =
    "Counted from your own browsing on this device. These are not predictions — they are " +
    "what you actually did, with the number behind every percentage.";
  const hub = hubTopic(entries);
  lede.textContent =
    hub === null
      ? base
      : `${base} ${hub.leadsFrom} of your ${hub.topics} topics lead back to ` +
        `${hub.category} more often than to anything else, so the rows worth reading are ` +
        `the ones that do not.`;

  for (const { fromCategory, card } of entries) {
    const panel = document.createElement("div");
    panel.className = "panel topic";

    const heading = document.createElement("h3");
    heading.textContent = `After ${fromCategory} `;
    const count = document.createElement("span");
    count.textContent = `— ${card.denominator} times`;
    heading.append(count);
    panel.append(heading);

    // Four is where a list stops being readable at a glance; the rest are counted, not
    // dropped, because "and 6 others" is part of the denominator being honest.
    const shown = card.answers.slice(0, 4);
    const widest = shown[0]?.share ?? 1;
    for (const answer of shown) {
      const row = document.createElement("div");
      row.className = "answer";

      const name = document.createElement("div");
      name.className = "name";
      const bar = document.createElement("i");
      // Scaled against the largest answer, so the shape is readable when everything is
      // small. The percentage beside it is the real number.
      bar.style.width = widest > 0 ? `${(answer.share / widest) * 100}%` : "0";
      const label = document.createElement("b");
      label.textContent = answer.category;
      name.append(bar, label);

      const pct = document.createElement("div");
      pct.className = "pct";
      pct.textContent = percent(answer.share);

      const of = document.createElement("div");
      of.className = "of";
      of.textContent = `${answer.count} of ${answer.denominator}`;

      row.append(name, pct, of);
      panel.append(row);
    }

    const remaining = card.answers.length - shown.length;
    if (remaining > 0) {
      const p = document.createElement("p");
      p.className = "empty";
      p.style.marginTop = "6px";
      p.textContent = `and ${remaining} other ${remaining === 1 ? "topic" : "topics"}.`;
      panel.append(p);
    }

    host.append(panel);
  }
}

function renderSummary(summary: BrowsingSummary, spans: number, minutes: number): void {
  const host = clear(element("summary"));
  const facts = document.createElement("table");

  if (summary.events === 0) {
    note(host, "Nothing collected yet.");
    return;
  }

  factRow(facts, "Pages visited", summary.events.toLocaleString());
  factRow(
    facts,
    "Collected here, versus imported",
    `${summary.liveEvents.toLocaleString()} / ${summary.importedEvents.toLocaleString()}`,
  );
  if (summary.firstAt !== null && summary.lastAt !== null) {
    factRow(
      facts,
      "Covering",
      `${shortDate(summary.firstAt)} — ${shortDate(summary.lastAt)}` +
        (summary.days !== null ? ` (${summary.days} days)` : ""),
    );
  }
  factRow(facts, "Sittings", summary.sessions.toLocaleString());
  factRow(facts, "Topics recognised", String(summary.topics));
  factRow(facts, "Times you changed topic", summary.changes.toLocaleString());
  if (summary.unshowableChanges > 0) {
    // Named rather than quietly subtracted: the difference between the two numbers above
    // and below is otherwise unexplainable from the page.
    factRow(
      facts,
      "…of those, into an uncategorised site",
      summary.unshowableChanges.toLocaleString(),
    );
  }
  factRow(
    facts,
    "Attention measured",
    spans === 0
      ? "not yet"
      : `${spans.toLocaleString()} spans, ${minutes.toLocaleString()} minutes`,
  );
  host.append(facts);
}

function renderTopics(summary: BrowsingSummary): void {
  const host = clear(element("topics"));
  if (summary.byTopic.length === 0) {
    note(host, "Nothing collected yet.");
    return;
  }

  const widest = summary.byTopic[0]?.share ?? 1;
  for (const topic of summary.byTopic) {
    const row = document.createElement("div");
    row.className = "answer";

    const name = document.createElement("div");
    name.className = "name";
    const bar = document.createElement("i");
    bar.style.width = widest > 0 ? `${(topic.share / widest) * 100}%` : "0";
    const label = document.createElement("b");
    label.textContent = topic.category;
    name.append(bar, label);

    const pct = document.createElement("div");
    pct.className = "pct";
    pct.textContent = percent(topic.share);

    const of = document.createElement("div");
    of.className = "of";
    of.textContent = topic.count.toLocaleString();

    row.append(name, pct, of);
    host.append(row);
  }

  const unknown = summary.byTopic.find((topic) => topic.category === "unknown");
  if (unknown !== undefined) {
    const p = document.createElement("p");
    p.className = "empty";
    p.style.marginTop = "10px";
    p.textContent =
      `“unknown” is ${percent(unknown.share)} of your browsing and that is by design. ` +
      "The list of sites Tise can name on sight leaves out employers, schools, councils " +
      "and neighbourhood services, because a list like that is a profile of you.";
    host.append(p);
  }
}

function renderScorecard(card: Scorecard): void {
  const host = clear(element("scorecard"));
  const lede = element("scorecard-lede");

  lede.textContent =
    "Tise scores itself. Every prediction it has made resolves automatically from what " +
    "you did next — there is no button asking you to confirm. These belong to a question " +
    "the project has since retired, and they are kept so the record stays checkable.";

  if (card.total === 0) {
    note(host, "No predictions made yet.");
    return;
  }

  const facts = document.createElement("table");
  factRow(facts, "Predictions made", card.total.toLocaleString());
  // **These two rows are different questions and this page conflated them until D108.**
  // A `hit` means the topic came back, whatever Tise said about it — so the first row is
  // how often the thing happened and the second is how often Tise called it correctly.
  // Labelling the first one "accuracy" turns an easy target into a good model.
  factRow(
    facts,
    "Topic came back / did not",
    `${card.hit.toLocaleString()} / ${card.miss.toLocaleString()}`,
  );
  factRow(
    facts,
    "…so it happened this often",
    card.outcomeRate === null
      ? "nothing scored yet"
      : `${percent(card.outcomeRate)} of ${card.scored.toLocaleString()}`,
  );
  factRow(
    facts,
    "Tise called it correctly",
    // Null until something resolves. A scorecard reading 0% because nothing has been
    // scored yet is a lie in the shape of a measurement.
    card.accuracy === null
      ? "nothing scored yet"
      : `${percent(card.accuracy)} — ${card.correct.toLocaleString()} of ${card.scored.toLocaleString()}`,
  );
  // D24: a score without a baseline is a number with nothing underneath it. Guessing
  // "came back" every time already scores `outcomeRate`, so this row is what the model
  // actually adds — and on a target that is positive most of the time it is usually
  // very little.
  if (card.outcomeRate !== null) {
    factRow(
      facts,
      "…against always guessing “came back”",
      `${percent(card.outcomeRate)} — the model is ` +
        (card.aheadOfAlwaysYes === 0
          ? "level with it"
          : `${card.aheadOfAlwaysYes > 0 ? "ahead" : "behind"} by ` +
            `${Math.abs(card.aheadOfAlwaysYes)} of ${card.scored}`),
    );
  }
  factRow(facts, "Still open", card.pending.toLocaleString());
  factRow(facts, "Expired — Tise was not watching", card.expired.toLocaleString());
  if (card.withheldByRetiredRule > 0) {
    factRow(
      facts,
      "Withheld by a rule since retired",
      card.withheldByRetiredRule.toLocaleString(),
    );
  }
  host.append(facts);

  const p = document.createElement("p");
  p.className = "empty";
  p.style.marginTop = "10px";
  // D72. A reader who assumes expired means wrong reads a fabricated negative into this.
  p.textContent =
    "Expired is not wrong. It means the window passed while Tise was paused or the " +
    "browser was closed, so nobody scored it — counting those as misses would invent " +
    "failures that never happened. It also means the scored rows are the days Tise " +
    "watched without interruption, which are the days you browsed most, so they are not " +
    "a fair sample of every day.";
  host.append(p);
}

function renderClaims(): void {
  const host = clear(element("claims"));
  for (const target of TARGET_STATUS) {
    const tag = document.createElement("span");
    tag.className = `tag ${target.state}`;
    tag.textContent = target.state;

    const body = document.createElement("div");
    const question = document.createElement("p");
    question.className = "q";
    question.textContent = target.question;
    const detail = document.createElement("p");
    detail.className = "n";
    detail.textContent = target.note;
    body.append(question, detail);

    host.append(tag, body);
  }
  element("purchase-intent").textContent = PURCHASE_INTENT_NOTE;
}

async function render(): Promise<void> {
  const settings = await loadSettings();
  const subtitle = element("subtitle");

  if (settings.consentGrantedAt === null) {
    subtitle.textContent =
      "Tise has stored nothing. Open the toolbar icon to turn it on — until you do, " +
      "there is nothing here to show.";
    for (const id of ["board", "summary", "topics", "scorecard"]) {
      clear(element(id));
      note(element(id), "Nothing collected.");
    }
    renderClaims();
    element("privacy").textContent =
      "Nothing has been collected, and nothing is ever sent anywhere.";
    return;
  }

  const events = await allEvents();
  const sessions = sessionise(events, settings.sessionTimeoutSeconds);
  const transitions = categoryTransitions(sessions);
  const spans = await allSpans();
  const summary = browsingSummary(events, sessions.length, transitions);

  subtitle.textContent = settings.paused
    ? "Paused. Nothing new is being recorded; everything below is what is already stored."
    : "Everything below is computed on this device from what you have browsed.";

  renderBoard(topicBoard(transitions), transitions.length);
  renderSummary(
    summary,
    spans.length,
    Math.round(spans.reduce((total, span) => total + span.activeSeconds, 0) / 60),
  );
  renderTopics(summary);
  renderScorecard(scorecard(await allPredictions()));
  renderClaims();

  element("privacy").textContent =
    "Tise has never sent any of this anywhere. There is no server, no account and no " +
    "network request in the extension at all. Web addresses are reduced to a site name " +
    "before anything is written down — no page contents, no search terms, no form fields.";
}

void render();
