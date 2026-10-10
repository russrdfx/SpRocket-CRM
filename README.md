# Sprocket CRM

A free, MIT-licensed, configurable CRM foundation.

## Run locally

Requires Python 3.9 or later. No packages to install.

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

Adds 12 fictional records (3 contacts, 2 companies, 3 deals, 2 tasks and 2 tickets), four activity entries, a demo owner label and a three-stage demo pipeline. Every record name begins with `SAMPLE`; emails and websites use reserved `.example` domains. Run against the same `SPROCKET_DB` as the server, then reload the browser. Re-running skips existing sample records and activities. Existing records are preserved. The database itself is never committed.

## Using the interface

- Open Deals and choose **Board view**. Drag a card into a stage, including a different pipeline, or into **No pipeline**.
- Click a deal to see its details. Use **Edit deal** for fields and relationships; use **Activities** to search, filter and log notes, emails, calls or meetings. These are logs, not delivery tools.
- Open **Configuration**: Account Defaults manages the workspace; Properties manages fields; Objects manages record types and pipelines.
- Use **More → Reporting → Reports** for the three live summaries. Other menu areas show their implementation status.

## Current scope

This is a local single-user development foundation, not a production deployment or functional CRM replacement. It binds to loopback only. Owner names are assignment labels, not login accounts. Authentication, authorization, audit history, collaboration, backups, an automation engine, inbox synchronization, email delivery, marketing, quotes, invoicing and richer reporting remain roadmap work. Do not expose this development server publicly.

## Test

```sh
python3 test_server.py
```

Tests cover empty initialization, custom pipelines, persistent records, invalid stages, referenced-stage protection, activity cleanup, and cross-origin write rejection.

## License

MIT. See LICENSE.
