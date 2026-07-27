import type { ReactNode } from "react";

export type StatusTone = "neutral" | "success" | "warning" | "danger" | "stale" | "running";

export type StatusBadgeProps = Readonly<{
  tone?: StatusTone;
  children: ReactNode;
}>;

export function StatusBadge({ tone = "neutral", children }: StatusBadgeProps) {
  return <span className={`camovar-status-badge camovar-status-badge--${tone}`}>{children}</span>;
}
