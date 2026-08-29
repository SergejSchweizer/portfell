import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useDebouncedSave } from "../../src/hooks/use-debounced-save";

describe("useDebouncedSave", () => {
  afterEach(() => vi.useRealTimers());

  it("persists only the latest value after rapid changes", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue(undefined);
    const { result } = renderHook(() => useDebouncedSave(save, vi.fn()));

    act(() => {
      result.current.schedule("first");
      result.current.schedule("latest");
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });

    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith("latest");
  });

  it("discards a pending save when cancelled or unmounted", async () => {
    vi.useFakeTimers();
    const save = vi.fn().mockResolvedValue(undefined);
    const { result, unmount } = renderHook(() => useDebouncedSave(save, vi.fn()));

    act(() => {
      result.current.schedule("cancelled");
      result.current.cancel();
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(save).not.toHaveBeenCalled();

    act(() => result.current.schedule("unmounted"));
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(250); });
    expect(save).not.toHaveBeenCalled();
  });
});