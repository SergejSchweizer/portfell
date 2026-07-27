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
    <button {...props} className={["camovar-button", `camovar-button--${variant}`, className].filter(Boolean).join(" ")}>
      {children}
    </button>
  );
}
