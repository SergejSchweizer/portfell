import type { ChangeEvent } from "react";
import { canSelectUiFixture, readPublicRuntimeEnv } from "../env";
import { listFixtureScenarioNames } from "../fixtures/scenarios";

export function FixtureSelector() {
  const env = readPublicRuntimeEnv();
  if (!canSelectUiFixture(env.uiFixtureMode)) return null;

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.currentTarget.value;
    const url = new URL(window.location.href);
    if (next) url.searchParams.set("fixture", next);
    else url.searchParams.delete("fixture");
    window.location.href = url.toString();
  }

  return (
    <label className="camovar-fixture-selector">
      Fixture scenario
      <select value={env.uiFixture} onChange={handleChange}>
        <option value="">default</option>
        {listFixtureScenarioNames().map((name) => (
          <option key={name} value={name}>
            {name}
          </option>
        ))}
      </select>
    </label>
  );
}
