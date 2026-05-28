import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // React 19's stricter hook compiler ships several advisory rules
  // ("refs", "set-state-in-effect", "immutability",
  // "incompatible-library") that flag patterns this codebase pre-dates.
  // They surface real concerns worth migrating away from but the
  // migration is incremental; hard-failing CI on them would block
  // every PR. Downgraded to `warn` so they show in lint output but
  // don't fail the build. Re-promote to `error` per-rule as code is
  // migrated. Per docs/build/runs/2026-05-28-eng-quality-tier-1.md
  // (TASK-48 Option 1).
  {
    rules: {
      "react-hooks/set-state-in-effect": "warn",
      "react-hooks/refs": "warn",
      "react-hooks/immutability": "warn",
      "react-hooks/incompatible-library": "warn",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
