import { QueryClient } from "@tanstack/react-query";

const fiveMinutes = 5 * 60_000;
const fifteenMinutes = 15 * 60_000;

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      gcTime: 15 * 60_000,
      retry: 2,
      retryDelay: (attempt) => Math.min(1_000 * 2 ** attempt, 8_000),
      staleTime: fifteenMinutes,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
});

export const queryTiming = { completed: fiveMinutes, volatile: 15_000 } as const;
