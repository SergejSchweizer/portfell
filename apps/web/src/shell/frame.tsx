
import { useState, type FormEvent, type ReactNode } from "react";
import { postJson } from "../api/client";
import { Button } from "../components/button";
import type { ApiMetadataFetch } from "../contracts";
import { workflowPages, type WorkflowPageId } from "../routes";

export type ShellFrameProps = Readonly<{
  currentPage: WorkflowPageId;
  children: ReactNode;
}>;

export function ShellFrame({ currentPage, children }: ShellFrameProps) {
  const [providerKey, setProviderKey] = useState("");
  const [fetching, setFetching] = useState(false);
  const [status, setStatus] = useState("Enter an EODHD key to refresh listing metadata.");

  async function fetchMetadata(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!providerKey.trim() || fetching) return;
    setFetching(true);
    setStatus("Saving key and fetching metadata…");
    try {
      await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() });
      setProviderKey("");
      const result = await postJson<ApiMetadataFetch>(
        "/api/metadata-filter/fetch-all-metadata",
        {},
      );
      setStatus(`${result.row_count.toLocaleString()} metadata rows from ${result.exchange_count} exchanges loaded.`);
      window.dispatchEvent(new Event("portfell:metadata-updated"));
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
        {workflowPages.map((page, index) => (
          <a
            key={page.id}
            href={page.path}
            aria-current={page.id === currentPage ? "page" : undefined}
          >
            <span>{index + 1}</span>
            {page.title}
          </a>
        ))}
      </nav>

      <main className="page-content">{children}</main>
    </div>
  );
}
