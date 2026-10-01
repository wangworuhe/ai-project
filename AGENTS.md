# ai-project agent instructions

## Project overview

- Flask + Waitress API, Vue 3 frontend, Caddy reverse proxy, and SQLite data.
- Deterministic grammar grading is authoritative. Mecha/Codex only adds asynchronous explanations and must never silently change deterministic grades.
- Runtime data and secrets are not stored in Git. Preserve `storage/` and `.env` during every update.

## Required validation

Before committing or deploying application changes, run:

```bash
.venv/bin/python -m unittest discover -s tests
cd frontend && npm run lint && npm run build
git diff --check
```

Existing frontend bundle-size warnings are informational; test, lint, build, or schema failures are blocking.

## Production deployment: jp2

- The Mac is a development checkout only. Its ai-project backend, Caddy, and grammar AI review LaunchAgents are disabled; do not re-enable them as part of a jp2 release.
- Target SSH alias: `jp2`.
- Tailscale device: `yala-jp` (`yala-jp.tailaafe48.ts.net`). Tailscale runs natively on the host, not in Docker.
- Tailscale SSH is enabled for private administration; the existing public-key SSH path remains the deployment fallback.
- Application checkout: `/opt/ai-project/current`.
- Persistent runtime data: `/srv/ai-project/storage`.
- Secrets: `/etc/ai-project/ai-project.env`, owned by root and mode `0600`.
- Backups: `/var/backups/ai-project`.
- Mecha database backups: `/var/backups/ai-project/mecha`.
- Compose file: `deployment/jp2/compose.yaml`.
- App containers use Linux host networking but bind services only to loopback: Waitress `127.0.0.1:5000`, Caddy `127.0.0.1:8080`.
- Mecha is a separate host service on `127.0.0.1:21212`; never expose Mecha with Tailscale Funnel.
- Mecha runs as the existing `ubuntu` user from `/usr/local/bin/mecha`, with source/runtime files in `/opt/mecha/current`, state in `/home/ubuntu/.mecha`, and a user systemd unit sourced from `deployment/jp2/mecha.service`.
- Mecha uses `ubuntu`'s rootless Docker daemon at `/run/user/1001/docker.sock`; keep the system Docker daemon separate for ai-project Compose.
- Build Mecha from revision `8ceced7f` with `deployment/jp2/mecha-rootless.patch`; validate with `scripts/smoke-mecha-worker.py` before releasing the AI runner.
- The default Tailscale Serve/Funnel design needs no new OCI or host-firewall ingress rule. If a future design requires public-interface binding, document the exact protocol, port, and allowed source before opening it.

Read `docs/jp2-deployment.md` before changing production deployment, data paths, Tailscale exposure, Mecha, or release scripts.

## Release safety

1. Keep `master` clean and pushed before deployment.
2. Create a consistent SQLite backup before replacing containers.
3. Never overwrite `/srv/ai-project/storage` with an empty checkout or image directory.
4. Build and start with `deployment/jp2/deploy.sh`; verify `/api/health` and core grammar APIs.
5. Deploy privately with Tailscale Serve first. Funnel is allowed only after application authentication and abuse controls are in place.
6. Do not advertise jp2 as an exit node or subnet router without an explicit networking requirement and route scope.
7. Project deployment details belong in this repository, not in the user-level `vps` skill. The `vps` skill only records host/Tailscale infrastructure changes.
8. Do not start `ai-review-runner` until Mecha is healthy, `grammar-mistake-explainer` is online, and a real schema-valid task has passed.
