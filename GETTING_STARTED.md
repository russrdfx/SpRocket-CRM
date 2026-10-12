# Start your company's SpRocket workspace

SpRocket CRM Web **v0.2.0-beta.1** is a free, open-source public beta. Each company runs its own installation and database. Hosting may cost money. There is no shared public signup service, and you do not need a SpRocket domain.

## Choose your hosting

| Option | Best for | What to expect |
| --- | --- | --- |
| Render Free trial | Trying the app before choosing hosting | HTTPS address included; app sleeps when idle; manual sync; database expires after 30 days. |
| Your own Docker server | A lasting private installation | Your domain, persistent database and automatic background checks. An administrator manages server costs, updates and backups. |
| Durable managed hosting | Teams that prefer a hosting provider | An always-on Docker app and persistent PostgreSQL database, with a backup/recovery plan. Review the provider's current prices before upgrading. |

[![Deploy trial to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Frussrdfx%2FSpRocket-CRM)

**The button creates a trial in your own Render account.** Review the proposed app and database before approving. Both must show Free. The template is a temporary test, not permanent free company hosting. See [Render's free-tier limits](https://render.com/docs/free). If your Render workspace already has a Free PostgreSQL database, use a separate eligible workspace or choose another hosting option; do not overwrite an existing installation.

For the lasting Docker option, follow [the installation commands in WEB.md](WEB.md#first-installation). For managed hosting, use the architecture in WEB.md: one Docker application process, persistent PostgreSQL, a stable encryption key, HTTPS and backups. You can keep Render after a trial by choosing suitable paid app/database plans; the free-trial button does not buy or upgrade anything.

## 1. Deploy the trial

1. Click **Deploy to Render**, then create or sign in to your own Render account.
2. Review the resources. Choose a suitable region and unique app/database names. Keep the database reference in the app's `DATABASE_URL` aligned if you edit names in the Blueprint. The default region is Oregon, USA.
3. Approve the trial deployment. Wait until the app shows **Live**.
4. Open the app's HTTPS address. A new, empty installation opens **Set up your workspace** automatically. The same page is available at `/setup`.
5. In Render, open the app's **Environment** page and privately copy the generated `SPROCKET_SETUP_TOKEN`. This is your setup code; it is different from the Google client secret and your password.

The default resource names contain `test` to make the temporary trial clear. Only one Free PostgreSQL database is allowed per Render workspace. Deployment updates are manual: upstream code pushes do not automatically change your running installation.

## 2. Create the first administrator

1. Enter the setup code, your company/workspace name, your email and your display name.
2. Choose a password of 12–128 characters and create your administrator account.
3. Sign in with that email and password.
4. Keep your deployment secrets private and preserved for recovery. The setup code stops working after the first administrator exists.

This initial password is needed to establish the administrator before Google has been configured. You can link Google next and use it for future sign-ins. No default administrator or shared password is included.

## 3. Set up your CRM

1. Open **Configuration → Account Defaults** to set your workspace name, currency, owner names and default phone country.
2. Open **Configuration → Pipelines** to create a Deals pipeline and its stages.
3. Use **Properties** for custom fields and **Import & Export** for reviewed CSV imports.
4. Create a test contact, company and deal. Check that associations and ownership are correct before importing company data.

## 4. Configure Google once for your company (optional)

You can use CRM records without a Google connection. Gmail, Calendar and Google sign-in require your organization's Google Cloud client; this setup is still an administrator task.

1. Create or select your own Google Cloud project. Create an OAuth **Web application** client and configure its audience/consent for intended users. For a testing audience, add the intended test users as Google requires.
2. Enable **Gmail API** and **Google Calendar API** if you want those integrations. API access is separate from basic Google sign-in.
3. In SpRocket, open **Configuration → Integrations**. Copy the three exact callback addresses shown there into that client's **Authorized redirect URIs**. They end in:
   - `/mail/callback/google`
   - `/calendar/callback/google`
   - `/auth/google/callback`
4. Save that client's ID and secret in SpRocket. The secret is encrypted in your company's database and never returned by its API. Do not share it through an issue, screenshot or email.
5. While signed in with your workspace password, open **Configuration → Security → Link Google account**. Choose the Google email matching your workspace account.
6. Sign out, then test **Sign in with Google**. Your existing records, ownership and connected accounts stay associated with the same workspace user.
7. Connect Gmail from **Inbox** and Calendar from **Configuration → Calendar**. Start with a small date range and review the result.

Basic sign-in requests name/email identity only. Gmail/Calendar permissions are separate. Mail sync automatically creates missing contacts and business-domain companies and logs messages on associated records, making those activities visible to admitted workspace members. Calendar sync does not create contacts; you choose which meetings to log. Review Google's consent/verification requirements before wider use; a testing client is not a shortcut around them. See [Google's OpenID Connect guide](https://developers.google.com/identity/openid-connect/openid-connect), [EMAIL.md](EMAIL.md) and [CALENDAR.md](CALENDAR.md).

## 5. Invite your team

1. Open **Configuration → Users & Teams**.
2. Enter a colleague's email and choose Member or Administrator.
3. Create an invitation and share the private link directly with that colleague. SpRocket does not email it automatically.
4. They can accept using their matching Google account without a new password, or create a password account. Invitations expire after 24 hours and can be used once.

Uninvited Google users cannot enter. Another company's administrator must deploy a separate installation; they cannot create another company inside yours.

## 6. Keep the installation running

Before the trial's database expiry, choose durable hosting or export/migrate your data. Free Render PostgreSQL has no managed backups. Follow [RENDER.md](RENDER.md#backups-and-expiry) for Render backup guidance or [WEB.md](WEB.md#backups-restoration-and-updates) for Docker backups and recovery. CSV exports are useful for records, but are not a full account/activity/configuration backup.

Preserve the encryption key (`SPROCKET_TOKEN_SECRET` on Render, or `MAIL_TOKEN_KEY` with Docker), keep the database private, and test recovery. Download new releases from [GitHub Releases](https://github.com/russrdfx/SpRocket-CRM/releases); back up before manually deploying an update. Never delete database volumes as an update step. See [web beta release notes](WEB_RELEASE.md) for current limitations.

## If setup gets stuck

- **I see Sign in instead of setup:** the database already has an administrator. Use that account or ask your administrator for an invitation. A new company needs its own deployment/database.
- **The setup code seems blank:** use Copy on the `SPROCKET_SETUP_TOKEN` value in Render's Environment page; do not copy the variable name or a masked display.
- **Google says redirect URI mismatch:** copy the full exact HTTPS callback from Integrations, including hostname, port if any and path. Recheck after changing your domain.
- **Calendar access fails:** check that Calendar API is enabled, audience permissions are correct and Calendar was connected separately.
- **No deal stages are available:** create a pipeline and stages under Configuration → Pipelines.
- **The free app takes time to open:** Render's free app sleeps after idle periods. An always-on plan removes that limitation.
- **I lost my password:** try your already-linked Google account. Self-service password recovery is not yet implemented; preserve administrator access and a recovery plan.

Report reproducible problems through [GitHub Issues](https://github.com/russrdfx/SpRocket-CRM/issues). Include the release, hosting type, steps and a redacted screenshot; omit credentials, invitation links, customer records and private messages.
