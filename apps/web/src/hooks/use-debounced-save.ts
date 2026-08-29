import { useEffect, useRef } from "react";

type PendingSave<T> = Readonly<{
  value: T;
  version: number;
}>;

export function useDebouncedSave<T>(
  save: (value: T) => Promise<unknown>,
  onError: (error: unknown) => void,
  delayMilliseconds = 250,
) {
  const saveRef = useRef(save);
  const errorRef = useRef(onError);
  const timeout = useRef<number | undefined>(undefined);
  const inFlight = useRef(false);
  const pending = useRef<PendingSave<T> | null>(null);
  const version = useRef(0);
  saveRef.current = save;
  errorRef.current = onError;

  async function flush() {
    if (inFlight.current) return;
    const next = pending.current;
    if (!next) return;
    pending.current = null;
    inFlight.current = true;
    try {
      await saveRef.current(next.value);
    } catch (error) {
      if (next.version === version.current) errorRef.current(error);
    } finally {
      inFlight.current = false;
      if (pending.current !== null) void flush();
    }
  }

  function schedule(value: T) {
    version.current += 1;
    pending.current = { value, version: version.current };
    if (timeout.current !== undefined) window.clearTimeout(timeout.current);
    timeout.current = window.setTimeout(() => {
      timeout.current = undefined;
      void flush();
    }, delayMilliseconds);
  }

  function cancel() {
    version.current += 1;
    pending.current = null;
    if (timeout.current !== undefined) window.clearTimeout(timeout.current);
    timeout.current = undefined;
  }

  useEffect(() => () => cancel(), []);

  return { cancel, schedule };
}