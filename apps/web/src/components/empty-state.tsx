import type { ReactNode } from "react";

export type EmptyStateProps = Readonly<{
  title: string;
  description: string;
  action?: ReactNode;
}>;

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <section className="portfell-empty-state" aria-label={title}>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  );
}
