import { Panel } from "../components/panel";
import { StatusBadge } from "../components/status-badge";

export function ValidationPage() {
  return (
    <section data-route="validation-page">
      <Panel title="Validation">
        <StatusBadge tone="warning">warning</StatusBadge>
        <p>Review readiness, risk, and policy checks.</p>
      </Panel>
    </section>
  );
}
