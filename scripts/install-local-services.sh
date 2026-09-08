#!/bin/zsh
set -euo pipefail

project_root="${0:A:h:h}"
launch_agents="$HOME/Library/LaunchAgents"
caddy_bin="$(command -v caddy)"
uid="$(id -u)"

if [[ ! -x "$project_root/.venv/bin/waitress-serve" ]]; then
  print -u2 "waitress is missing; run .venv/bin/python -m pip install -r requirements.txt first."
  exit 1
fi
if [[ -z "$caddy_bin" ]]; then
  print -u2 "Caddy is missing; install it before registering services."
  exit 1
fi

mkdir -p "$launch_agents" "$project_root/storage/logs" "$project_root/storage/caddy"

sed -e "s|__PROJECT_ROOT__|$project_root|g" "$project_root/deployment/Caddyfile.template" > "$project_root/storage/caddy/Caddyfile"
sed -e "s|__PROJECT_ROOT__|$project_root|g" "$project_root/deployment/com.yala.ai-project.backend.plist.template" > "$launch_agents/com.yala.ai-project.backend.plist"
sed -e "s|__PROJECT_ROOT__|$project_root|g" -e "s|__CADDY_BIN__|$caddy_bin|g" "$project_root/deployment/com.yala.ai-project.caddy.plist.template" > "$launch_agents/com.yala.ai-project.caddy.plist"

for label in com.yala.ai-project.backend com.yala.ai-project.caddy; do
  launchctl bootout "gui/$uid/$label" 2>/dev/null || true
  launchctl bootstrap "gui/$uid" "$launch_agents/$label.plist"
done

print "Services installed. Verify with: $project_root/scripts/status-local-services.sh"
