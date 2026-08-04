
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { loadWorkflow, postJson } from "../api/client";
import { Button } from "../components/button";
import type { ApiMetadataFetch } from "../contracts";
import { useResource } from "../hooks/use-resource";
import { workflowPages, type WorkflowPageId } from "../routes";

export type ShellFrameProps = Readonly<{
  currentPage: WorkflowPageId;
  children: ReactNode;
}>;

export function ShellFrame({ currentPage, children }: ShellFrameProps) {
  const [providerKey, setProviderKey] = useState("");
  const [fetching, setFetching] = useState(false);
  const [status, setStatus] = useState("Enter an EODHD key to refresh listing metadata.");
  const [workflowRevision, setWorkflowRevision] = useState(0);
  const workflow = useResource(loadWorkflow, [workflowRevision]);

  useEffect(() => {
    const refresh = () => setWorkflowRevision((value) => value + 1);
    window.addEventListener("portfell:workflow-updated", refresh);
    return () => window.removeEventListener("portfell:workflow-updated", refresh);
  }, []);

  async function fetchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!providerKey.trim() || fetching) return;
    setFetching(true);
    setStatus("Saving key and fetching metadata…");
    try {
      await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() });
      setProviderKey("");
      const result = await postJson<ApiMetadataFetch>(
        "/api/metadata/fetch-all",
        {},
      );
      setStatus(`${result.row_count.toLocaleString()} metadata rows from ${result.exchange_count} exchanges loaded.`);
      window.dispatchEvent(new Event("portfell:metadata-updated"));
      window.dispatchEvent(new Event("portfell:workflow-updated"));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
    } finally {
      setFetching(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <strong className="brand">Portfell</strong>
          <span className="brand-subtitle">Four-stage statistics workflow</span>
        </div>
        <form className="metadata-fetch" onSubmit={fetchMetadata}>
          <label>
            EODHD key
            <input
              type="password"
              autoComplete="off"
              value={providerKey}
              onChange={(event) => setProviderKey(event.target.value)}
              placeholder="Enter provider key"
            />
          </label>
          <Button type="submit" variant="primary" disabled={!providerKey.trim() || fetching}>
            {fetching ? "Fetching…" : "Fetch all metadata"}
          </Button>
          <output className="metadata-fetch__status" aria-live="polite">{status}</output>
        </form>
      </header>

      <nav className="workflow-nav" aria-label="Portfell workflow">
        {workflowPages.map((page, index) => {
          const locked = workflow.status === "ready" && workflow.data.stages[page.id].status === "locked";
          const label = <><span>{index + 1}</span>{page.title}</>;
          return locked ? <span key={page.id} aria-disabled="true" className="workflow-nav__locked">{label}</span> : <a key={page.id} href={page.path} aria-current={page.id === currentPage ? "page" : undefined}>{label}</a>;
        })}
      </nav>

      <main className="page-content">{children}</main>
    </div>
  );
}
