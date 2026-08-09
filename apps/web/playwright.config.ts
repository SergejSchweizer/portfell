import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.ts",
  fullyParallel: true,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1080 } } },
    { name: "tablet", use: { ...devices["iPad Pro 11"], viewport: { width: 1024, height: 1366 } } },
    { name: "mobile", use: { ...devices["iPhone 13"], viewport: { width: 390, height: 844 } } },
  ],
});
