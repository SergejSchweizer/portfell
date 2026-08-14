import type { ReactNode } from "react";
import { LoaderCircle } from "lucide-react";

export type LoadingStateProps = Readonly<{
  label?: string;
  children?: ReactNode;
}>;

export function LoadingIndicator({ label, compact = false }: Readonly<{ label: string; compact?: boolean }>) {
  return (
    <div className="portfell-loading-indicator" data-compact={compact} role="status" aria-label={label} aria-live="polite" aria-busy="true">
      <span><LoaderCircle aria-hidden="true" />{label}</span>
      <progress aria-label={label} />
    </div>
  );
}

export function LoadingState({ label = "Loading", children }: LoadingStateProps) {
  return (
    <section className="portfell-loading-state" aria-label={label} aria-busy="true">
      <LoadingIndicator label={label} />
      {children}
    </section>
  );
}
