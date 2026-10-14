# Start your company's SpRocket workspace

SpRocket CRM Web **v0.2.0-beta.5** is a free, open-source public beta. Each company runs its own installation and database. Hosting may cost money. There is no shared public signup service, and you do not need a SpRocket domain.

## Choose your hosting

| Option | Best for | What to expect |
| --- | --- | --- |
| Render Free trial | Trying the app before choosing hosting | HTTPS address included; app sleeps when idle; manual sync; database expires after 30 days. |
| Existing AWS account | Companies already using AWS | Run the Docker package on an EC2 Linux server; use bundled PostgreSQL or an IT-configured RDS PostgreSQL database. See [existing-cloud options](#already-use-aws-azure-or-another-provider). |
| Existing Azure subscription | Companies already using Azure | Run the Docker package on a Linux virtual machine; use bundled PostgreSQL or an IT-configured Azure Database for PostgreSQL. See [existing-cloud options](#already-use-aws-azure-or-another-provider). |
| Your own Docker server | A lasting private installation | Your domain, persistent database and automatic background checks. An administrator manages server costs, updates and backups. |
| Durable managed hosting | Teams that prefer a hosting provider | An always-on Docker app and persistent PostgreSQL database, with a backup/recovery plan. Review the provider's current prices before upgrading. |

[![Deploy trial to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Frussrdfx%2FSpRocket-CRM)

**The button creates a trial in your own Render account.** Review the proposed app and database before approving. Both must show Free. The template is a temporary test, not permanent free company hosting. See [Render's free-tier limits](https://render.com/docs/free). If your Render workspace already has a Free PostgreSQL database, use a separate eligible workspace or choose another hosting option; do not overwrite an existing installation.

For the lasting Docker option, follow [the installation commands in WEB.md](WEB.md#first-installation). For managed hosting, use the architecture in WEB.md: one Docker application process, persistent PostgreSQL, a stable encryption key, HTTPS and backups. You can keep Render after a trial by choosing suitable paid app/database plans; the free-trial button does not buy or upgrade anything.

## Already use AWS, Azure or another provider?

You can host SpRocket in your company's existing cloud account or on a company-managed server. **Render is optional.** Your team can keep its usual domain, billing, infrastructure management and backup arrangements.

| Existing service | Starting approach | Database choices |
| --- | --- | --- |
| AWS | EC2 Linux virtual machine with Docker Compose | PostgreSQL included in the Compose package, or Amazon RDS for PostgreSQL configured by IT. |
| Azure | Linux virtual machine with Docker Compose | PostgreSQL included in the Compose package, or Azure Database for PostgreSQL configured by IT. |
| Another cloud provider or company server | Always-on Linux server with Docker Compose and persistent storage | Bundled PostgreSQL, or a compatible PostgreSQL service configured by IT. |

**The simplest path with the current package:** ask your IT administrator to provide a suitable Linux server, point a hostname such as `crm.company.com` to it, and follow [WEB.md → First installation](WEB.md#first-installation). That package runs the app, PostgreSQL and HTTPS proxy together. Your administrator manages persistent storage, backups and upgrades.

**If your company prefers a managed database:** the application can use a PostgreSQL connection through `DATABASE_URL`, but the supplied Compose file is wired to its bundled database. RDS or Azure PostgreSQL requires a reviewed configuration change, private connectivity, the provider's TLS settings and a host-specific backup/update procedure. It is not a one-click option in the supplied template. See [the administrator notes](WEB.md#existing-cloud-accounts-and-company-servers).

Provider references: [AWS EC2 with RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/CHAP_GettingStarted.CreatingConnecting.PostgreSQL.html) and [Azure Linux/PostgreSQL guidance](https://learn.microsoft.com/en-us/training/paths/migrate-linux-postgres-azure/). These describe provider infrastructure; they are not SpRocket-specific deployment templates.

The Docker deployment approach is portable, but AWS- and Azure-specific installations have not yet been verified for this project. Test sign-in, records, Gmail/Calendar connections and backup recovery before rolling out to the team. The Render price chart below applies only to Render; costs in an existing cloud account depend on its services, storage, network charges and contract. Existing subscriptions do not necessarily include additional app/database hosting at no cost.

## What will hosting cost?

SpRocket has **no software subscription or per-user licence fee**. Your company pays its hosting provider for the app and database. The figures below are **US dollars per month for one company installation**, not per CRM user. Prices checked **October 13, 2026**.

### Example Render budgets

These examples keep the **Hobby workspace at $0/month**. The app's compute plan and PostgreSQL plan are selected and billed separately.

| Setup | App hosting | Database compute | Approximate monthly budget | What to expect |
| --- | ---: | ---: | ---: | --- |
| Temporary trial | Free | Free | $0 within included usage | App sleeps; database expires after 30 days. |
| Paid database only | Free | $6 · 256 MB RAM | $6–8 | Database trial limit removed; app still sleeps. |
| Always-on starting point | $7 · 512 MB RAM | $6 · 256 MB RAM | **$13–15** | Low-cost starting point for light usage. |
| More database memory | $7 · 512 MB RAM | $19 · 1 GB RAM | **$26–28** | More room for database work as records and synced mail grow. |
| More app and database memory | $25 · 2 GB RAM | $19 · 1 GB RAM | **$44–46** | More room for imports, concurrent requests and a larger workspace. |

Paid totals are rounded planning estimates with a small database-storage allowance, not fixed-price bundles. Render lists expandable PostgreSQL storage at **$0.30 per GB/month**; confirm the included storage, selected capacity and total in the dashboard before approving an upgrade. Taxes, currency conversion, usage above included bandwidth/build allowances, domain registration and any separately priced services are additional. No extra worker or paid Render Pro workspace is assumed here.

On Render's [pricing page](https://render.com/pricing), app hosting appears under **Compute → Services & Workers**, and database pricing under **Postgres**. New plan labels may use CPU/RAM identifiers: the $7 app is `0.5c-512mb` (formerly Starter), the $6 database is `0.1c-256mb`, and the $19 database is `0.5c-1g`. See [compute plan specifications](https://render.com/docs/compute-plans) and [billing details](https://render.com/docs/faq#what-does-render-bill-for).

### Is $13–15 enough for 5–10 users?

**It is a reasonable budget to try for a small team with light usage; it is not a verified capacity guarantee.** SpRocket has not yet been load-tested with 5–10 simultaneous users on these plans. The number of stored records, retained email history, simultaneous inbox imports and reporting requests matter more than the number of invited users alone. The starter app has only 512 MB RAM and the smallest paid database only 256 MB.

Start with a small import window and test the team's normal work. Watch app/database memory, CPU, response times, failed requests and sync delays in Render. If database load is the constraint, the $26–28 option is the next budgeting example; if app memory or CPU is the constraint, increase app compute instead. Extra memory creates headroom but does not replace performance testing. Before a larger rollout, test pagination and activity-history growth: the current app loads workspace records and activity into the browser together.

CRM members sign in to SpRocket; they do **not** each need a Render dashboard account. Adding CRM users does not create a SpRocket licence charge, although increased usage can require larger hosting plans.

### Which upgrades remove the trial limits?

Upgrade **both the app service and the database** for an always-on installation. A paid database alone does not stop a free app from sleeping after 15 idle minutes and taking about a minute to wake. Upgrading the Render workspace to Pro alone also does not upgrade those resources. See [Render's free-instance limits](https://render.com/docs/free).

The free trial template sets `SPROCKET_WEB_JOBS=0`. Moving to paid hosting does not change that setting automatically. To run the existing background scheduler, an administrator must enable `SPROCKET_WEB_JOBS=1` on the always-on service and configure each account's sync preferences. Keep the documented single-process deployment; changing the worker count requires a separate review of sync/OAuth state. Preserve the database and encryption key and follow [UPDATES.md](UPDATES.md) when making changes.

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
- **No deal stages are available:** new installations include an editable Sales Pipeline. If it has been removed or this workspace predates the template, create a pipeline and stages under Configuration → Pipelines.
- **The free app takes time to open:** Render's free app sleeps after idle periods. An always-on plan removes that limitation.
- **I lost my password:** try your already-linked Google account. Self-service password recovery is not yet implemented; preserve administrator access and a recovery plan.

Report reproducible problems through [GitHub Issues](https://github.com/russrdfx/SpRocket-CRM/issues). Include the release, hosting type, steps and a redacted screenshot; omit credentials, invitation links, customer records and private messages.

For later upgrades, use **Configuration → Updates** and follow [UPDATES.md](UPDATES.md). The administrator updates the existing workspace instead of repeating company setup.

## Make Home your own

Switch between **Daily desk**, **Sales overview** and **Relationship hub**. Choose **Customize home** to save your own layout. New installations include an editable Sales Pipeline under Configuration → Pipelines. Use the profile menu’s **Feature request & feedback** to prepare an email to russ@rdfx.ca. See [DASHBOARD.md](DASHBOARD.md).

## Arrange your sidebar

Use **More tools** to find a tool and pin it to the sidebar. Select a section heading to collapse it, or remove shortcuts you do not need. These choices are saved for your user. See [NAVIGATION.md](NAVIGATION.md).

## Enrich contacts and companies

Open **Configuration → Data Enrichment** to connect Apollo or import a provider CSV without an API account. Use **Enrich** on a record or select rows in the contacts/companies list. Review identity and proposed fields before applying; existing values stay unselected. See [the enrichment guide](ENRICHMENT.md) for mapping, limits, source history and undo.

## Optional email open tracking

On the web version, an administrator can enable **Configuration → Tracking & Analytics**. Choose your inbox default, or use **Track opens** for individual messages. Click **Opened N times** to view timestamps. See [the tracking guide](EMAIL_TRACKING.md) for details. Tracking requires a public HTTPS installation and applies to messages composed in SpRocket.

## Follow-ups and reusable emails

Use **Schedule follow-up** on a contact or deal, or **Create follow-up task** on an email. **Tasks** now opens My tasks with due-date views and completion/rescheduling actions. Find **Message Templates** in **More tools → Work**, then preview and apply a template in the email composer. See [the workflow guide](FOLLOWUPS.md).
