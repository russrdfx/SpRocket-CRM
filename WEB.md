# Private web deployment beta

New administrator? Start with [the getting-started guide](GETTING_STARTED.md).

SpRocket's web edition runs one shared workspace per organization on its own HTTPS domain. The existing desktop edition keeps its SQLite storage and local behavior. The web edition uses PostgreSQL and workspace accounts; it does not expose the desktop development server.

## Hosting

Use a Linux server or a container host that supports Docker Compose and persistent volumes. A registrar's DNS record points your CRM hostname, for example `crm.company.com`, to that server. Docker Compose starts PostgreSQL, the production Gunicorn application server and Caddy. Caddy obtains and renews HTTPS certificates. Only ports 80 and 443 are published; the database and application use the private deployment network.

Vercel is not the initial deployment target: the current web package uses a continuously running process for provider connection state and background checks. A Vercel adaptation would need external durable services for those responsibilities. A static interface preview is possible there, but it would not be the full deployment described here.

This is a first web preview, not a claim of production readiness. Complete a real HTTPS hosting test, recovery drill and independent security review before exposing real customer data. Docker/container testing must be done on a host with Docker installed; local verification uses Gunicorn and a separate PostgreSQL database.

## First installation

1. Install Docker Engine with the Compose plugin on your server. Point your hostname's DNS A/AAAA records at that server and allow inbound ports 80 and 443. Remove any stale AAAA record pointing elsewhere.
2. Download or clone SpRocket and open its directory.
3. Generate private settings:
   ```sh
   python3 deploy/configure.py --domain crm.company.com
   ```
   This creates `deploy/.env` with a database password, first-run setup code and provider-token encryption key. It refuses to overwrite an existing file. Keep this file private and preserve it during updates and recovery.
4. Start the deployment:
   ```sh
   docker compose --env-file deploy/.env up -d --build
   ```
5. Open `https://crm.company.com/setup`. Enter the setup code from the file, workspace name, administrator email, display name and a password of 12–128 characters. Setup can create only the first administrator. Sign in afterward.
6. Configure pipelines and stages in Configuration. In **Users & Teams**, create invitations and share the private links directly with intended colleagues. No invitation email is sent automatically. Invitations expire after 24 hours and can be used once.

Administrators manage workspace configuration, invitations, rules and hosting backups. Members can create/edit shared CRM records and connect their own mail/calendar accounts. Personal mailbox caches, calendar caches and saved views are scoped to the signed-in account. Logging an email or meeting shares it with the workspace's CRM records. This edition is not a public registration or multi-tenant service.

## Google setup (administrator only)

The organization registers its own Google web OAuth application once. In the same Google Cloud project, enable Gmail API and Google Calendar API. Configure consent and intended users/scopes appropriate to your organization. Follow Google's production and verification requirements; installing SpRocket does not exempt Gmail restricted scopes from those requirements.

In SpRocket, open **Configuration → Integrations** and save the Google client ID and secret. The secret is encrypted in PostgreSQL and is never returned by the API. You can alternatively set `GOOGLE_MAIL_CLIENT_ID` and `GOOGLE_MAIL_CLIENT_SECRET` in `deploy/.env`. Register all three exact callbacks:

- `https://crm.company.com/mail/callback/google`
- `https://crm.company.com/calendar/callback/google`
- `https://crm.company.com/auth/google/callback`

Configuration saved through the app takes effect immediately. If you configure credentials through environment values, recreate the application:
```sh
docker compose --env-file deploy/.env up -d --force-recreate app
```
Users then click Connect and complete Google consent themselves. Keep the encryption key stable; replacing it makes stored provider tokens unreadable. Microsoft email can use the existing provider environment settings when explicitly added to the application container; they are not included in the default Compose template.

## Background work

The host checks opted-in automatic email imports and enabled inactivity task rules roughly once a minute, even without an open browser. Email auto-sync still requires the user's selected initial import and explicit enablement. Provider errors remain on account status rather than logging private payloads. Calendar date-range sync starts explicitly. Users can enable **Automatically refresh this date window** to refresh that selected window every ten minutes with browsers closed. Changing dates and syncing saves the refreshed window. Operating-system notifications are not part of this web preview. Browser reminders are available when users open the app.

Run one Gunicorn process with multiple threads. Current OAuth pending requests and import continuations remain process-local: a restart may require reconnecting or restarting a pending import. Login sessions are stored in PostgreSQL and survive application restarts. Multiple application replicas require shared provider continuation/job coordination first.

## Backups, restoration and updates

Run `sh deploy/backup.sh` from the project directory. It writes a private PostgreSQL custom-format archive under `backups/`. Set a host schedule for this command and copy backups to storage outside the server. Preserve `deploy/.env` separately: encrypted provider tokens and saved Google client configuration require the original key. Saved Google configuration takes precedence over environment credentials on restart.

To restore a **trusted backup produced by this deployment**:
```sh
sh deploy/restore.sh backups/SpRocket-web-TIMESTAMP.dump RESTORE
```
The command stops the application, makes a safety backup, restores transactionally, and starts the application only after successful restoration. Treat archives as executable database input; never restore an untrusted file. Test restoration on a separate database first. SQLite browser backup/restore is specific to the desktop edition; the web Configuration screen directs administrators to PostgreSQL recovery.

Before an update, make a backup and preserve `.env`. Then download the new source and run:
```sh
docker compose --env-file deploy/.env up -d --build
```
Initialization adds missing tables and existing form fields. Future destructive schema changes need explicit versioned migrations. Never remove the persistent volumes to update the app.

## Desktop data migration

On a trusted workstation, install `requirements-web.txt`, back up the desktop database, and set `DATABASE_URL` to the destination PostgreSQL database. Initialize the web deployment first. The destination must have no CRM records.

```sh
python3 deploy/migrate_desktop.py /path/to/desktop-backup.db
python3 deploy/migrate_desktop.py /path/to/desktop-backup.db --apply
```
The first command validates and previews counts without committing. The second copies workspace settings, record IDs/relationships and activity history in one transaction. It does not copy desktop passwords, profiles, provider credentials/tokens, cached inbox/calendar messages or local sessions. Web users connect their own providers after migration. Original desktop files are read-only and are never modified.

## Validation and preview limits

Run the established desktop tests with `python3 -m unittest discover -q`; PostgreSQL tests are skipped unless `SPROCKET_TEST_DATABASE_URL` names a **disposable, separate** PostgreSQL database. These tests truncate fixture tables. Run:
```sh
SPROCKET_TEST_DATABASE_URL=postgresql://USER@localhost/DISPOSABLE_DB python3 -m unittest test_web_deployment -v
```

The first web preview includes password sign-in, one-time bootstrap, invitations, administrator/member boundaries and persistent sessions. Password reset and user deactivation/role changes remain future work. Google OIDC sign-in is available for linked users and invited members. Google credential entry is available in Configuration; Google Cloud registration remains an administrator task. Test deployment, backups and Google callbacks on your actual HTTPS domain before treating this as a production installation.

Local verification completed: 14 PostgreSQL integration tests covering bootstrap/login/invitations, member boundaries, migration, background owner isolation, opt-in Calendar refresh and encrypted Google configuration. A native PostgreSQL dump/restore into a separate database preserved test accounts and sessions. Browser checks verified administrator setup, sign-in and invitations. The existing 103 desktop backend tests and both presentation suites pass. The Render Docker/HTTPS pilot and real Gmail/Calendar connections have been verified. Docker Compose/Caddy still needs separate hosting verification. Google sign-in admission, token verification, browser binding and replay tests pass; live Google sign-in consent and explicit account linking have also been verified on the hosted pilot.

For a temporary free hosted pilot, see [Render deployment](RENDER.md). That template disables background jobs because free web services sleep.

## Google sign-in

Google sign-in is separate from Gmail and Calendar access and requests only `openid email profile`. Configure the existing Google client and register `/auth/google/callback` at your exact HTTPS origin.

Existing users first sign in with their workspace password and open **Configuration → Security → Link Google account**. Choose the Google email matching their workspace account. This explicit linking preserves the user ID, role, record ownership and private mail/calendar caches. Subsequent logins use the Google subject ID rather than email-based automatic linking. The password continues to work.

New invited users can select **Accept invitation with Google** on their invitation page. The verified Google email must match an unexpired invitation; their assigned role is preserved and no password is created. Uninvited Google accounts cannot enter. First administrator bootstrap still requires the setup code and a password; link Google afterward.

Sign-in uses an authorization code with PKCE, a browser-bound state cookie and nonce, RS256 ID-token verification (issuer, audience, expiry and authorized party), encrypted single-use pending attempts in PostgreSQL and existing eight-hour opaque sessions. Google sign-in tokens are discarded after verification. Existing mailbox/calendar connections continue under the same workspace user ID.
