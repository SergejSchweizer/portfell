import { getFixtureScenario, mockResponseFor } from "./fixtures/scenarios";
import { readPublicRuntimeEnv } from "./env";

function mockAllowed(): boolean {
  const env = readPublicRuntimeEnv();
  return env.uiFixtureMode === "test" || env.uiFixtureMode === "local-dev";
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

export async function maybeMockJson<T>(path: string, init: RequestInit = {}): Promise<T | null> {
  const env = readPublicRuntimeEnv();
  if (!env.uiFixture || !mockAllowed()) return null;
  const scenario = getFixtureScenario(env.uiFixture);
  if (!scenario) return null;
  if (env.uiFixture === "slow-api") {
    await delay(120);
  }
  const method = (init.method || "GET").toUpperCase();
  return (mockResponseFor(path, env.uiFixture, method) as T | null) ?? null;
}
