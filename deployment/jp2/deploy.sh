#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compose_file="$repo_root/deployment/jp2/compose.yaml"
storage_dir="/srv/ai-project/storage"
env_file="/etc/ai-project/ai-project.env"
backup_dir="/var/backups/ai-project"
public_mode="${1:-}"
if [[ -n "$public_mode" && "$public_mode" != "--public" ]]; then
  echo "usage: $0 [--public]" >&2
  exit 2
fi
if [[ "$public_mode" == "--public" ]]; then
  if ! sudo grep -qx 'AI_PROJECT_AUTH_ENABLED=yes' "$env_file"; then
    echo "Public release requires application authentication enabled." >&2
    exit 1
  fi
  if ! sudo grep -qx 'AI_PROJECT_PUBLIC_ACCESS=yes' "$env_file"; then
    echo "Public release requires AI_PROJECT_PUBLIC_ACCESS=yes in the application environment." >&2
    exit 1
  fi
  sudo docker compose -f "$repo_root/deployment/jp2/public.compose.yaml" config --quiet
fi

if ! sudo test -f "$env_file"; then
  echo "Missing $env_file; copy ai-project.env.example and set production secrets." >&2
  exit 1
fi
if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=no)" ]]; then
  echo "Refusing deployment from a dirty tracked worktree." >&2
  exit 1
fi

sudo install -d -m 0750 -o ubuntu -g ubuntu "$storage_dir"
sudo install -d -m 0700 -o root -g root "$backup_dir"
sudo python3 "$repo_root/deployment/jp2/backup_sqlite.py" \
  "$storage_dir/database/database.db" "$backup_dir"
sudo python3 "$repo_root/deployment/jp2/backup_sqlite.py" \
  "/home/ubuntu/.mecha/mecha.db" "$backup_dir/mecha"

if sudo test -f "$storage_dir/database/auth.db"; then
  sudo python3 "$repo_root/deployment/jp2/backup_sqlite.py" \
    "$storage_dir/database/auth.db" "$backup_dir/auth"
fi

sudo docker compose -f "$compose_file" build --pull
sudo docker compose -f "$compose_file" up -d --remove-orphans

for _ in $(seq 1 30); do
  if curl --fail --silent http://127.0.0.1:8080/api/health >/dev/null; then
    if [[ "$public_mode" == "--public" ]]; then
      auth_status=$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8080/api/auth/session)
      if [[ "$auth_status" != "401" ]]; then
        echo "Refusing public cutover: unauthenticated session must return 401." >&2
        exit 1
      fi
      sudo install -d -m 0700 /srv/ai-project/caddy-public/data /srv/ai-project/caddy-public/config
      sudo docker compose -f "$repo_root/deployment/jp2/public.compose.yaml" run --rm --no-deps gateway caddy validate --config /etc/caddy/Caddyfile
      sudo docker compose -f "$repo_root/deployment/jp2/public.compose.yaml" up -d --force-recreate
    fi
    sudo docker compose -f "$compose_file" ps
    echo "ai-project deployment is healthy on http://127.0.0.1:8080"
    exit 0
  fi
  sleep 2
done

sudo docker compose -f "$compose_file" ps
sudo docker compose -f "$compose_file" logs --tail=100
echo "Deployment failed health verification." >&2
exit 1
