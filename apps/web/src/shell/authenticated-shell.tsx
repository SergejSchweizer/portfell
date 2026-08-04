import { requestJson } from "../api/client";
import { EmptyState } from "../components/empty-state";
import { LoadingState } from "../components/loading-state";
import { Panel } from "../components/panel";
import { StatusBadge } from "../components/status-badge";
import { readPublicRuntimeEnv } from "../env";
import { useResource } from "../hooks/use-resource";

type SessionSnapshot = Readonly<{
  user_id?: string;
  email?: string;
  display_name?: string;
  authenticated?: boolean;
}>;

export async function loadSessionSnapshot(): Promise<SessionSnapshot> {
  return requestJson<SessionSnapshot>("/api/session");
}

export function AuthenticatedShell() {
  const env = readPublicRuntimeEnv();
  const session = useResource(loadSessionSnapshot, [env.uiFixture, env.uiFixtureMode]);

  if (session.status === "loading" || session.status === "idle") {
    return <LoadingState label="Loading authenticated shell" />;
  }

  if (session.status === "error") {
    return (
      <EmptyState
        title="Unable to load session"
        description="The authenticated shell could not load the current session snapshot."
      />
    );
  }

  return (
    <section className="portfell-authenticated-shell" data-route="authenticated-shell">
      <Panel title="Session">
        <StatusBadge tone={session.data.authenticated ? "success" : "warning"}>
          {session.data.authenticated ? "authenticated" : "anonymous"}
        </StatusBadge>
        <p>API base: {env.apiBaseUrl}</p>
        <p>Auth mode: {env.authMode}</p>
        <p>API boundary remains server-owned while React takes the shell.</p>
      </Panel>
    </section>
  );
}
