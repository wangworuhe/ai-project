# jpv3 production deployment

This document is the source of truth for deploying ai-project to jpv3. Host-wide VPS facts remain in the external `vps` skill; application releases, paths, data, and rollback procedures stay here.

The host's current shorthand and SSH alias are `jpv3` (formerly `jp2`); connect with `ssh jpv3`. The existing `deployment/jp2/` directory and `docs/jp2-deployment.md` filename are intentionally retained.

## Architecture and paths

- Host: SSH alias `jpv3`, Ubuntu ARM64.
- Tailscale: native host service, node `yala-jp`, MagicDNS `yala-jp.tailaafe48.ts.net`.
- Tailscale SSH: enabled for Tailnet administration; public-key SSH through alias `jpv3` remains available as a fallback.
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

Do not delete or overwrite the Mac copy during the initial migration. Keep it as the rollback source until jpv3 has passed functional validation and a fresh backup exists.

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

## Cutover record (2026-10-01)

- jpv3 is running ai-project, the AI review runner, Mecha, and its rootless Docker Worker. A synthetic explanation completed with schema, answer-slot, deterministic-grading boundary, and deduplication checks; the Worker remained usable after a Mecha restart. The runner is configured and idle with no queued jobs at the time of validation.
- Azure Speech generated a short MP3 through the jpv3 API; its media URL returned HTTP 200 through jpv3's Tailnet-only Serve. The app health endpoint also returned HTTP 200 through `https://yala-jp.tailaafe48.ts.net:8443/` when the Mac bypassed its general-purpose HTTP proxy for the Tailnet domain.
- The Mac's previous Tailscale Serve on HTTPS 8443 and Funnel on HTTPS 443 were reset. `tailscale serve status --json` returned `{}` while the Mac stayed online in the Tailnet. jpv3 Funnel remains off, so the migrated app is accessible only to Tailnet members.
- The deployed ai-project commit is `2770afc`. It was transferred by verified Git bundles from the local checkout; these new commits have not yet been pushed to the Git remote. No Oracle external firewall rule was added.

## Mac development checkout (2026-10-02)

The Mac retains the repository, virtual environment, `.env`, and `storage/` for development and rollback. Production requests and automatic explanation jobs run on jpv3. The three Mac LaunchAgents `com.yala.ai-project.backend`, `com.yala.ai-project.caddy`, and `com.yala.ai-project.grammar-ai-review` were stopped and persistently disabled with `launchctl`; their plist files remain under `~/Library/LaunchAgents` for reversible local testing. Do not re-enable them during a jpv3 release. The local port 8080 no longer responds; jpv3's Tailnet health endpoint remains healthy.

The Mac remains logged into Tailscale but has no Serve or Funnel configuration. Local `im.mecha.serve` and `im.mecha.mcp` are owned by the separate `mecha.im` project and were left untouched; stopping the ai-project runner prevents the Mac from submitting new grammar explanation jobs.

## Routine release

### Personal public domain: ai.yalacore.com

The public domain A record targets jpv3 (`161.33.165.41`). The optional
`deployment/jp2/public.compose.yaml` gateway serves HTTPS with HTTP Basic
authentication for one owner; it does not add user accounts or isolate the
existing shared practice data. Its credentials are in
`/etc/ai-project/public.env` (root-owned, `0600`), with `PUBLIC_USERNAME` and a
bcrypt `PUBLIC_PASSWORD_HASH`. Quote the hash in that env file so Compose does
not interpolate dollar signs. Never commit this file or its plaintext password.

The gateway forwards authenticated requests to `127.0.0.1:8080`, strips the
Authorization header, rejects foreign browser origins, and limits bodies to
16 MB. Enable `AI_PROJECT_PUBLIC_ACCESS=yes` in the existing application env
file before release. The backend then enforces origin checks, 600 API requests
per minute, speech/AI budgets of 10 requests per minute and 120 per hour, at
most two concurrent speech/AI requests, and a 10000-character text bound.
These are per-process budgets for the single Waitress process, reset by a
restart; they are not a billing cap. `AI_PROJECT_ALLOWED_ORIGINS` lists the
public origin and existing Tailscale HTTPS origin. Deterministic grading is
unchanged.

Network scope: the gateway binds `0.0.0.0:443`, **TCP HTTPS only**, with allowed
source `0.0.0.0/0` for browser access and ACME TLS-ALPN validation. Host INPUT
and OCI security-list/NSG ingress must permit that exact traffic. No new public
TCP 80, UDP 443, application backend, database, or Mecha listener is needed.
HTTP certificate validation and automatic HTTP redirects are disabled; users
must visit `https://ai.yalacore.com`. Certificates persist under
`/srv/ai-project/caddy-public/`. Existing Tailscale Serve HTTPS 8443 remains.

Before release, verify the gateway configuration and authenticated/unauthenticated
HTTP behavior over a loopback-only staging listener. Run required repository
checks, commit and push master, then use `deployment/jp2/deploy.sh --public`.
The deploy script backs up both SQLite databases before replacing containers.
After the precise firewall ingress is in place, verify a valid public TLS
certificate, anonymous HTTP 401, authenticated frontend/API HTTP 200, rejected
cross-site requests, and HTTP 429 without invoking real paid services. A
successful private health check alone is not public acceptance.

To roll back the public entry only, run
`sudo docker compose -f deployment/jp2/public.compose.yaml down` and remove the
specific TCP 443 ingress rule. Retain certificate storage, application runtime
storage, secrets, and Tailscale Serve. Application rollback follows the steps
below; preserve a fresh database backup before any data restore.

### Application release

1. Review, test, commit, and push changes from the development machine.
2. On jpv3, fetch and fast-forward `/opt/ai-project/current` to the intended commit.
3. Run `deployment/jp2/deploy.sh`. It creates a consistent SQLite backup, retains the latest 14 deploy backups, rebuilds images, replaces containers, and verifies health.
4. Verify `sudo docker compose -f deployment/jp2/compose.yaml ps`, `/api/health`, and the changed feature.
5. Check AI review separately when the change touches Mecha, prompts, schemas, or grading.

## Rollback

1. Check out the previous known-good Git commit in `/opt/ai-project/current`.
2. Restore a selected database backup from `/var/backups/ai-project` only if the release changed stored data incompatibly.
3. Re-run `deployment/jp2/deploy.sh`.
4. Verify health before changing Tailscale exposure.

Database rollback can discard newer submissions. Preserve the current database under a new timestamped filename before restoring an older copy.
