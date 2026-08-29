export type ProgressSnapshot = Readonly<{
  runId: string;
  percent: number;
}>;

export function progressPercent(completed: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(100, Math.max(0, completed / total * 100));
}

export function nextProgressSnapshot(
  previous: ProgressSnapshot | null,
  runId: string,
  percent: number,
): ProgressSnapshot {
  const boundedPercent = Math.min(100, Math.max(0, percent));
  if (previous?.runId !== runId) return { runId, percent: boundedPercent };
  return { runId, percent: Math.max(previous.percent, boundedPercent) };
}