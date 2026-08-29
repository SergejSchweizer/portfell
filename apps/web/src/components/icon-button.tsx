import type { ButtonHTMLAttributes, ReactNode } from "react";

export type IconButtonProps = Readonly<ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  children: ReactNode;
}>;

export function IconButton({ label, children, className, ...props }: IconButtonProps) {
  return <button {...props} className={["portfell-icon-button", className].filter(Boolean).join(" ")} aria-label={label} title={label}>{children}</button>;
}