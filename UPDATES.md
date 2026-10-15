# Updates and upgrades

SpRocket Web v0.2.0-beta.2 adds **Configuration → Updates** and installed-version information in **About SpRocket CRM**. Each company chooses when to upgrade its existing installation. The site, database, users, ownership, settings and original encryption key stay in place; company setup is not repeated.

## Check for an update

An administrator opens Configuration → Updates and chooses Stable or Beta, then clicks **Check for updates**. The app contacts the public SpRocket GitHub release API on demand; it does not send company data, provider credentials or mailbox contents. Results are cached for one minute. There is no background installation or automatic code execution.

Web installations check only `web-v…` releases; desktop installations check only `v…` releases. Beta includes stable and prerelease versions; Stable excludes prereleases. The current releases are previews, so an empty Stable result is expected. Local development checkouts are labelled separately and do not offer managed release checks. Release notes are shown as text, never executed as HTML.

## Render: update the existing service

1. Review the web release notes and any migration instructions.
2. Create and verify a full PostgreSQL backup using your hosting backup procedure. Preserve `SPROCKET_TOKEN_SECRET` separately. CSV exports are not a full database backup.
3. In your existing Render service, choose **Manual Deploy → Deploy a specific commit** and use the commit linked from the approved release tag. Keep the same database connection and secrets.
4. Wait for Live, refresh SpRocket, and confirm the version/build under About and your records/connections.

This replaces the app within the same service. It is a deployment of an update, not a new company deployment. The app intentionally does not store a Render account token or automatically trigger upgrades: the Free trial has no managed backup facility and cannot guarantee a durable pre-upgrade backup. See [Render deployment controls](https://render.com/docs/deploys) and [RENDER.md](RENDER.md#backups-and-expiry).

If an app rollback is needed, use Render's available rollback controls for your plan and follow the release's database compatibility notes. An app rollback is not a database restore. Never run an older app against an incompatible newer schema.

## Docker: approved host-side upgrade

The hosting administrator runs this tool on the existing Docker Compose host. It requires Python 3, Docker Compose, an existing `deploy/.env`, the running app/database, available disk space for a build and backup, and outbound HTTPS to GitHub. The tool does not run inside the CRM and does not give the CRM access to the Docker socket. Release downloads are bounded to 25 MB compressed and 50 MB expanded, unsafe paths/symlinks are rejected, and backup validation reads only the archive header before listing it so large database backups are not loaded into memory.

Use a trusted copy of `deploy/upgrade.py` from this release with `--root` pointing to your existing installation if you have downloaded the release elsewhere. The tool resolves an exact published web release to its Git commit, downloads that source from the repository, validates archive paths and its upgrade contract, and builds a version-specific app image. Future releases with an incompatible database contract require their own reviewed migration procedure; the tool stops rather than guessing.

Preview first:

```sh
python3 deploy/upgrade.py --root /srv/sprocket --version web-v0.2.0-beta.7
```

For the first upgrade from the original web beta, which had no version metadata, also supply `--from-version 0.2.0-beta.1` after confirming that this is what you installed. Never use that option to bypass a known incompatible version.

Approve after reviewing the target:

```sh
python3 deploy/upgrade.py --root /srv/sprocket --version web-v0.2.0-beta.7 --approve
```

The tool:

1. Locks upgrades so only one host process runs at a time.
2. Builds the target app before stopping the existing app.
3. Stops app writes and creates a private PostgreSQL custom-format backup; checks the archive header and listing.
4. Recreates only the app in the **same Compose project**, retaining its environment file and named volumes. It never runs `down` or removes volumes.
5. Verifies application health and the installed version. If backup or startup verification fails, it restores the prior app image and checks readiness.
6. Records the target commit, previous image, backup location and result under `.updates/last-upgrade.json`. That folder and backups are excluded from source control and Docker build context.

Keep the pre-upgrade backup and copy it off-host under your usual backup policy. The updater keeps the database and doesn't replace the original source checkout; subsequent updates use versioned source under `.updates/`. Use the tool again rather than rebuilding the old source checkout with a generic `up --build` command.

To restore the previous app image after this schema-compatible upgrade:

```sh
python3 deploy/upgrade.py --root /srv/sprocket --rollback --approve
```

This retains current data. Full database restoration is a separate operation using `deploy/restore.sh` and the recorded backup, with the app stopped. A database restore loses changes made after that backup; review it with the administrator. The current upgrade contract permits app rollback only within schema version 1. Automatic downgrade across future schema changes is not supported.

## Database changes

The web server stores its baseline schema version in PostgreSQL and refuses to start against a newer unsupported version. Future migrations must be registered in the ordered migration code, update the upgrade compatibility contract, and be tested for both upgrade and recovery. This release establishes schema version 1; it makes no destructive data migration.

## Mac desktop updates

Once packaged with this feature, the desktop app checks only Mac releases and shows its actual installer version. Back up the local database, quit the app, install the matching new package and reopen it. Data lives outside the application. The current v0.1.8 download predates this Updates screen. Signed/notarized installer work is needed before a seamless unattended Mac updater; this release does not add automatic desktop installation.

## Verification and limits

Release selection, prerelease ordering, cache behaviour, protected routes, malformed archive rejection, upgrade contracts, existing project retention, backup failure and app rollback are covered by tests. The Render web edition can be exercised live. Full Docker-host upgrade/recovery verification still requires an actual Docker host; simulated safety tests do not replace that recovery drill. Automatic installation remains disabled. Versioned public container-image publishing and optional unattended upgrade scheduling remain future work.

Web v0.2.0-beta.3 added personalized Home dashboards, feedback drafts and a new-installation sales pipeline template. Upgrade existing workspaces in place; their pipelines remain unchanged. The additive dashboard preferences table is created on startup. See [DASHBOARD.md](DASHBOARD.md) for behavior and backup compatibility.

## Web v0.2.0-beta.4

Adds personal navigation, reviewed enrichment, opt-in hosted email-open tracking, contextual follow-ups and email templates. Upgrade in place after a verified backup. New tables and contact/company properties are additive; retired existing properties and customized pipelines are preserved. Provider credentials and the installation encryption key are retained. Email tracking starts disabled; Apollo requires an administrator-supplied API key. Neither is enabled automatically during upgrade. See [ENRICHMENT.md](ENRICHMENT.md), [EMAIL_TRACKING.md](EMAIL_TRACKING.md) and [FOLLOWUPS.md](FOLLOWUPS.md).

## Web v0.2.0-beta.5

Adds personal email-open, incoming-mail and task-reminder notifications, persistent unread state and preferences, and optional desktop alerts while the CRM is open. Contact/deal actions now use a consistent layout, and opening a new section resets its scroll position. README screenshots now show the private web edition using fictional data.

Failed release checks can be retried immediately and preserve the last successful result for the selected channel. GitHub rate limits and network failures have clearer guidance and a direct release-page link. No update is installed automatically.

The database additions are additive. Existing records, pipelines, custom fields, profiles, connected accounts and encryption keys are retained. Back up before deploying the beta.5 commit to the existing service; do not create a new workspace or database. See [Notifications](NOTIFICATIONS.md).

## Web v0.2.0-beta.6

Adds dedicated company details, cleaner deal forms, consolidated owner labels, live deal forecasting, explicit pipeline stage outcomes and an administrator setup checklist. See [FORECASTING.md](FORECASTING.md) and [ONBOARDING.md](ONBOARDING.md).

Back up and verify restoration before deploying this commit to the existing service. Keep the same database and encryption key. The new setup progress table is additive; existing records, pipelines, properties, profiles and Google connections are retained. Older stages use their existing Won/Lost names until an administrator explicitly sets their outcome. Background jobs and provider integrations are not enabled automatically.

## Web v0.2.0-beta.7

Adds ticket statuses/details, team access management and recovery, host job health, Docker verified-backup tooling, and observed sales insights. New tables and property definitions are additive; existing records, ticket pipeline metadata, customized fields and provider connections remain. Retain the same database and encryption key and take a verified backup before updating the existing service. Existing deals start stage observation at this update; no earlier history is fabricated. Background jobs and backup schedules are not enabled automatically. See [TEAM_ADMIN.md](TEAM_ADMIN.md), [HOST_OPERATIONS.md](HOST_OPERATIONS.md) and [SALES_INSIGHTS.md](SALES_INSIGHTS.md).
