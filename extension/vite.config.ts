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
  ["ui/welcome/welcome.html", "welcome.html"],
  // Listed one by one rather than copied as a directory, so a file the manifest names and
  // the build forgets fails here instead of on someone's install. `manifest.test.ts`
  // checks the other direction: an icon on disk the manifest never references.
  ["icons/icon16.png", "icons/icon16.png"],
  ["icons/icon32.png", "icons/icon32.png"],
  ["icons/icon48.png", "icons/icon48.png"],
  ["icons/icon128.png", "icons/icon128.png"],
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
        welcome: resolve(here, "ui/welcome/welcome.ts"),
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
