import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  // Manuscript rendering has a separate config because the public companion
  // repository must remain runnable without a private sibling book checkout.
  testIgnore: "book-review.spec.ts",
  // Browser media mocks and the separately served Quarto review are stable
  // when a reader runs one lesson at a time. Serial workers also prevent a
  // resource-constrained Windows laptop from terminating Chromium while a
  // chapter capture and a book review compete for the same process budget.
  workers: 1,
  globalSetup: "./tests/app-server.setup.ts",
  use: {
    baseURL: process.env.CAPTURE_BASE_URL ?? "http://127.0.0.1:8765",
    channel: process.env.PW_CHANNEL === "msedge" ? "msedge" : undefined,
    trace: "retain-on-failure",
  },
});
