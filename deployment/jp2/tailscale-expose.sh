#!/usr/bin/env bash
set -euo pipefail

mode="${1:-status}"
target="http://127.0.0.1:8080"

require_healthy_app() {
  curl --fail --silent --show-error "$target/api/health" >/dev/null
}

case "$mode" in
  status)
    sudo tailscale serve status
    sudo tailscale funnel status
    ;;
  private)
    require_healthy_app
    sudo tailscale serve --bg --https=8443 8080
    sudo tailscale serve status
    ;;
  public)
    if [[ "${AI_PROJECT_PUBLIC_READY:-}" != "yes" ]]; then
      echo "Refusing public Funnel: set AI_PROJECT_PUBLIC_READY=yes only after authentication and abuse controls are verified." >&2
      exit 1
    fi
    require_healthy_app
    sudo tailscale funnel --bg --https=443 8080
    sudo tailscale funnel status
    ;;
  off)
    sudo tailscale serve reset
    sudo tailscale funnel reset
    ;;
  *)
    echo "usage: $0 {status|private|public|off}" >&2
    exit 2
    ;;
esac

