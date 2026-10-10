![SpRocket full-color icon](web/assets/brand/icons/sprocket-symbol-color.png)

# SpRocket CRM

A free, MIT-licensed, configurable CRM foundation.

## Run locally

Requires Python 3.9 or later. The local demo needs no packages. Optional SSO requires the dependencies in [SSO setup](SSO.md).

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
- Overview counts and weighted value using configured probabilities.
- Validation prevents removal of pipelines or stages still used by records.

The workspace starts empty. No external CRM records or configuration are imported. Activity logs do not send email or place calls.

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
- Click a contact to open its full details page. Use **Edit contact** or **Edit links** to edit properties and associations. Email and call shortcuts log activity; they do not send messages or place calls.
- Click a deal to see its details. Use **Edit deal** for fields and relationships; use **Activities** to search, filter and log notes, emails, calls or meetings. These are logs, not delivery tools.
- Open **Configuration**: Account Defaults manages the workspace; Properties manages fields; Objects manages record types and pipelines.
- Use **More → Reporting → Reports** for the three live summaries. Other menu areas show their implementation status.

## Current scope

This is a local single-user development foundation, not a production deployment or functional CRM replacement. It binds to loopback only. Owner names are assignment labels, not login accounts. Team roles, audit history, collaboration, backups, an automation engine, inbox synchronization, email delivery, marketing, quotes, invoicing and richer reporting remain roadmap work. Do not expose this development server publicly.

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

The canonical repository is [SpRocket-CRM](https://github.com/russrdfx/SpRocket-CRM). Its GitHub social preview uses the full-color logo with a 1280 × 640 canvas; editable vector and PNG versions are included in the logo directory. GitHub displays the owner's avatar beside repository names and does not provide a separate repository avatar.
