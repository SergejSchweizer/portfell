import type { ReactNode } from "react";
import { routeTitle, routes } from "../routes";
import { Button } from "../components/button";
import { FixtureSelector } from "../components/fixture-selector";
import { Panel } from "../components/panel";
import { StatusBadge } from "../components/status-badge";

export type ShellFrameProps = Readonly<{
  pathname: string;
  children: ReactNode;
}>;

export function ShellFrame({ pathname, children }: ShellFrameProps) {
  const title = routeTitle(pathname);
  const shellRoutes = routes.filter((route) => route.shell);

  return (
    <div className="camovar-shell-frame">
      <aside className="camovar-shell-sidebar" aria-label="Camovar navigation">
        <Panel title="Camovar">
          <StatusBadge tone="success">authenticated</StatusBadge>
          <p>React shell scaffold.</p>
        </Panel>
        <Panel title="Routes">
          <nav aria-label="Research funnel">
            <ul className="camovar-shell-nav">
              {shellRoutes.map((route) => (
                <li key={route.path}>
                  <a aria-current={route.path === pathname ? "page" : undefined} href={route.path}>
                    {route.title}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        </Panel>
        <Panel title="Account">
          <Button type="button" variant="secondary">
            Refresh session
          </Button>
        </Panel>
        <Panel title="Fixture">
          <FixtureSelector />
        </Panel>
      </aside>
      <section className="camovar-shell-main">
        <header className="camovar-shell-header">
          <h1>{title}</h1>
          <p>API boundary remains server-owned while React takes the shell.</p>
        </header>
        {children}
      </section>
    </div>
  );
}
