# Productivity guide

## Email

1. Connect an inbox and choose **Import email**.
2. Choose a time frame, preview the count and import. Keep the automatic-sync checkbox selected to check for new mail while the app is open.
3. Use **Pause automatic sync** / **Enable automatic sync** at any time. Pausing preserves the checkpoint for catch-up when resumed.
4. Use **Sender & signature** to choose plain text or rich text / HTML. Add formatting, links or a small local logo. Save and compose a test message to an address you control.
5. Confirm sender name, formatting, inline logo and reply threading in the actual recipient's client. Both Google and Microsoft require real-account checks.

Automatic checks continue across CRM pages. They do not run with the app closed. Initial import selection remains separate from catch-up checks. Errors appear in inbox status and checks retry without advancing the failed checkpoint. A large backlog takes several batches.

## Cleanup

Open **Data cleanup** in the navigation (also **More → Data Management → Data Quality**). Duplicate groups use exact case-insensitive contact emails or normalized company domains; names alone are not automatically merged. Choose **Review merge**, select the primary record, review field differences and confirm. The primary keeps populated fields; missing values, relationships and activities move over. Email activities are deduplicated by cached message ID. All changes happen in one database transaction. The secondary is removed; there is no merge undo. Back up the database before a large cleanup.

Imported records and existing personal-domain companies are listed for review. New email imports exclude common personal domains from company creation. The domain list is conservative and can be extended in `crm_tools.py`; review unknown domains manually. Existing contacts/companies are not deleted automatically.

## Tasks and reminders

Create/edit tasks with a due date, local due time, reminder preference and optional repeat preference. The task list sorts by due date and filters open/completed work. **Complete** marks a one-off task completed. For a daily, weekly or monthly task it records completion and moves the same task to the next future date; overdue occurrences are skipped. Monthly dates clamp to the last valid day. Simultaneous completion attempts against a changed task are rejected.

**Reminders** in the top bar shows due reminders for your profile/identity or connected email owner labels, plus unassigned tasks. Due time defaults to 09:00 if omitted. Snooze hides an occurrence for 15 minutes; dismiss hides that occurrence. Changing its date/time/reminder preference makes a new occurrence. Reminder state is private to the sign-in identity (or shared local operator in demo mode). Workspace records remain shared.

Desktop notifications are optional and require permission from **Notifications → Preferences → Enable browser notifications**. Enable **Show desktop alerts** and save preferences as well. Alerts are shown once per task occurrence per browser profile and identity. In-app reminders work without permission. All reminder checks require the CRM window to be open; minimized/background windows may be throttled by the browser or operating system. Owner names are assignment labels, so renaming a profile does not rewrite existing task owners.

## Validation

Run `python3 -m unittest discover` and `node test_email_ui.cjs` / `node test_productivity_ui.cjs` from the repository. Productivity tests cover merge links/fields/activity/log deduplication, invalid merges, personal domains, reminder isolation, completion/recurrence/stale updates, automatic-sync controls/checkpoint retry/range preservation, and provider HTML delivery formats. Browser checks use a separate sample database; never merge or send mail in a user's live workspace as an implementation test.

## Your profile

Open **Profile & preferences** in the top-right menu, or **Configuration → General → Profile**, to edit display name, job title and phone. Both paths use the same saved profile. Calendar, enrichment, CSV imports, saved views and additional automation discussed for the next phase are not included in this source update.

## Focused task desk and email templates

The current local development adds My/Team/Unassigned tasks, overdue/today/upcoming views, context-linked follow-up scheduling, rescheduling with stale-edit protection, and personal/shared email templates. See [Follow-ups and templates](FOLLOWUPS.md). Reminder delivery now uses the personal [notification center](NOTIFICATIONS.md), with the existing snooze/dismiss controls.
