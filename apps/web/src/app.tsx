
import { useEffect, useState, type MouseEvent, type ReactNode } from "react";
import { currentWorkflowPage } from "./routes";
import { ShellFrame } from "./shell/frame";
import { useStatusEventStream } from "./query/use-status-event-stream";

export function App(): ReactNode {
  useStatusEventStream();
  const [pathname, setPathname] = useState(window.location.pathname);
  const page = currentWorkflowPage(pathname);
  const Page = page.component;

  useEffect(() => {
    document.title = `${page.title} · Portfell`;
  }, [page.title]);

  useEffect(() => {
    if (pathname === page.path) return;
    window.history.replaceState({}, "", `${page.path}${window.location.search}${window.location.hash}`);
    setPathname(page.path);
  }, [page.path, pathname]);

  useEffect(() => {
    const updatePathname = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", updatePathname);
    window.addEventListener("portfell:navigation", updatePathname);
    return () => {
      window.removeEventListener("popstate", updatePathname);
      window.removeEventListener("portfell:navigation", updatePathname);
    };
  }, []);

  function navigateInternally(event: MouseEvent<HTMLDivElement>) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest<HTMLAnchorElement>("a[href]");
    if (!link || link.target || link.hasAttribute("download")) return;
    const destination = new URL(link.href);
    if (destination.origin !== window.location.origin) return;
    event.preventDefault();
    window.history.pushState({}, "", `${destination.pathname}${destination.search}${destination.hash}`);
    window.dispatchEvent(new Event("portfell:navigation"));
  }

  return (
    <div onClickCapture={navigateInternally}>
      <ShellFrame currentPage={page.id}>
        <Page />
      </ShellFrame>
    </div>
  );
}
