# SpRocket CRM Web v0.2.0-beta.1

Public beta released October 12, 2026. This is the first tagged private web edition; it does not replace the separately packaged v0.1.8 Mac preview.

## Install

Start with [GETTING_STARTED.md](GETTING_STARTED.md). Use the Render deployment button for a temporary trial or Docker Compose for a lasting private installation. Each company hosts its own workspace/database on its provider address or domain. Software is MIT-licensed and free; hosting charges and Google application registration are separate.

## Available

- Contacts, companies, deals, tasks and tickets; custom fields and record types; configurable pipelines and stages.
- Linked records, inline contact editing, phone country selection/formatting, shared activity timelines and dashboard drilldowns.
- Deal boards with stage totals, weighted values and drag-and-drop changes; compact filters and personal saved views.
- Reviewed CSV import/export, company website suggestions requiring approval, and opt-in follow-up task rules.
- Gmail connections, chosen date-window imports, automatic contact/company matching, rich email display/compose/reply and HTML signatures.
- Independent read-only Google Calendar sync and reviewed meeting logging.
- First administrator bootstrap, password accounts, one-use invitations, administrator/member permissions and persistent eight-hour sessions.
- Google sign-in through explicit account linking; invitation acceptance with a matching Google account without a new password.
- PostgreSQL storage, encrypted provider configuration/tokens, Docker/Gunicorn deployment, optional background jobs, desktop record migration and backup/restore tooling.

## Preview limits

- One company workspace per deployment; no public signup or automatic provisioning of separate companies.
- Google Cloud app registration remains an administrator task. Provider testing/verification requirements still apply.
- Password reset and user deactivation/role-management screens are not yet implemented.
- Shared CRM activities are visible to workspace members. Personal caches and views are user-scoped; fine-grained record permissions are not included.
- Render Free is temporary: app sleep, manual sync and a database expiring after 30 days. Use durable storage and backups for ongoing use.
- One application process is supported. Provider connection/import continuation coordination across replicas is not implemented.
- Docker Compose/Caddy still needs a separate end-to-end host validation. The Render Docker/HTTPS pilot, Gmail, Calendar and Google sign-in have been exercised live.
- Some navigation sections remain explicitly marked Planned feature. This beta is not a production-readiness certification.

## Verification

103 desktop/backend regression tests and 14 PostgreSQL web integration tests passed, along with both presentation suites. Web tests cover session persistence, invitations and member permissions, Google token signature/issuer/audience/expiry verification, browser binding, replay prevention, explicit linking, invited admission, private ownership, encrypted configuration, migration and opt-in jobs. A PostgreSQL backup/restore was tested against a separate database. Screenshots use fictional sample records; older Mac screenshots are labelled separately.

## Updates and feedback

Updates are chosen by each hosting administrator; the Render template disables automatic upstream deploys. Back up your database and preserve the encryption key before updating. Use [GitHub Issues](https://github.com/russrdfx/SpRocket-CRM/issues) for reproducible feedback, with private data redacted.
