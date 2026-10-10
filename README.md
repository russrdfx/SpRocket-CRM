# Sprocket CRM

A free, MIT-licensed, configurable CRM foundation. No HubSpot connection, account configuration, or customer data is included.

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
- Record relationships and notes, call, email and meeting activity logs.
- Overview counts and weighted value using configured probabilities.
- Validation prevents removal of pipelines or stages still used by records.

The workspace starts empty. No external CRM records or configuration are imported. Activity logs do not send email or place calls.

## Current scope

This is a local single-user development foundation, not a production deployment or full HubSpot replacement. It binds to loopback only. Owner names are assignment labels, not login accounts. Authentication, authorization, audit history, collaboration, backups, an automation engine, inbox synchronization, email delivery, marketing, quotes, invoicing and richer reporting remain roadmap work. Do not expose this development server publicly.

## Test

```sh
python3 test_server.py
```

Tests cover empty initialization, custom pipelines, persistent records, invalid stages, referenced-stage protection, activity cleanup, and cross-origin write rejection.

## License

MIT. See LICENSE.
