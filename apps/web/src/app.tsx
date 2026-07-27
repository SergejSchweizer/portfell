import { useEffect, useMemo, type ReactNode } from "react";
import { matchRoute, routeTitle } from "./routes";
import { ShellFrame } from "./shell/frame";

export function App(): ReactNode {
  const pathname = window.location.pathname;
  const route = useMemo(() => matchRoute(pathname), [pathname]);

  useEffect(() => {
    document.title = routeTitle(pathname);
  }, [pathname]);

  const content = route.element();
  return route.shell ? <ShellFrame pathname={pathname}>{content}</ShellFrame> : content;
}
