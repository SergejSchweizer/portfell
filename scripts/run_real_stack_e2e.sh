#!/usr/bin/env bash
# Run browser tests against the actual Portfell Docker stack and deterministic provider.
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

compose=(docker compose --project-name portfell-e2e --env-file tests/e2e/compose.env -f compose.yaml -f compose.e2e.yaml)
cleanup() {
  "${compose[@]}" down --volumes --remove-orphans
  docker volume rm portfell-e2e-playwright-modules >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${compose[@]}" up --build --detach
for _ in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:13000/health >/dev/null; then
    break
  fi
  sleep 2
done
curl --fail --silent http://127.0.0.1:13000/health >/dev/null

docker run --rm --network host --ipc=host \
  -e CI=true \
  -e PORTFELL_REAL_STACK=true \
  -e npm_config_cache=/tmp/npm-cache \
  --mount "type=bind,src=$root,dst=/workspace" \
  --mount type=volume,source=portfell-e2e-playwright-modules,target=/workspace/apps/web/node_modules \
  -w /workspace/apps/web \
  mcr.microsoft.com/playwright:v1.62.1-noble \
  bash -lc 'npm ci && npm run e2e'
