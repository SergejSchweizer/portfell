import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  loadEodhdCredentialStatus,
  loadEodhdCredentialValue,
  loadMetadataFetchRun,
  postJson,
} from "../api/client";
import type { ApiMetadataFetch } from "../contracts";
import { useResource } from "../hooks/use-resource";

type MetadataFetchContextValue = Readonly<{
  providerKey: string;
  setProviderKey: (value: string) => void;
  fetching: boolean;
  metadataProgress: number;
  metadataStatus: string;
  hasSavedCredential: boolean;
  maskedCredentialLabel: string | null;
  fetchMetadata: () => Promise<void>;
}>;

const MetadataFetchContext = createContext<MetadataFetchContextValue | null>(null);

export function MetadataFetchProvider({ children }: Readonly<{ children: ReactNode }>) {
  const credential = useResource(loadEodhdCredentialStatus, []);
  const savedProviderKey = useResource(loadEodhdCredentialValue, []);
  const [providerKey, setProviderKey] = useState("");
  const [fetching, setFetching] = useState(false);
  const [metadataRunId, setMetadataRunId] = useState<string | null>(null);
  const [metadataProgress, setMetadataProgress] = useState(0);
  const [metadataStatus, setMetadataStatus] = useState("Refresh listing metadata with the operations provider credential.");
  const hasSavedCredential = credential.status === "ready" && credential.data.status === "active";

  useEffect(() => {
    if (savedProviderKey.status === "ready") setProviderKey(savedProviderKey.data.provider_key);
  }, [savedProviderKey.status]);

  useEffect(() => {
    if (!metadataRunId || !fetching) return;
    const activeRunId = metadataRunId;
    let cancelled = false;
    let timeoutId: number | undefined;

    async function pollMetadataRun() {
      try {
        const result = await loadMetadataFetchRun(activeRunId);
        if (cancelled) return;
        setMetadataProgress(result.percent);
        if (result.status === "running") {
          setMetadataStatus(`Fetching metadata: ${result.completed.toLocaleString()} of ${result.total.toLocaleString()} exchanges completed.`);
          timeoutId = window.setTimeout(() => void pollMetadataRun(), 750);
          return;
        }
        setFetching(false);
        setMetadataRunId(null);
        if (result.status === "failed") {
          setMetadataStatus(result.error_code ?? "Metadata fetch failed.");
          return;
        }
        setMetadataStatus(`${(result.row_count ?? 0).toLocaleString()} metadata rows from ${result.exchange_count ?? 0} exchanges loaded.`);
        window.dispatchEvent(new Event("portfell:metadata-updated"));
        window.dispatchEvent(new Event("portfell:workflow-updated"));
      } catch (error) {
        if (cancelled) return;
        setFetching(false);
        setMetadataRunId(null);
        setMetadataStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
      }
    }

    void pollMetadataRun();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [fetching, metadataRunId]);

  async function fetchMetadata() {
    if (fetching) return;
    setFetching(true);
    setMetadataProgress(0);
    setMetadataStatus("Fetching metadata...");
    try {
      const result = await postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {});
      setMetadataRunId(result.metadata_run_id);
      setMetadataProgress(result.percent);
    } catch (error) {
      setMetadataStatus(error instanceof Error ? error.message : "Metadata fetch failed.");
      setFetching(false);
    }
  }

  return (
    <MetadataFetchContext.Provider value={{
      providerKey,
      setProviderKey,
      fetching,
      metadataProgress,
      metadataStatus,
      hasSavedCredential,
      maskedCredentialLabel: credential.status === "ready" ? credential.data.masked_label : null,
      fetchMetadata,
    }}>
      {children}
    </MetadataFetchContext.Provider>
  );
}

export function useMetadataFetch(): MetadataFetchContextValue {
  const context = useContext(MetadataFetchContext);
  if (!context) throw new Error("MetadataFetchProvider is required.");
  return context;
}
