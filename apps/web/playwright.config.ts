import { defineConfig, devices } from "@playwright/test";

const realStack = process.env.PORTFELL_REAL_STACK === "true";
const prebuiltDist = process.env.PORTFELL_WEB_DIST_DIR !== undefined;

export default defineConfig({
  testDir: "./tests",
  testMatch: realStack ? "**/*.real-stack.spec.ts" : "**/*.spec.ts",
  testIgnore: realStack ? undefined : "**/*.real-stack.spec.ts",
  fullyParallel: !realStack,
  workers: realStack ? 1 : undefined,
  retries: 0,
  use: {
    baseURL: realStack ? "http://127.0.0.1:13000" : "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1080 } } },
  ],
  webServer: realStack ? undefined : {
    command: prebuiltDist ? "npm start" : "npm run build && npm start",
    url: "http://127.0.0.1:3000/health",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
