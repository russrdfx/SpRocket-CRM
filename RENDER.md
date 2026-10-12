# Render free pilot

This Blueprint is for a short, fictional-data test. It requests a Free Docker web service and a Free PostgreSQL database in Oregon, USA. Render provides an HTTPS `onrender.com` address. Choose a suitable region before deploying if data residency matters.

Free web services sleep after 15 minutes without inbound traffic, and local files are lost on sleep/restart/redeploy. Free PostgreSQL expires after 30 days; Render later deletes it unless upgraded. This is not an ongoing free production installation. Background jobs are disabled in the pilot; use explicit email/calendar sync. Do not create artificial traffic to bypass the free service's sleep policy. See [Render's free-tier limits](https://render.com/docs/free).

## Deploy

1. Create/sign in to your Render account. Use the Free/Hobby workspace option and review any terms yourself. No paid workspace upgrade is needed for this pilot.
2. Create a **Blueprint** from the SpRocket-CRM GitHub repository, using `render.yaml`. Connect only the repository access required for this deployment. Review the two resources before applying: both must say **Free**.
3. Render builds `deploy/Dockerfile`, starts Gunicorn on its provided `PORT`, and connects PostgreSQL over Render's private network. Its generated external URL becomes SpRocket's canonical origin. Login remains required; desktop/demo entry points are disabled.
4. Wait for the service to be healthy. In its Environment section, copy the generated `SPROCKET_SETUP_TOKEN` privately. Open the service URL followed by `/setup`, enter that code, and create your administrator account. Do not post the code or encryption key in chat, screenshots or GitHub.
5. In Configuration → Integrations, configure your Google client. Register the exact mail/calendar/sign-in callback addresses displayed there on the existing Google OAuth client, keeping the desktop callbacks if still needed. Use a separate OAuth client for a lasting production installation.
6. Test fictional records, invitations, filtering, import/export and Google connections. Use a narrow import window if you choose to connect a real account. Logging mail/meetings shares those activities with admitted workspace members.

Google configuration is encrypted in PostgreSQL, so it survives app sleep/restarts. Preserve the generated `SPROCKET_TOKEN_SECRET`: the app derives its encryption key from this secret, and changing it makes saved provider tokens and Google configuration unreadable. The setup code works only before the first administrator exists. No demo user or sample password is bundled in the deployment.

## Custom domain

After the pilot works, add your domain in Render's service settings. Update `SPROCKET_ORIGIN` to the exact HTTPS origin, redeploy, and update Google callbacks to match. The app accepts only its canonical hostname; use that address for sign-in. Render's health endpoint is public and contains only readiness status, allowing infrastructure health probes without weakening CRM authentication.

## Backups and expiry

The Compose backup scripts in WEB.md target self-hosted Docker Compose and do not operate on Render's managed database. Render Free Postgres has no managed backups. Before the 30-day expiry, use `pg_dump --format=custom` with a securely supplied database connection, or migrate to a durable hosting/database plan. The Blueprint blocks public database connections; a trusted backup workstation may need a temporary, narrow IP allowlist entered by the administrator. Never open the database to all IPs for convenience.

Check usage/billing settings before testing. This template chooses Free resources, but bandwidth/build allowances and platform limits still apply; it is not a promise that unrelated Render activity cannot incur charges. Review [Render's pricing](https://render.com/pricing) before any upgrade.

The hosted profile identifies password-based workspace sign-in separately from desktop OIDC SSO. The first registered user is the account administrator.

Google sign-in is available after registering `https://YOUR-SERVICE.onrender.com/auth/google/callback`. Existing users link their matching Google account from Configuration → Security while signed in; invited members can join through Google without a new password. The login page then offers Sign in with Google. Gmail and Calendar permissions remain separate.
