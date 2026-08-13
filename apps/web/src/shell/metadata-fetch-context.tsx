import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  loadEodhdCredentialStatus,
  loadMetadataFetchRun,
  postJson,
} from "../api/client";
import { nextProgressSnapshot } from "../computation-progress";
import type { ApiCredentialStatus, ApiMetadataFetch } from "../contracts";
import { useResource } from "../hooks/use-resource";

type MetadataFetchContextValue = Readonly<{
  providerKey: string;
  setProviderKey: (value: string) => void;
  fetching: boolean;
  metadataProgress: number;
  metadataStatus: string;
  hasSavedCredential: boolean;
  canFetchMetadata: boolean;
  maskedCredentialLabel: string | null;
  fetchMetadata: () => Promise<void>;
}>;

const MetadataFetchContext = createContext<MetadataFetchContextValue | null>(null);

export function MetadataFetchProvider({ children }: Readonly<{ children: ReactNode }>) {
  const credential = useResource(loadEodhdCredentialStatus, []);
  const [providerKey, setProviderKey] = useState("");
  const [savedCredential, setSavedCredential] = useState<ApiCredentialStatus | null>(null);
  const [fetching, setFetching] = useState(false);
  const [metadataRunId, setMetadataRunId] = useState<string | null>(null);
  const [metadataProgress, setMetadataProgress] = useState(0);
  const [metadataStatus, setMetadataStatus] = useState("Refresh listing metadata with the operations provider credential.");
  const credentialStatus = savedCredential ?? (credential.status === "ready" ? credential.data : null);
  const hasSavedCredential = credentialStatus?.status === "active";
  const canFetchMetadata = hasSavedCredential || providerKey.trim().length > 0;

  useEffect(() => {
    if (!metadataRunId || !fetching) return;
    const activeRunId = metadataRunId;
    let cancelled = false;
    let timeoutId: number | undefined;

    async function pollMetadataRun() {
      try {
        const result = await loadMetadataFetchRun(activeRunId);
        if (cancelled) return;
        setMetadataProgress((previous) => nextProgressSnapshot(
          { runId: activeRunId, percent: previous }, activeRunId, result.percent,
        ).percent);
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
    if (fetching || !canFetchMetadata) return;
    setFetching(true);
    setMetadataProgress(0);
    setMetadataStatus("Fetching metadata...");
    try {
      const pendingKey = providerKey.trim();
      if (pendingKey) {
        const status = await postJson<ApiCredentialStatus>("/api/credentials/eodhd", {
          provider_key: pendingKey,
        });
        setSavedCredential(status);
        setProviderKey("");
      }
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
      canFetchMetadata,
      maskedCredentialLabel: credentialStatus?.masked_label ?? null,
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
