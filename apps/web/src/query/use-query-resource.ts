import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";

export type ResourceState<T> =
  | Readonly<{ status: "idle" | "loading"; data?: undefined; error?: undefined; refreshing?: false }>
  | Readonly<{ status: "ready"; data: T; error?: undefined; refreshing?: boolean; refreshError?: Error }>
  | Readonly<{ status: "error"; data?: undefined; error: Error; refreshing?: false }>;

export function useQueryResource<T>(
  queryKey: QueryKey,
  queryFn: (signal: AbortSignal) => Promise<T>,
  staleTime?: number,
  retainPreviousData = false,
): ResourceState<T> {
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => queryFn(signal),
    staleTime,
    placeholderData: retainPreviousData ? keepPreviousData : undefined,
  });
  if (query.data !== undefined) {
    return { status: "ready", data: query.data, refreshing: query.isFetching, refreshError: query.error ?? undefined };
  }
  if (query.error) return { status: "error", error: query.error };
  return { status: "loading" };
}
