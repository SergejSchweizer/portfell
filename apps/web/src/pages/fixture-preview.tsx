import { FixtureSelector } from "../components/fixture-selector";
import { Panel } from "../components/panel";
import { listFixtureScenarioNames } from "../fixtures/scenarios";
import { readPublicRuntimeEnv } from "../env";

export function FixturePreviewPage() {
  const env = readPublicRuntimeEnv();

  return (
    <section data-route="fixture-preview-page">
      <Panel title="Fixture preview">
        <FixtureSelector />
        <p>Mode: {env.uiFixtureMode}</p>
        <p>Current fixture: {env.uiFixture || "default"}</p>
      </Panel>
      <Panel title="Available scenarios">
        <ul>
          {listFixtureScenarioNames().map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      </Panel>
    </section>
  );
}
