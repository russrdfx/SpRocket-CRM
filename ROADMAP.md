# SpRocket CRM roadmap

## Product requirements

- Free, open source, self-hostable, MIT licensed.
- Account- and portal-agnostic. No external CRM identifiers, customer data, branding or customer-specific custom configuration in source or sample data.
- Configuration is foundational: multiple pipelines, stage order/probabilities, object types, typed properties, relationships, saved views and rules belong to users.
- Reference general CRM functionality; use an original interface.

## Delivered foundation

Local persistent record management, generic typed fields, configurable record types and pipelines, assignment labels, record relationships, activity logs, list/board views with drag-and-drop stage changes, enriched cards, stage totals and weighted values, three-column deal and contact details pages, a profile menu with administrator designation, clickable dashboard drilldowns, searchable activity timelines, live summary reports and overview metrics. Expanded navigation and searchable/tabbed Settings establish the product structure; unfinished areas are explicitly labeled as planned. An optional fictional sample-data script is included. This is an initial development release, with optional OIDC sign-in and an explicit subject allowlist. Team roles and workspace isolation remain future work.

## Personal email delivered

Google and Microsoft personal inbox adapters now share a connection UI, encrypted tokens, date-range historical imports, optional foreground automatic sync, rich-text compose/reply, HTML signatures, contact/deal matching, automatic contact/domain-company creation and shared activity logging and follow-up tasks. See [EMAIL.md](EMAIL.md). Live-provider registration and consent tests remain required. Next email work: provider delta/history cursors, closed-app sync, incoming attachments, shared inboxes and assignment.

## Record creation delivered

Create dropdown and type-specific side panels for contacts, companies, deals, tickets and tasks, with searchable associations, custom fields, create-and-add-another, additive property migration and editable deal line items. Tasks support completion, due dates/times, in-app reminders, optional foreground desktop notifications and daily/weekly/monthly next occurrences on completion. Closed-app scheduling remains future work.

## Next releases

1. Production foundation: expanded identity management, roles, workspaces, audit history, migrations, backups, PostgreSQL deployment and container packaging. Enforce workspace isolation in every API operation.
2. Rich records: field editing/retirement, required and conditional fields, relationship labels, import/export, merge, saved views and advanced filtering. Handle configuration migrations without data loss.
3. Automation: configurable triggers, conditions and actions; task creation, assignment, stage changes, scheduling, retries, execution logs and loop prevention.
4. Service: SLA calendars and clocks, support queues, shared inbox channels, conversation assignment and knowledge base.
5. Sales: product catalog, line items, quote documents, approvals, forecasting, sequences, playbooks and meeting scheduling.
6. Marketing: static and dynamic segments, consent and subscription preferences, templates, email delivery adapters, campaigns, forms and landing pages.
7. Commerce: invoices, subscriptions, orders and optional payment-provider adapters.
8. Reporting: configurable dashboards, funnels, conversion/cohort reports, attribution and activity metrics.

No premium-feature gates are planned for the open-source core. External email, calling and payment services may have their own costs. Feature availability in a reference account does not determine Sprocket's requirements. Features that were not exposed through MCP require independent product design; inspection is not evidence of complete parity.

## Desktop distribution

Implemented: Electron launcher, bundled Python backend, Apple Silicon Mac DMG build, separate persistent data directory, single-instance behavior, server ownership checks, native database backup and system-browser sign-in handoffs. See [DESKTOP.md](DESKTOP.md).

Next: signed/notarized Mac releases, clean-machine and live-provider testing, Intel Mac and Windows packaging, and automatic updates.

Mac release validation now requires strict code-signature verification before and after ZIP extraction. v0.1.0 had invalid bundle integrity metadata; v0.1.1 adds ad-hoc development signing.

Implemented data cleanup: exact contact-email/company-domain duplicate review, transactional reviewed merges retaining fields/links/activities, imported-record review and personal-domain company exclusion for new imports. Fuzzy matching and merge undo remain planned.

## Latest workspace productivity development

Implemented in development source: discoverable pipeline settings; personal saved filter views; mapped/reviewed CSV imports and scoped export; independent read-only Google Calendar connection with date-window pagination and reviewed meeting logging; source-backed company website suggestions with approval; opt-in stage/inactivity follow-up tasks with execution history; validated administrator database backup/restore with a safety copy. See [WORKSPACE.md](WORKSPACE.md) and [CALENDAR.md](CALENDAR.md). Live Google Calendar consent remains to be tested. Advanced enrichment providers, closed-app automation and older-schema browser restore remain future work.

## Phone formatting delivered

Country selection and local phone formatting for contact, company and profile fields, inline contact editing, a workspace country default, and normalization on record/profile saves and CSV imports. Incomplete or ambiguous input is preserved. Number verification remains outside this feature.

## Private web preview

Initial web deployment: Gunicorn, PostgreSQL, Docker Compose/Caddy HTTPS, first administrator bootstrap, account invitations, admin/member permissions, persistent sessions, host-side email and task-rule checks, desktop record migration and PostgreSQL backup/restore tools. Hosting on an organization-owned domain and live Google callbacks require an integration test. Google OIDC sign-in now supports explicit linking for existing users and invitation-based admission without a new password. Password recovery and account lifecycle administration remain pending. Optional unattended Calendar refresh and encrypted Google credential entry are included in the web preview.

## Render pilot deployment

Free web/database Blueprint, provider credentials encrypted in PostgreSQL, platform port/origin detection and unauthenticated readiness probes. Background jobs are disabled for sleeping free instances. Free database expiry and backup limitations are documented in RENDER.md.

## Public web beta distribution

Web v0.2.0-beta.1 adds a guided company deployment path, a Render trial button with manual update control, durable hosting guidance, tagged source distribution and explicit beta limits. See [GETTING_STARTED.md](GETTING_STARTED.md) and [WEB_RELEASE.md](WEB_RELEASE.md). Google Cloud registration and hosting administration remain company responsibilities.

Web v0.2.0-beta.2 adds edition-specific release checks, stable/beta selection, installed version/build metadata, a database-version guard and an approved Docker host updater with backup and app rollback. Render uses its existing deployment controls. Automatic installation, prebuilt image publishing and a signed unattended Mac updater remain future work. See [UPDATES.md](UPDATES.md).

## Personalized Home delivered

Three purpose-specific Home tabs, owner-scoped card visibility/order and layout preferences, a private calendar agenda, direct task completion, deal and contact follow-up summaries, and compact deduplicated conversations. New installations have a removable, editable Sales Pipeline template; upgrades preserve existing configuration. Profile-menu feedback prepares a user-reviewed email to russ@rdfx.ca with version context. See [DASHBOARD.md](DASHBOARD.md).
