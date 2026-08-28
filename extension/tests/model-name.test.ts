/**
 * The model's name must be derived, never typed.
 *
 * This is the third time the same defect has been found in three places. `model_report.py`
 * printed `fs_2` in the title and every fold-table header of `model.md` after D83 shipped
 * `fs_3`. `predict.ts` wrote `modelName: "logreg_fs2"` onto every stored prediction while
 * the `featureSet` field beside it, which *was* derived, said `fs_3`. In both cases the
 * numbers were right and the label was a version behind, which is the hardest kind of wrong
 * to see: nothing throws, nothing fails, and the record reads as a measurement of something
 * that was never measured.
 *
 * A test that only checked today's value would pass again the next time someone writes a
 * literal that happens to be current. So this checks the **shape of the code** rather than
 * the value: no source file may contain a quoted model name at all.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { FEATURE_SET } from "../src/features/vector";
import { MODEL_NAME, modelName } from "../src/model/train";

const SOURCE_ROOT = join(__dirname, "..", "src");

function sourceFiles(directory: string): string[] {
  const found: string[] = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) {
      found.push(...sourceFiles(path));
    } else if (entry.endsWith(".ts")) {
      found.push(path);
    }
  }
  return found;
}

describe("deriving the model name", () => {
  it("matches the Python mirror's construction", () => {
    // `model_name` in research/.../return_model.py. Drift here would put two different
    // names on the same model in the benchmarks and in the product.
    expect(modelName("fs_2")).toBe("logreg_fs2");
    expect(modelName("fs_3")).toBe("logreg_fs3");
  });

  it("follows the shipped feature set rather than a constant of its own", () => {
    expect(MODEL_NAME).toBe(modelName(FEATURE_SET));
  });

  it("strips every underscore in the set, as Python's str.replace does", () => {
    // JavaScript's `replace(string, …)` takes only the first occurrence, so this is the
    // one line where the two languages diverge by default rather than by choice. The
    // prefix keeps its own underscore in both — `f"logreg_{...}"` on the Python side.
    expect(modelName("fs_3_b")).toBe("logreg_fs3b");
  });
});

describe("no source file names a model in a string literal", () => {
  const files = sourceFiles(SOURCE_ROOT);

  it("found source files to check", () => {
    // A glob that silently matches nothing would make every assertion below vacuous.
    expect(files.length).toBeGreaterThan(10);
  });

  it("contains no quoted logreg_* name outside the deriving function", () => {
    const offenders: string[] = [];
    for (const path of files) {
      const text = readFileSync(path, "utf-8");
      for (const [index, line] of text.split("\n").entries()) {
        const trimmed = line.trim();
        // Prose may name a model — the entry explaining this very bug does. What must not
        // exist is a *value*, so comment lines are not offenders.
        if (trimmed.startsWith("*") || trimmed.startsWith("//") || trimmed.startsWith("/*")) {
          continue;
        }
        // The template inside `modelName` itself is the one legitimate occurrence in code,
        // and it is a template rather than a completed name.
        if (line.includes("`logreg_${")) continue;
        if (/["'`]logreg_[a-z0-9]/i.test(line)) {
          offenders.push(`${path}:${index + 1}: ${line.trim()}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});
