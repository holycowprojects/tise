import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    languageOptions: {
      globals: { chrome: "readonly", indexedDB: "readonly", console: "readonly" },
    },
    rules: {
      // The privacy invariant is enforced by construction, not by convention, but an
      // accidental `any` around the storage boundary is exactly how a full URL would
      // slip past the type system.
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "no-restricted-globals": [
        "error",
        { name: "fetch", message: "Tise makes no network requests. See SPEC.md invariant 1." },
        { name: "XMLHttpRequest", message: "Tise makes no network requests." },
        { name: "WebSocket", message: "Tise makes no network requests." },
      ],
    },
  },
);
