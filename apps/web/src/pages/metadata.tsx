import { Button } from "../components/button";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import { requestJson } from "../api/client";
import { useResource } from "../hooks/use-resource";
import type { ApiFieldOptions } from "../contracts";

async function loadFieldOptions(): Promise<ApiFieldOptions> {
  return requestJson<ApiFieldOptions>("/api/metadata-filter/options");
}

export function MetadataPage() {
  const options = useResource(loadFieldOptions);

  if (options.status === "loading" || options.status === "idle") {
    return <LoadingState label="Loading metadata options" />;
  }

  if (options.status === "error") {
    return <EmptyState title="Metadata unavailable" description="Metadata options could not be loaded." />;
  }

  return (
    <section data-route="metadata-page">
      <Panel title="Project definition">
        <form>
          <label>
            Exchange
            <select defaultValue="">
              <option value="">Any</option>
              {options.data.exchange.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input placeholder="UCITS ETF" />
          </label>
          <Button type="button" variant="primary">
            Create New Project
          </Button>
        </form>
      </Panel>
      <EmptyState title="No project selected" description="Choose a project or create one." />
    </section>
  );
}
