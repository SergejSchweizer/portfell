import { useEffect } from "react";
import { readPublicRuntimeEnv } from "../env";
import { queryClient } from "./client";
import { queryKeys } from "./keys";

type StatusEvent = Readonly<{
  aggregate_ref: string;
  event_type: string;
  projection_revision: string | null;
  terminal_status: string | null;
}>;

const reconnectDelays = [1_000, 2_000, 5_000, 10_000, 30_000] as const;

function isStatusEvent(value: unknown): value is StatusEvent {
  return typeof value === "object" && value !== null
    && typeof (value as { aggregate_ref?: unknown }).aggregate_ref === "string"
    && typeof (value as { event_type?: unknown }).event_type === "string";
}

function invalidate(event: StatusEvent | null) {
  if (event?.aggregate_ref.startsWith("project:")) {
    const projectId = event.aggregate_ref.slice("project:".length);
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflow(projectId) });
    void queryClient.invalidateQueries({ queryKey: ["page-view", projectId] });
  } else {
    void queryClient.invalidateQueries({ queryKey: queryKeys.projectContext() });
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflowRoot() });
  }
  window.dispatchEvent(new CustomEvent("portfell:status-event", { detail: event }));
}

/** Keep one reconnecting SSE connection for exact hosted status invalidations. */
export function useStatusEventStream() {
  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const { apiBaseUrl } = readPublicRuntimeEnv();
    let closed = false;
    let source: EventSource | null = null;
    let reconnectAttempt = 0;
    let timeoutId: number | undefined;

    const connect = () => {
      if (closed) return;
      source = new EventSource(`${apiBaseUrl}/status-events`);
      source.addEventListener("status", (message) => {
        reconnectAttempt = 0;
        try {
          const parsed: unknown = JSON.parse((message as MessageEvent<string>).data);
          if (isStatusEvent(parsed)) invalidate(parsed);
        } catch {
          invalidate(null);
        }
      });
      source.addEventListener("reset", () => invalidate(null));
      source.onerror = () => {
        source?.close();
        const delay = reconnectDelays[Math.min(reconnectAttempt, reconnectDelays.length - 1)];
        reconnectAttempt += 1;
        timeoutId = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      closed = true;
      source?.close();
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, []);
}
