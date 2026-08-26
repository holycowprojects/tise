/**
 * The export, and the reason the privacy feature and the research pipeline are the same
 * mechanism.
 *
 * There is no server. Python never reads the browser's storage. The only way research
 * numbers are ever produced is from a file the user chose to write and chose to hand
 * over — so "you can take your data out" and "this is how the benchmarks were made" are
 * the same sentence, and neither can be true without the other.
 *
 * The file therefore contains **everything Tise holds**, including the user's own
 * category overrides. An export that quietly omitted part of the store would be the
 * visible half of the truth, which is the thing this project is meant not to do.
 *
 * `research/tise_research/data/load.py` reads this format, and
 * `research/fixtures/export_v1.json` is the contract both sides assert against.
 */
import { allEvents } from "./events";
import { loadSettings } from "./settings";
import { CATEGORY_MAP_VERSION } from "../categories/map";
import { SUFFIX_LIST_VERSION } from "../collect/domain";
import type { TiseEvent } from "../types";

/** Bumped only on a breaking change. The Python loader refuses anything it is not. */
export const EXPORT_SCHEMA = "tise.export.v1";

export interface TiseExport {
  readonly schema: string;
  readonly exportedAt: string;
  readonly extensionVersion: string;
  /** Reproducibility: a benchmark means nothing without the map that produced it. */
  readonly categoryMapVersion: number;
  readonly suffixListVersion: number;
  readonly sessionTimeoutSeconds: number;
  readonly rawRetentionDays: number;
  readonly overrides: Readonly<Record<string, string>>;
  readonly events: readonly TiseEvent[];
}

export async function buildExport(options: {
  readonly now: number;
  readonly extensionVersion: string;
}): Promise<TiseExport> {
  const settings = await loadSettings();
  return {
    schema: EXPORT_SCHEMA,
    exportedAt: new Date(options.now).toISOString(),
    extensionVersion: options.extensionVersion,
    categoryMapVersion: CATEGORY_MAP_VERSION,
    suffixListVersion: SUFFIX_LIST_VERSION,
    sessionTimeoutSeconds: settings.sessionTimeoutSeconds,
    rawRetentionDays: settings.rawRetentionDays,
    overrides: settings.overrides,
    events: await allEvents(),
  };
}

/**
 * Serialise for writing to disk.
 *
 * Indented rather than minified: a person who exports their own data should be able to
 * open the file and read it. That is not a nicety — a privacy claim nobody can inspect
 * is a claim nobody can check.
 */
export function serialiseExport(data: TiseExport): string {
  return JSON.stringify(data, null, 2);
}

export function exportFilename(now: number): string {
  return `tise-export-${new Date(now).toISOString().slice(0, 10)}.json`;
}
