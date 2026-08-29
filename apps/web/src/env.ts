export type PublicRuntimeEnv = Readonly<{
  apiBaseUrl: string;
  uiFixture: string;
  uiFixtureMode: string;
}>;

function readQueryFixture(): string {
  try {
    return new URL(window.location.href).searchParams.get("fixture") || "";
  } catch {
    return "";
  }
}

export function readPublicRuntimeEnv(): PublicRuntimeEnv {
  const uiFixtureMode = import.meta.env.VITE_PORTFELL_UI_FIXTURE_MODE || "production";
  const queryFixture = readQueryFixture();
  const uiFixture =
    uiFixtureMode === "test" || uiFixtureMode === "local-dev"
      ? import.meta.env.VITE_PORTFELL_UI_FIXTURE || queryFixture
      : "";

  return {
    apiBaseUrl: import.meta.env.VITE_PORTFELL_API_BASE_URL || "/api",
    uiFixture,
    uiFixtureMode,
  };
}

export function canSelectUiFixture(mode = readPublicRuntimeEnv().uiFixtureMode): boolean {
  return mode === "test" || mode === "local-dev";
}
