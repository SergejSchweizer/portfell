import type { ReactNode } from "react";

export type LoadingStateProps = Readonly<{
  label?: string;
  children?: ReactNode;
}>;

export function LoadingState({ label = "Loading", children }: LoadingStateProps) {
  return (
    <section className="portfell-loading-state" aria-label={label}>
      <p>{label}</p>
      {children}
    </section>
  );
}
