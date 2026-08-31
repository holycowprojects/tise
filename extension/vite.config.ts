import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const here = dirname(fileURLToPath(import.meta.url));

/**
 * Files that are shipped verbatim rather than bundled.
 *
 * `popup.html` is deliberately static and loads `popup.js` by name, so the build stays
 * a flat, readable directory. An MV3 reviewer — or anyone reading the repository —
 * should be able to open `dist/` and recognise every file in it.
 */
const VERBATIM: ReadonlyArray<readonly [string, string]> = [
  ["manifest.json", "manifest.json"],
  ["ui/popup/popup.html", "popup.html"],
  ["ui/dashboard/dashboard.html", "dashboard.html"],
];

function copyStaticFiles(): Plugin {
  return {
    name: "tise-copy-static",
    apply: "build",
    closeBundle() {
      for (const [from, to] of VERBATIM) {
        const target = resolve(here, "dist", to);
        mkdirSync(dirname(target), { recursive: true });
        copyFileSync(resolve(here, from), target);
      }
    },
  };
}

export default defineConfig({
  root: here,
  plugins: [copyStaticFiles()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Readability over bytes. This source is published and is meant to be audited.
    minify: false,
    sourcemap: true,
    target: "chrome116",
    rollupOptions: {
      input: {
        background: resolve(here, "src/background.ts"),
        popup: resolve(here, "ui/popup/popup.ts"),
        dashboard: resolve(here, "ui/dashboard/dashboard.ts"),
      },
      output: {
        format: "es",
        entryFileNames: "[name].js",
        chunkFileNames: "chunks/[name].js",
        assetFileNames: "assets/[name][extname]",
      },
    },
  },
  test: {
    globals: true,
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
