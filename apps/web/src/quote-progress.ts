/** Project-relative wording for the shared historical-data update action. */

import type { ApiQuoteFetch } from "./contracts";

function remainingTime(startedAt: number | undefined, completed: number, total: number): string {
  if (!startedAt || completed <= 0 || total <= completed) return " · estimating remaining time…";
  const elapsedSeconds = (Date.now() - startedAt * 1_000) / 1_000;
  if (elapsedSeconds <= 0) return " · estimating remaining time…";
  const remainingSeconds = Math.ceil((elapsedSeconds / completed) * (total - completed));
  if (remainingSeconds < 60) return " · less than 1 min remaining";
  const hours = Math.floor(remainingSeconds / 3_600);
  const minutes = Math.ceil((remainingSeconds % 3_600) / 60);
  return hours > 0
    ? ` · about ${hours}h ${minutes}m remaining`
    : ` · about ${minutes} min remaining`;
}

/**
 * The backend progresses through quote, companion-data, and Silver tasks.
 * Map that work onto the project's selected ISIN count so the UI stays useful
 * without exposing the implementation-specific task count.
 */
export function historicalDataUpdateLabel(run: ApiQuoteFetch | null): string {
  if (!run) return "Preparing historical-data update…";
  const totalTasks = run.total ?? 0;
  const completedTasks = run.completed ?? 0;
  const percent = Math.min(100, Math.max(0, run.percent ?? (totalTasks > 0
    ? Math.round((completedTasks / totalTasks) * 100)
    : 0)));
  const projectIsins = run.selected_listing_count ?? 0;
  if (projectIsins <= 0) return `Updating historical data · ${percent}%${remainingTime(run.started_at, completedTasks, totalTasks)}`;
  const completedIsins = Math.min(projectIsins, Math.round((projectIsins * percent) / 100));
  return `Updating historical data · ${completedIsins.toLocaleString()} / ${projectIsins.toLocaleString()} ISINs · ${percent}%${remainingTime(run.started_at, completedTasks, totalTasks)}`;
}
