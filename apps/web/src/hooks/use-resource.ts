import { useEffect, useState } from "react";

export type ResourceState<T> =
  | Readonly<{ status: "idle" }>
  | Readonly<{ status: "loading" }>
  | Readonly<{ status: "ready"; data: T; refreshing?: boolean; refreshError?: Error }>
  | Readonly<{ status: "error"; error: Error }>;

export function useResource<T>(load: () => Promise<T>, deps: readonly unknown[] = []): ResourceState<T> {
  const [state, setState] = useState<ResourceState<T>>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    setState((current) => current.status === "ready"
      ? { status: "ready", data: current.data, refreshing: true }
      : { status: "loading" });
    void load()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          const normalized = error instanceof Error ? error : new Error("resource_load_failed");
          setState((current) => current.status === "ready"
            ? { status: "ready", data: current.data, refreshError: normalized }
            : { status: "error", error: normalized });
        }
      });

    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}
