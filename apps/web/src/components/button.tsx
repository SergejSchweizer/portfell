import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger";

export type ButtonProps = Readonly<
  ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: ButtonVariant;
    children: ReactNode;
  }
>;

export function Button({ variant = "secondary", className, children, ...props }: ButtonProps) {
  return (
    <button {...props} className={["portfell-button", `portfell-button--${variant}`, className].filter(Boolean).join(" ")}>
      {children}
    </button>
  );
}
