import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useResource } from "../../src/hooks/use-resource";

describe("useResource", () => {
  it("moves from loading to ready and reloads when dependencies change", async () => {
    const load = vi.fn().mockResolvedValueOnce("first").mockResolvedValueOnce("second");
    const { result, rerender } = renderHook(({ revision }) => useResource(load, [revision]), { initialProps: { revision: 1 } });

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current).toEqual({ status: "ready", data: "first" }));
    rerender({ revision: 2 });
    await waitFor(() => expect(result.current).toEqual({ status: "ready", data: "second" }));
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("normalizes rejected values, retains Error instances, and ignores cancelled loads", async () => {
    const { result } = renderHook(() => useResource(() => Promise.reject("nope")));
    await waitFor(() => expect(result.current).toMatchObject({ status: "error", error: new Error("resource_load_failed") }));

    const sourceError = new Error("provider_failed");
    const errored = renderHook(() => useResource(() => Promise.reject(sourceError)));
    await waitFor(() => expect(errored.result.current).toEqual({ status: "error", error: sourceError }));

    let resolve!: (value: string) => void;
    const pending = new Promise<string>((next) => { resolve = next; });
    const mounted = renderHook(() => useResource(() => pending));
    mounted.unmount();
    resolve("late");
    await new Promise((next) => setTimeout(next, 0));
    expect(mounted.result.current.status).toBe("loading");

    let reject!: (reason: Error) => void;
    const rejected = new Promise<string>((_resolve, next) => { reject = next; });
    const cancelled = renderHook(() => useResource(() => rejected));
    cancelled.unmount();
    reject(new Error("late"));
    await new Promise((next) => setTimeout(next, 0));
    expect(cancelled.result.current.status).toBe("loading");
  });
});
