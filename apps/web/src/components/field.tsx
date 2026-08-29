import type { ReactNode } from "react";

export type FieldProps = Readonly<{
  label: string;
  htmlFor: string;
  children: ReactNode;
  hint?: string;
  error?: string;
}>;

export function Field({ label, htmlFor, children, hint, error }: FieldProps) {
  return <label className="portfell-field" htmlFor={htmlFor}><span>{label}</span>{children}<small role={error ? "alert" : undefined}>{error ?? hint ?? " "}</small></label>;
}