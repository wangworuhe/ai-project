#!/bin/zsh
set -euo pipefail

uid="$(id -u)"
for label in com.yala.ai-project.backend com.yala.ai-project.caddy; do
  print -- "--- $label ---"
  launchctl print "gui/$uid/$label" | rg 'state =|pid =|last exit code' || true
done

print -- "--- local health ---"
curl --fail --silent --show-error http://127.0.0.1:8080/api/health
print
print -- "--- Tailscale Serve ---"
tailscale serve status 2>&1 || true
