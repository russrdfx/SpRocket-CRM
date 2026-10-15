# Background work and verified backups

**Configuration → Background services** shows host job start, finish, last successful cycle and failure count. Only administrators can inspect it. Checks older than five minutes are flagged. Provider payloads and private inbox contents are never returned by this screen.

`SPROCKET_WEB_JOBS=1` enables the existing host worker: enabled personal mail sync each minute, opted-in Calendar windows each ten minutes, inactive-deal task rules and daily observed sales snapshots. Deactivated users are excluded. Enable it on an always-on, single-process host. Sleeping Render Free instances stop background work while asleep; the pilot remains at `SPROCKET_WEB_JOBS=0`. No keep-alive, paid upgrade or external scheduler is installed. Notification delivery still needs an open CRM browser; background email/push reminders are not included.

## Docker Compose backup tool

Run from the installation root with host Python 3 and Docker Compose available:

```sh
python3 deploy/verified_backup.py --root /srv/sprocket --folder /srv/sprocket/backups
```

This targets the bundled Compose `db` service using its matching PostgreSQL tools. It writes a private custom-format archive, checks its table of contents, creates a uniquely named disposable verification database, performs a full restore, checks required tables, then removes only that verification database. A verified archive and `latest-verified-backup.json` receipt are published only on success. Failed attempts retain an `.incomplete` file and leave the last successful receipt intact. The tool does not restore over the live workspace, delete old backups or upload backups elsewhere. Storage use grows until the administrator applies an appropriate retention policy.

For daily execution, a Linux hosting administrator can add this to their own scheduler after a successful manual test (adjust paths):

```cron
15 3 * * * /usr/bin/python3 /srv/sprocket/deploy/verified_backup.py --root /srv/sprocket --folder /srv/sprocket/backups >> /srv/sprocket/backups/backup.log 2>&1
```

Copy verified archives to a private off-site destination and separately retain `deploy/.env`/the installation encryption key. A database restore alone cannot recover encrypted connections without that key. The restore test checks archive/table recovery; it does not prove the separate key is backed up. Full Docker-host validation remains required; regression tests simulate command success/failure and cleanup, not a real Docker engine.

To display receipts, mount the host backup folder read-only into the app and set `SPROCKET_BACKUP_RECEIPT` to the mounted `latest-verified-backup.json`. A receipt older than 36 hours is flagged. This attests to the backup tool's latest restore test, not off-site storage or key retention. Missing configuration is shown explicitly.

Render's external PostgreSQL service is not the bundled Compose database. Use Render backups or an administrator-run external PostgreSQL backup/restore test. This Docker tool does not automatically back up the Render pilot. Its current verified local backup procedure remains available before deployments.
