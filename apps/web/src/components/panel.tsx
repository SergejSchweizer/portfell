import type { ReactNode } from "react";

export type PanelProps = Readonly<{
  title?: ReactNode;
  children: ReactNode;
}>;

export function Panel({ title, children }: PanelProps) {
  return (
    <section className="portfell-panel">
      {title ? <h2>{title}</h2> : null}
      {children}
    </section>
  );
}
