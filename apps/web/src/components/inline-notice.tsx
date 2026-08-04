import type { ReactNode } from "react";

export type InlineNoticeTone = "information" | "success" | "warning" | "error";
export type InlineNoticeProps = Readonly<{ tone?: InlineNoticeTone; children: ReactNode }>;

export function InlineNotice({ tone = "information", children }: InlineNoticeProps) {
  return <p className={`portfell-inline-notice portfell-inline-notice--${tone}`} role={tone === "error" ? "alert" : "status"}>{children}</p>;
}