import { Panel } from "../components/panel";
import { Button } from "../components/button";

export function LoginGateShell() {
  return (
    <main className="camovar-login-gate" data-route="login-gate">
      <Panel title="Sign in to continue">
        <p>The research dashboard is only available after Google authentication.</p>
        <Button variant="primary" type="button">
          Google Login
        </Button>
      </Panel>
    </main>
  );
}
