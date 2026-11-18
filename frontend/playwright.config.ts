import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 95_000,
  retries: 0,
  expect: {timeout: 15_000},
  workers: 1,
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    actionTimeout: 20_000,
    launchOptions: {executablePath: process.env.CHROMIUM_PATH || undefined},
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
