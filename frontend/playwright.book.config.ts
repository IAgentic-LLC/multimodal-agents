import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "book-review.spec.ts",
  workers: 1,
  globalSetup: "./tests/book-server.setup.ts",
  use: {
    trace: "retain-on-failure",
  },
});
