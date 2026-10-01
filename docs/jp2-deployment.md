# jp2 production deployment

This document is the source of truth for deploying ai-project to jp2. Host-wide VPS facts remain in the external `vps` skill; application releases, paths, data, and rollback procedures stay here.

## Architecture and paths

- Host: SSH alias `jp2`, Ubuntu ARM64.
- Tailscale: native host service, node `yala-jp`, MagicDNS `yala-jp.tailaafe48.ts.net`.
- Tailscale SSH: enabled for Tailnet administration; public-key SSH through alias `jp2` remains available as a fallback.
- Checkout: `/opt/ai-project/current`.
- Compose: `/opt/ai-project/current/deployment/jp2/compose.yaml`.
- Secrets: `/etc/ai-project/ai-project.env` (`root:root`, mode `0600`).
- Persistent data: `/srv/ai-project/storage`.
- Deploy backups: `/var/backups/ai-project`.
- Mecha SQLite backups: `/var/backups/ai-project/mecha`.
- Loopback endpoints: Caddy `127.0.0.1:8080`, Waitress `127.0.0.1:5000`, Mecha `127.0.0.1:21212`.
- Mecha binary: `/usr/local/bin/mecha`; source/runtime tree: `/opt/mecha/current`; state and configuration: `/home/ubuntu/.mecha`.
- Mecha service: `/home/ubuntu/.config/systemd/user/mecha.service`, sourced from `deployment/jp2/mecha.service`, running under the existing `ubuntu` user manager.
- The Worker uses `ubuntu`'s rootless Docker daemon at `/run/user/1001/docker.sock`; ai-project Compose uses the separate system daemon. `loginctl enable-linger ubuntu` keeps the user services running after logout and across boot.

The backend and review runner share the same SQLite-backed storage bind mount. Docker host networking is intentional on Linux: it lets the runner reach host-local Mecha while every HTTP listener remains bound to loopback.

The default deployment requires no new Oracle Cloud Infrastructure security-list or network-security-group ingress rule, and no new host-firewall ingress rule. Tailscale Serve/Funnel terminates access through the native Tailscale service while the application remains on loopback. Reassess the firewall only if a future design binds Caddy or another service to a public interface, adds a non-Tailscale public listener, or troubleshooting proves that this Tailnet needs an explicit UDP path; document the exact protocol, port, and allowed source before opening it.

## First migration

1. Clone the pushed repository into `/opt/ai-project/current`.
2. Create `/etc/ai-project/ai-project.env` from `deployment/jp2/ai-project.env.example`, add real secrets, and set mode `0600`.
3. Copy production data while preserving the source:
   - required: `storage/database/database.db`
   - required for the reader: `storage/grammar/book-pages/`
   - user data: `storage/uploads/` and `storage/outputs/`
   - optional build inputs: `storage/grammar/import-packages/`
   - do not migrate `storage/grammar/source-cache/` unless a remote rebuild is planned
4. Install/configure host-local Mecha and the `grammar-mistake-explainer` worker before enabling the review runner.
5. Run `deployment/jp2/deploy.sh` and verify API health, grammar content, formal submissions, mistake book, TTS, and one AI explanation job.

Do not delete or overwrite the Mac copy during the initial migration. Keep it as the rollback source until jp2 has passed functional validation and a fresh backup exists.

## Mecha runtime

Mecha is a separate host service, not an ai-project Compose service. Build or install the Linux ARM64 binary from the Mecha revision that implements the deployed `POST /task` contract, then build `mecha-worker:latest` from the same revision and load it into the rootless Docker daemon. Register `workers/grammar-mistake-explainer.yml`, install `deployment/jp2/mecha.service` as an `ubuntu` user unit, and keep the API on `127.0.0.1:21212` with an API key in `/home/ubuntu/.mecha/config.yml`.

This deployment uses Mecha revision `8ceced7ff6ec3b5848d6a3a3aa4214c5032495eb` plus `deployment/jp2/mecha-rootless.patch`. Apply that patch to the revision before building the Linux ARM64 binary. The patch selects container UID `0:0` only when Docker reports a rootless daemon; there, container UID 0 maps to the `ubuntu` daemon owner, allowing the read-only bind mount of the `0600` Codex credential. On a rootful daemon, Mecha retains its existing host UID behavior. The deployed binary reports `8ceced7f-rootless1`.

The Worker image is built from the same Mecha revision. Import it into `ubuntu`'s rootless daemon (`DOCKER_HOST=unix:///run/user/1001/docker.sock`). After `mecha worker start grammar-mistake-explainer`, restart the Mecha user service so its in-memory registry sees the new Worker state. Mecha's SQLite database is backed up by `deployment/jp2/deploy.sh` before application releases.

The Worker requires `/home/ubuntu/.codex/auth.json` with owner `ubuntu` and mode `0600`. Treat it as a high-sensitivity credential: transfer it only with explicit authorization, never put it in Git or a shared temporary directory, and validate its use with a synthetic task before processing stored mistakes. Start and enable `mecha.service` only after the credential is present. `ai-review-runner` must remain stopped until Mecha health, Worker online state, schema validation, idempotency, and restart recovery are confirmed.

Use `scripts/smoke-mecha-worker.py` with `AI_PROJECT_ROOT=/app` inside the backend container to verify a synthetic task. It saves the raw Mecha result under `/srv/ai-project/storage/logs/` without sending stored answer data. Preserve failed attempts for diagnosis.

## Tailscale exposure policy

Deploy in two phases:

1. Private validation: `sudo tailscale serve --bg --https=8443 8080`. This is available only inside the Tailnet.
2. Public exposure: use Funnel only after authentication, request-size limits, and abuse/rate controls protect uploads and paid speech endpoints.

Use `deployment/jp2/tailscale-expose.sh` for repeatable status/private/public/off operations. The public mode deliberately requires `AI_PROJECT_PUBLIC_READY=yes` and a healthy local application. Planned bindings are private Serve on HTTPS 8443 and public Funnel on HTTPS 443, both targeting loopback port 8080.

Never expose Mecha port 21212. Exit-node advertisement, subnet routes, and Tailscale SSH are host administration features, not application requirements; enable them only with an explicit scope and policy review.

After final cutover, reset both Serve and Funnel on the Mac while leaving the Mac logged into Tailscale.

## Routine release

1. Review, test, commit, and push changes from the development machine.
2. On jp2, fetch and fast-forward `/opt/ai-project/current` to the intended commit.
3. Run `deployment/jp2/deploy.sh`. It creates a consistent SQLite backup, retains the latest 14 deploy backups, rebuilds images, replaces containers, and verifies health.
4. Verify `sudo docker compose -f deployment/jp2/compose.yaml ps`, `/api/health`, and the changed feature.
5. Check AI review separately when the change touches Mecha, prompts, schemas, or grading.

## Rollback

1. Check out the previous known-good Git commit in `/opt/ai-project/current`.
2. Restore a selected database backup from `/var/backups/ai-project` only if the release changed stored data incompatibly.
3. Re-run `deployment/jp2/deploy.sh`.
4. Verify health before changing Tailscale exposure.

Database rollback can discard newer submissions. Preserve the current database under a new timestamped filename before restoring an older copy.
