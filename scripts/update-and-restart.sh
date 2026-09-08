#!/bin/zsh
set -euo pipefail

project_root="${0:A:h:h}"
uid="$(id -u)"
cd "$project_root"

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  print -u2 "Refusing to update: commit or stash tracked changes first."
  exit 1
fi

git pull --ff-only
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/build-grammar-book-assets.py
(cd frontend && npm ci && npm run build)
PYTHONPYCACHEPREFIX=/private/tmp/ai-project-pycache .venv/bin/python -m py_compile run.py backend/__init__.py
mkdir -p storage/caddy
sed -e "s|__PROJECT_ROOT__|$project_root|g" deployment/Caddyfile.template > storage/caddy/Caddyfile

launchctl kickstart -k "gui/$uid/com.yala.ai-project.backend"
launchctl kickstart -k "gui/$uid/com.yala.ai-project.caddy"

for _ in {1..10}; do
  if curl --fail --silent http://127.0.0.1:8080/api/health >/dev/null; then
    print "Update complete and service healthy."
    exit 0
  fi
  sleep 1
done

print -u2 "Services restarted but health check failed. See storage/logs/*.launchd.*.log"
exit 1
