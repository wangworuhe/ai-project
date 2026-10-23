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
`deployment/jp2/public.compose.yaml` gateway serves HTTPS. Authentication now
uses the application's `/login` page, replacing the browser Basic Auth dialog.
One personal account shares the existing practice data; registration and
password recovery are not enabled.

Set `AI_PROJECT_AUTH_ENABLED=yes`, `AI_PROJECT_AUTH_USERNAME`, and
`AI_PROJECT_AUTH_PASSWORD_HASH` (Werkzeug format) in
`/etc/ai-project/ai-project.env` (root-owned, mode `0600`). Never commit real
credentials. Public mode defaults authentication on and fails startup if
credentials are missing. Explicitly disabling auth is only for local development;
the public deploy script requires it enabled. Existing private password files
remain the owner's credential reference; `/etc/ai-project/public.env` holds
legacy Basic credentials for rollback only.

Successful login creates an opaque session cookie with Secure, HttpOnly,
SameSite=Lax and a fixed lifetime of **60 days**. Only its SHA-256 digest and a
CSRF token are stored in persistent `storage/database/auth.db` (mode `0600`).
Sessions survive application restarts. Logout revokes the current session;
changing the configured password hash invalidates all old sessions. Every API,
media file and book-page route requires authentication except health and auth
bootstrap/login. Health exposes only `status: ok` for container checks. The SPA
shell and static bundles are public; protected data is fetched only after login.
Mutating authenticated requests require a session CSRF token; login requires
JSON and a custom header. Auth responses and API data use `Cache-Control:
no-store`. Ten login attempts per 15 minutes are allowed across the personal
account (process-local, reset by restart).

The gateway rejects foreign browser origins and limits bodies to 16 MB.
Enable `AI_PROJECT_PUBLIC_ACCESS=yes` in the application environment. The backend
also enforces origin checks, 600 API requests per minute, speech/AI budgets of
10 requests per minute and 120 per hour, at most two concurrent speech/AI
requests, and a 10000-character text bound. These per-process budgets reset on
restart and are not a billing cap. `AI_PROJECT_ALLOWED_ORIGINS` lists both public
and Tailscale HTTPS origins. Deterministic grading is unchanged.

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
The deploy script backs up the application, Mecha and existing auth SQLite
databases before replacing containers. It verifies private health and a protected
session endpoint before recreating the public gateway without Basic Auth.
After the precise firewall ingress is in place, verify a valid public TLS
certificate, anonymous login-page HTTP 200 and protected API HTTP 401,
authenticated API HTTP 200, rejected
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

## Public cutover acceptance (2026-10-22)

- Application release: `a32fcadab01b3d8f12a68dc39040be2ebce8ed39`, committed and pushed before deployment. The deployment used `deployment/jp2/deploy.sh --public`.
- Public URL: `https://ai.yalacore.com`; public DNS A record `161.33.165.41`, no AAAA record at acceptance. A personal username/password is required for both the frontend and APIs.
- Certificate: Let's Encrypt YE1, subject `ai.yalacore.com`, valid through `2027-01-21 02:15:18 UTC`. Normal certificate verification succeeded from the Mac's public proxy egress and independently from rn, without using Tailscale.
- Acceptance: anonymous/incorrect credentials HTTP 401, authenticated frontend/health/grammar library HTTP 200, foreign-origin requests HTTP 403, excessive speech text HTTP 413, and speech/AI request budget HTTP 429. Rate-limit probes used a nonexistent route in the protected speech namespace; no real paid request was submitted by the acceptance checks.
- Validation: 22 local backend tests passed, frontend lint/build passed with informational bundle-size warnings, and `git diff --check` passed. The six request-guard tests were also rerun successfully inside the deployed backend image.
- Initial certificate validation failed before the host's TCP 443 rule was enabled. After the port was enabled, certificate issuance and public HTTPS acceptance succeeded. No certificate-validation bypass was used.
- Host firewall: one new IPv4 TCP 443 rule, source `0.0.0.0/0`, comment `ai-project-public-https`; persisted by adding only that rule before INPUT REJECT in `/etc/iptables/rules.v4`. Existing live Docker/Tailscale chains were not flushed or reloaded. OCI rules did not need to be changed during this release; public ingress was verified end to end.
- Backups: application SQLite `/var/backups/ai-project/database-20261023-030813.db`; Mecha SQLite `/var/backups/ai-project/mecha/database-20261023-030813.db`; prior application environment `/etc/ai-project/ai-project.env.bak.public-20261023T030809Z`; persistent firewall `/var/backups/ai-project/rules.v4.before-public-20261023`; live firewall snapshot `/var/backups/ai-project/iptables-runtime.before-public-20261023`. Backup filename timestamps are UTC.
- Existing Tailscale HTTPS 8443 still returned HTTP 200 with valid TLS from jpv3. The original Mecha Worker remained healthy. Backend 5000, private web 8080, and Mecha 21212 retained loopback listeners. No Mac production LaunchAgent was enabled.
- The loopback-only staging gateway was stopped after acceptance. The Mac's earlier Tailscale DNS interface-binding issue was not changed by this public-domain deployment.

## Login-page acceptance (2026-10-23)

- Application release `d22805d` replaces gateway Basic Auth with `/login` and persistent, revocable application sessions. The existing personal username/password was reused without exposing plaintext in logs or Git. Master was clean and pushed before `deployment/jp2/deploy.sh --public`.
- Sessions have a fixed 60-day expiry (`Max-Age=5184000`), Secure/HttpOnly/SameSite=Lax cookies, and server-side expiry. Logout invalidates the current token even if its previous cookie is replayed. Password-hash rotation invalidates existing sessions.
- Local validation: 28 backend tests, frontend lint/build and whitespace checks passed. Existing bundle-size warnings remain informational. Desktop 1440 px and mobile 390 px previews had no horizontal overflow or browser script errors.
- Public browser acceptance used normal TLS verification through the Mac's explicit HTTP proxy: initial page HTTP 200 with no Basic challenge, redirect to login, incorrect-password message, successful login with the existing password, grammar library HTTP 200, retained login after reload and in a second browser context, and a verified 60-day cookie/expiry. Logout returned to `/login`, and the copied old cookie then returned HTTP 401. No browser script errors occurred.
- Anonymous grammar, media and book-page API requests returned HTTP 401. Missing CSRF returned HTTP 403; a valid CSRF token reached a nonexistent speech route (HTTP 404). Foreign Origin returned HTTP 403. No real paid speech/AI request was invoked.
- Twelve auth/request-guard tests passed inside the production image. Private Tailscale health remained HTTP 200, Mecha health and its original Worker remained healthy, and ports 5000/8080/21212 remained loopback-only. Session storage is `/srv/ai-project/storage/database/auth.db`, mode `0600`; deployment backs it up on subsequent releases. No host ingress rule or Mac LaunchAgent changed.
- Release backups: application SQLite `/var/backups/ai-project/database-20261023-045058.db`, Mecha SQLite `/var/backups/ai-project/mecha/database-20261023-045058.db`, previous private environment `/etc/ai-project/ai-project.env.bak.login-20261023T045047Z`. Existing runtime/practice data was preserved.
- Rollback: keep the private environment backup and legacy `/etc/ai-project/public.env`. Restore the previous application/Caddy revision and its environment together using the routine release procedure; retain current storage and make fresh backups first. Never disable application auth while the current public gateway is running without Basic Auth.
