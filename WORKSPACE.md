# Workspace productivity

## Pipelines and stages

Open **Settings → Pipelines → + Pipeline**. Deals is the default record type. Name the pipeline, add stage names and probabilities, then save. Stages can be added, removed or renamed through **Edit pipeline & stages**; stages containing records cannot be removed until those records move. Shortcuts are available in Properties and deal creation forms. New workspaces start empty by design.

## Filters and saved views

Use the top search to search across the CRM. Record lists group owner, stage, company, pipeline and inactivity controls under the **Filters** dropdown; task lists also filter completion. The button shows the active filter count. Click outside or press Escape to close the dropdown. Inactivity uses the latest record edit or logged activity. Contacts' stage filter maps to Lifecycle / Lead stage. Save the current filter combination with **Save view**, then select it from the Saved view dropdown. Views belong to the sign-in identity; local mode uses one local operator. Saved views do not change visibility permissions.

## CSV import and export

Use **Configuration → Import & Export** and select a record type. Choose **Import** to upload a CSV, or export all records of that type. To export a specific group, save a filtered view from the records page and select it under **Records to export**. The export count previews the selected group. Import/export actions are kept out of the record-list toolbar. Imports accept UTF-8 CSV up to 500 KB / 1,000 rows. Map source columns to CRM fields, preview all proposed changes, and check **I reviewed these changes** before importing. Errors block the entire import. Previews expire after 15 minutes and reject records changed since review.

Exact contact emails and company domains match existing records. Exported `_record_id` can match other record types. Matching rows default to filling empty fields; choose Skip or explicitly Replace mapped populated fields. Blank CSV cells never erase existing values. Duplicate rows and ambiguous existing matches must be resolved before import. Reapplying the same file/mapping/mode is idempotent. Related `company_domain` and `contact_email` columns accept semicolon-separated values matching existing records; import companies first, then contacts, then deals/tasks. Pipeline/stage columns use configured IDs; exports provide these IDs.

Spreadsheet formula prefixes are escaped with an apostrophe on export. That protective apostrophe is preserved on import; remove it deliberately in the CSV if you want the original text. CSV export contains defined fields and key associations, not full activity history or every additional property. Use database backup for full fidelity recovery.

## Website enrichment

Open **Settings → Data Enrichment**, or **Review website enrichment** on a contact/company. The company's business domain identifies its website; personal email domains are excluded. An optional page URL must match that domain. Supported Organization JSON-LD facts include company name, description, city, region, postal code and LinkedIn company page. No paid provider is required.

Review the source link and individual field differences. Select fields to apply. Replacing populated fields requires explicit confirmation. A contact without a company can create/associate a domain company only after confirmation. Applied facts retain source/time metadata and a review note in the company timeline. Sites without supported structured facts produce no suggestions; individual job titles, personal phone numbers, employee counts and revenue are not inferred. Connections require public HTTPS, pin a validated public address and verify TLS; redirects are revalidated, and responses are limited to 1 MB. Suggestions expire after 15 minutes and reject stale records.

## Follow-up automation

Administrators can configure **Settings → Automation**. Rules start disabled until enabled. **Deal enters stage** creates a task on a future stage change made through editing or board drag. New record creation, CSV imports and existing stage assignments do not trigger it retroactively. **Deal stays inactive** creates a task when the latest deal edit/activity exceeds the selected number of days, excluding stages with 100% probability or names containing won/lost. Rename/localize terminal stages with this limitation in mind.

Task titles can use `{deal}`. Set a task owner or inherit the deal owner and choose days until due. Tasks link back to the deal. Each trigger is recorded to prevent duplicates; a later stage transition or renewed inactivity after a new activity/edit can create another task. Preview pending inactivity tasks before **Run now**. Enabled inactivity rules also run every minute while an administrator has the app visible and no dialog open. Closed-app scheduling, email actions, complex conditions and retries are future work. Execution history lists the most recent 50 tasks created.

## Backup and restore

Administrators use **Settings → Backup & Restore**. Download a consistent SQLite snapshot including settings, records, activities, profiles, saved views, mail/calendar caches and encrypted tokens. Files are private and contain sensitive workspace data. OAuth application credentials and the token-encryption key are external; preserve them separately or reconnect providers after recovery.

Browser backup/restore is limited to 24 MB. The desktop **File → Back Up Database** command supports larger downloads. Restore accepts a compatible database from this version. It verifies integrity, schema, relationships and record validation; never executes uploaded SQL/schema. Preview counts and workspace, type **RESTORE**, then confirm replacement. A private safety backup is saved under the database's `backups/` directory. Replacement is transactional and rejects workspace changes since preview. Provider import jobs are cleared after restore. Older-version schema migration through browser restore and encrypted backup files are not implemented.

## Testing

`python3 -m unittest discover -q` includes CSV validation/ownership/idempotency, saved views, website enrichment review/public-network restrictions, stage/inactivity rule deduplication, calendar cache/log ownership and cancellation updates, and real SQLite backup/restore safety tests. Existing mail, auth, record, desktop and productivity tests remain required. Run `node test_email_ui.cjs` and `node test_productivity_ui.cjs` for the established presentation helpers. Live Google consent is a separate integration test.

## Phone numbers

Contact, company and profile phone fields include a country-code selector and format numbers as you type. Set your usual country under **Settings → Account Defaults → Default phone country code**; the initial default is United States (+1). Canada and other supported countries can be selected individually. Enter the area code and optionally an extension such as `ext. 123`. Complete numbers are saved in international format, preserving extensions. Explicit international numbers determine their country. Incomplete numbers and ambiguous input are preserved rather than guessed. Existing records are formatted when saved; no bulk rewrite is performed. CSV imports use the workspace default for national numbers, so include `+country code` for other countries.

Formatting runs locally using the `phonenumbers` metadata package. It does not send numbers to an external lookup service and does not verify that a number is active. Company phone is added without replacing existing custom properties. Source installations must install the updated requirements; desktop builds bundle the metadata.

Deal boards expand to the full available window width on large displays; stage columns remain horizontally scrollable when needed.
