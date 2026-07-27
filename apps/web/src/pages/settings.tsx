import { Button } from "../components/button";
import { Panel } from "../components/panel";

export function SettingsPage() {
  return (
    <section data-route="settings-page">
      <Panel title="Settings">
        <label>
          Theme
          <select defaultValue="system">
            <option value="system">System</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
        <Button type="button" variant="secondary">
          Save settings
        </Button>
      </Panel>
    </section>
  );
}
