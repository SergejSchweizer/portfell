
import { useEffect, type ReactNode } from "react";
import { currentWorkflowPage } from "./routes";
import { ShellFrame } from "./shell/frame";

export function App(): ReactNode {
  const page = currentWorkflowPage(window.location.pathname);
  const Page = page.component;

  useEffect(() => {
    document.title = `${page.title} · Portfell`;
  }, [page.title]);

  return (
    <ShellFrame currentPage={page.id}>
      <Page />
    </ShellFrame>
  );
}
