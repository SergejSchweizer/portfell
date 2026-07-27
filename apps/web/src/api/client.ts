import { maybeMockJson } from "../mock-api";

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const mocked = await maybeMockJson<T>(path, init);
  if (mocked !== null) return mocked;
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      accept: "application/json",
      ...(init.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    throw new Error(`request_failed_${response.status}`);
  }

  return (await response.json()) as T;
}
