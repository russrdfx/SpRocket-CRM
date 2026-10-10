![SpRocket full-color icon](web/assets/brand/icons/sprocket-symbol-color.png)

# SpRocket CRM

A free, MIT-licensed, configurable CRM foundation.

## Desktop app

**Mac download:** [v0.1.2 preview release](https://github.com/russrdfx/SpRocket-CRM/releases/tag/v0.1.2) for Apple Silicon Macs. The package passes strict signature integrity verification with an ad-hoc development signature; Developer ID signing and notarization remain planned. Avoid the defective v0.1.0 package.

An Apple Silicon Mac desktop installer now bundles the CRM and Python server, uses the full-color SpRocket icon, and keeps data outside the app. The preview build is ad-hoc signed for development and is not notarized. See [desktop installation, backups and build instructions](DESKTOP.md). Windows, Intel Mac and signed public releases remain planned.

## Run locally

Requires Python 3.9 or later. The local demo needs no packages. Optional SSO and email integrations require the dependencies in [SSO setup](SSO.md).

```sh
python3 server.py
```

Open http://127.0.0.1:8765. Set `PORT` to use another port and `SPROCKET_DB` to change the database location. Workspace data persists in `data/sprocket.db` and is excluded from Git.

## Working features

- Contacts, companies, deals, tasks and tickets, plus user-created record types.
- Create, edit, delete and search records.
- Typed custom fields: text, email, numbers, dates, checkboxes and selections.
- User-defined pipelines and stages for any record type. Stage names, order and probabilities are configurable.
- Board and list views, pipeline filtering, workspace owner names and currency.
- Drag cards between stages; changes persist automatically. Cards show owner, close date, amount and associations. Each stage shows total and probability-weighted value.
- Deal details page with properties, related records, searchable activity history and activity logging.
- Live reports for record counts, pipeline values and activity totals.
- Expanded two-column module navigation and searchable Settings categories with tabbed pages. Unimplemented sections are labeled **Planned feature**.
- Record relationships and notes, call, email and meeting activity logs.
- Personal Google and Microsoft inbox connections, manual sync, plain-text compose/reply, signatures, contact/deal matching and email follow-up tasks. See [Email setup](EMAIL.md); provider credentials and a stable token encryption key are required.
- Overview counts and weighted value using configured probabilities.
- Validation prevents removal of pipelines or stages still used by records.

The workspace starts empty. No external CRM records or configuration are imported. Activity logs do not send email or place calls. The separate Inbox compose/reply feature sends through a connected provider only when you choose Send.

## Optional sample data

```sh
python3 seed_sample.py
```

Adds 13 fictional records (3 contacts, 2 companies, 3 deals, 3 tasks and 2 tickets), four activity entries, a demo owner label and a three-stage demo pipeline. Every record name begins with `SAMPLE`; emails and websites use reserved `.example` domains. Run against the same `SPROCKET_DB` as the server, then reload the browser. Re-running skips existing sample records and activities. Existing records are preserved. The database itself is never committed.

## Recent interface updates

- Profile dropdown with profile details, account settings, SSO administration for designated admins, and sign-out for authenticated users. Local demo identity is labeled explicitly.
- Click dashboard tiles to open records or the weighted-value breakdown. Activity entries open their records; the Recent activity heading opens the full history.
- Contact details use a three-column layout with properties, activity search and filters, logging shortcuts, related records and upcoming linked tasks. Overview, Activities and Intelligence tabs show implemented functionality or an explicit planned status.
- Records without pipelines always use list view, preventing an empty board from hiding contacts, companies or tasks.
- Each sample deal has a linked contact, company and task. Sample relationships are visible from both ends in detail pages.

## Using the interface

- Open Deals and choose **Board view**. Drag a card into a stage, including a different pipeline, or into **No pipeline**.
- Click a contact to open its full details page. Use **Edit contact** or **Edit links** to edit properties and associations. Activity shortcuts log activity. The separate **Send email** button uses a connected account; calls are not placed.
- Click a deal to see its details. Use **Edit deal** for fields and relationships; use **Activities** to search, filter and log notes, emails, calls or meetings. These are logs, not delivery tools.
- Open **Configuration**: Account Defaults manages the workspace; Properties manages fields; Objects manages record types and pipelines.
- Use **More → Reporting → Reports** for the three live summaries. Other menu areas show their implementation status.

## Current scope

This is a local single-user development foundation, not a production deployment or functional CRM replacement. It binds to loopback only. Owner names are assignment labels, not login accounts. Team roles, audit history, collaboration, backups, an automation engine, background inbox synchronization, bulk email delivery, marketing, quotes, invoicing and richer reporting remain roadmap work. Do not expose this development server publicly.

## Optional OpenID Connect SSO

Open **Configuration → Security → Single sign-on (SSO)** to save provider settings and test discovery. See [SSO setup](SSO.md) for provider registration, dependencies, environment configuration and activation.

Sign-in protects CRM pages and APIs when configured. Allowed identities share full workspace access; SSO administration requires server-designated administrator subjects. Secrets stay in the server environment. Saved non-secret settings stay in ignored local storage; environment values override them. Restart to activate changes.

The default unconfigured mode is a local demo without authentication. Discovery tests check provider metadata only; real-provider sign-in remains an integration check.

## Test

```sh
python3 test_server.py
# After installing SSO dependencies:
python3 -m unittest discover -p 'test_*.py'
```

Tests cover empty initialization, custom pipelines, persistent records, invalid stages, referenced-stage protection, activity cleanup, and cross-origin write rejection.

## License

MIT. See LICENSE.

## Brand assets

The supplied SpRocket vector logos, full-color symbol, monochrome variants, favicon and app icons are in `web/assets/brand/`. The app uses the dark horizontal logo in navigation, the light logo on sign-in, and the full-color favicon. The blue, orange and navy palette is applied to primary brand surfaces and accents. See [brand guide](web/assets/brand/guidelines/BRAND-GUIDE.md) for the supplied asset status and usage guidance. Selected PNG fallbacks are included alongside the vector library.

The canonical repository is [SpRocket-CRM](https://github.com/russrdfx/SpRocket-CRM). Its GitHub social preview uses the full-color logo with a 1280 × 640 canvas; editable vector and PNG versions are included in the logo directory.

## Personal email

Connect Google or Microsoft from **Inbox** or **Configuration → Integrations / Inboxes**. Setup instructions, supported scopes, privacy controls and limitations are in [EMAIL.md](EMAIL.md). Recent-message sync is manual and bounded. Sync automatically logs messages on contacts and linked deals, creates missing contacts, and links domain-based companies. The cache is owner-scoped under SSO; local demo mail is available to anyone using the local workspace. Provider registration and real-account integration checks remain necessary.

The email update passed 45 automated tests covering existing CRM/SSO behavior and mocked email-provider flows, including automatic record creation, activity deduplication, encrypted credentials, account ownership and send safeguards. Real-provider verification is still required.

## Create and edit records

The top **Create** dropdown opens Contact, Company, Deal, Ticket or Task in a right-side panel. Custom record types also appear. Record-list Create buttons use the same panels; edit keeps existing values and activity logging. Sticky actions include Create, Create and add another, Cancel, and Save for edits. Associations use searchable checkboxes instead of a multiple-selection list.

Contacts collect email, first/last name, owner, job title, phone, lifecycle stage and lead status. Companies collect domain/name, owner, industry/type, location, headcount, revenue, time zone, description and LinkedIn URL. Deals collect pipeline/stage, amount/date, owner/type/priority, relationships and description/quantity/price line items. A blank deal amount is calculated from its line items; an explicit amount is preserved. Tickets collect name, pipeline/status, description, source, owner, priority and create date. Tasks collect title, type, priority, relationships, assignee, queue, due date/time, reminder/repeat preferences and notes.

Task reminder/repeat preferences are stored; automated notifications and recurring-task generation remain planned. Deal line items are saved data; a product catalog, quotes and invoicing remain planned. Pipelines are required when available, with a no-pipeline path for an unconfigured workspace. Contact names can be derived from first/last name or email; company names can be derived from domain.

New default properties are added once without overwriting custom definitions or existing records. Configure labels/options and add custom properties through **Configure properties**. Later user removal of a default property is respected after the migration.

Record creation update validation: 48 automated tests pass. Browser checks verified the dropdown, task/company/deal panels, contact name derivation, saved line items, calculated amount and Create and add another. Temporary verification records were removed.

### Email imports and contact editing

Choose a date range and preview its message count before importing email. Imports process the entire selected range in batches, show progress, and avoid duplicate activities. New contacts belong to the signed-in user (or connected email address in local mode). Contact properties support direct editing with Save and Cancel, and owner selectors include the current user and connected inbox addresses. See [EMAIL.md](EMAIL.md).
