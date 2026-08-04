
import { useEffect, useState, type ReactNode } from "react";
import { currentWorkflowPage } from "./routes";
import { ShellFrame } from "./shell/frame";

export function App(): ReactNode {
  const [pathname, setPathname] = useState(window.location.pathname);
  const page = currentWorkflowPage(pathname);
  const Page = page.component;

  useEffect(() => {
    document.title = `${page.title} · Portfell`;
  }, [page.title]);

  useEffect(() => {
    const updatePathname = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", updatePathname);
    window.addEventListener("portfell:navigation", updatePathname);
    return () => {
      window.removeEventListener("popstate", updatePathname);
      window.removeEventListener("portfell:navigation", updatePathname);
    };
  }, []);

  return (
    <ShellFrame currentPage={page.id}>
      <Page />
    </ShellFrame>
  );
}
