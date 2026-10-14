# SpRocket CRM Web v0.2.0-beta.6

Released October 14, 2026. This is the private web release; the separately packaged Mac preview remains v0.1.8.

## Install or upgrade

Start with [GETTING_STARTED.md](GETTING_STARTED.md). Existing installations should follow [UPDATES.md](UPDATES.md) and take a verified backup. Each company keeps its own deployment, database and domain. SpRocket is free MIT-licensed software; hosting and enrichment provider costs are separate.

## New in this release

- Organized navy sidebar with proper icons, collapsible groups, searchable tools and personal pins. Existing logo preserved.
- Apollo configuration, encrypted API key storage, field mapping, daily lookup limits and reviewed contact/company enrichment. LinkedIn fields and reviewed Apollo/ZoomInfo CSV updates work without an Apollo API account. Source history and guarded undo protect newer changes.
- Optional hosted email-open tracking: **Opened N times** expands to show timestamps and relative ages. Administrator, inbox and per-message controls; contact exclusions; expiry and rapid-load deduplication. Tracking is off by default.
- My/Team/Unassigned tasks, overdue/today/upcoming views, contextual follow-ups from contacts/deals/emails, reminders, rescheduling and guarded completion. Existing saved views and repeat behavior remain available.
- Personal and workspace email templates, supported contact/company/user placeholders, composer preview and explicit draft replacement. Missing/ambiguous data stays flagged; unresolved placeholders are blocked before sending.
- Existing focused Home dashboards, customizable layouts, feedback drafts, email/calendar connections and editable pipeline settings remain available.

Guides: [Navigation](NAVIGATION.md), [Enrichment](ENRICHMENT.md), [Email tracking](EMAIL_TRACKING.md), [Follow-ups and templates](FOLLOWUPS.md).

New tables and property definitions are additive. Credentials, identities, records, activities and customized pipelines are retained by an in-place upgrade. Apollo and email tracking are not enabled by deployment. Older browser-restorable SQLite backups must match the current schema; retain the full pre-upgrade backup for recovery.

## Preview limits

- One company workspace per deployment; no public signup or automatic provisioning of separate companies.
- Google Cloud app registration remains an administrator task. Provider testing/verification requirements still apply.
- Password reset and user deactivation/role-management screens are not yet implemented.
- Shared CRM activities are visible to workspace members. Personal caches and views are user-scoped; fine-grained record permissions are not included.
- Render Free is temporary: app sleep, delayed background checks and a database expiring after 30 days. Use durable storage and backups for ongoing use.
- One application process is supported. Provider connection/import continuation coordination across replicas is not implemented.
- Docker Compose/Caddy still needs a separate end-to-end host validation. The Render Docker/HTTPS pilot, Gmail, Calendar and Google sign-in have been exercised live.
- Some navigation sections remain explicitly marked Planned feature. This beta is not a production-readiness certification.

## Feature limits

Apollo live lookups await an API-enabled account. ZoomInfo currently supports reviewed CSV imports. LinkedIn profile/company URLs are supported; direct LinkedIn data access is not provided. Tracking applies to new messages sent from the hosted CRM; it cannot retroactively track Gmail-composed emails. Open counts reflect image loads, with limitations explained in the tooltip and guide. A standalone localhost desktop app cannot receive opens. Live recipient-client testing remains a post-deployment check with consenting test inboxes. Reminders are foreground notifications, not background email or push delivery.

## Verification

153 unique Python regression checks, 23 disposable PostgreSQL checks and 12 JavaScript suites pass. Browser checks use fictional SAMPLE data and cover navigation, enrichment review/save/undo, tracking expansion, follow-up scheduling/rescheduling/completion and template preview/application. Tests send no real mail. Production updates use a fresh backup whose isolated restore and encrypted Google configuration are verified before deploying.

## New in beta.5

A personal notification center covers tracked email opens, incoming synced email and due task reminders, with saved unread state/preferences and optional desktop alerts. Contact and deal cards have grouped, responsive actions. Release-check failures preserve the last successful result and allow immediate retry. GitHub documentation screenshots now show the web edition. See [Notifications](NOTIFICATIONS.md) and [Updates](UPDATES.md).

## New in beta.6

Company names open dedicated details pages with related records and activity. Deal forms no longer navigate away to configuration, and owner lists consolidate the signed-in user’s name and email aliases while preserving existing assignments. Live deal forecasts filter by period, owner and pipeline; stages support explicit Open/Won/Lost outcomes. Administrators have a guided setup checklist with saved personal progress and optional integrations. See [Forecasting](FORECASTING.md) and [Getting started checklist](ONBOARDING.md).

The setup progress table is additive. This update preserves existing configuration, records, connections and encryption keys. It does not enable background jobs, providers or automatic email sending.
