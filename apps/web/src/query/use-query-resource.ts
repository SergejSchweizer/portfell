import { useQuery, type QueryKey } from "@tanstack/react-query";
import type { ResourceState } from "../hooks/use-resource";

export function useQueryResource<T>(
  queryKey: QueryKey,
  queryFn: () => Promise<T>,
  staleTime?: number,
): ResourceState<T> {
  const query = useQuery({ queryKey, queryFn, staleTime });
  if (query.data !== undefined) {
    return { status: "ready", data: query.data, refreshing: query.isFetching, refreshError: query.error ?? undefined };
  }
  if (query.error) return { status: "error", error: query.error };
  return { status: "loading" };
}
