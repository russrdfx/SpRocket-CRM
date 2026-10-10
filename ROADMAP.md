# SpRocket CRM roadmap

## Product requirements

- Free, open source, self-hostable, MIT licensed.
- Account- and portal-agnostic. No external CRM identifiers, customer data, branding, pipeline names or custom configuration in source or sample data.
- Configuration is foundational: multiple pipelines, stage order/probabilities, object types, typed properties, relationships, saved views and rules belong to users.
- Reference general CRM functionality; use an original interface.

## Delivered foundation

Local persistent record management, generic typed fields, configurable record types and pipelines, assignment labels, record relationships, activity logs, list/board views with drag-and-drop stage changes, enriched cards, stage totals and weighted values, three-column deal and contact details pages, a profile menu with administrator designation, clickable dashboard drilldowns, searchable activity timelines, live summary reports and overview metrics. Expanded navigation and searchable/tabbed Settings establish the product structure; unfinished areas are explicitly labeled as planned. An optional fictional sample-data script is included. This is an initial development release, with optional OIDC sign-in and an explicit subject allowlist. Team roles and workspace isolation remain future work.

## Personal email delivered

Google and Microsoft personal inbox adapters now share a connection UI, encrypted tokens, manual bounded message import, plain-text compose/reply, signatures, contact/deal matching, automatic contact/domain-company creation and shared activity logging and follow-up tasks. See [EMAIL.md](EMAIL.md). Live-provider registration and consent tests remain required. Next email work: background incremental sync, attachments, richer composition, shared inboxes and assignment.

## Record creation delivered

Create dropdown and type-specific side panels for contacts, companies, deals, tickets and tasks, with searchable associations, custom fields, create-and-add-another, additive property migration and editable deal line items. Tasks store queue, due time and reminder/repeat preferences; automated scheduling and notifications remain future work.

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
