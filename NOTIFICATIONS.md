# Notifications

Open **Notifications** in the top bar to review personal alerts, open the related email/task, or mark alerts as read. The center shows the latest 100 alerts from the last 90 days. **Mark displayed as read** affects those visible entries. Preferences and read status are saved for the signed-in CRM identity, across devices.

## Included alerts

| Alert | When it appears | Requirements |
| --- | --- | --- |
| Email opened | Each recorded open of an accepted tracked email | Workspace tracking enabled when sending, Track opens selected, a connected sender account |
| Incoming email | A newly cached received email, dated after notification preferences were first initialized | A manual or automatic email sync |
| Task reminder | The configured reminder time is reached | An incomplete task assigned to your profile name/email, or an unassigned task, with a reminder selected |

Historical email imports do not create incoming-mail alerts. Sent messages imported from Gmail do not create incoming alerts. Open alerts belong to the sender's authenticated account, even when email activities are shared on CRM records. Rapid pixel retries are already deduplicated by tracking. Open tracking records image loads, which can include privacy tools and scanners.

Task reminder times use the current device's time zone. Completed, rescheduled, reassigned, dismissed or snoozed reminders are filtered from the active center. Use **Task reminder controls** to snooze or dismiss a reminder. Owner names remain assignment labels; profile renames do not rewrite tasks.

## Preferences

Choose **Notifications → Preferences**, or **Configuration → Your Preferences → Notifications**. Email opens, incoming email and task reminders can each be enabled or disabled. Disabling a type hides its alerts without marking them read. Desktop alerts are off by default.

For desktop alerts, select **Show desktop alerts**, press **Enable browser notifications**, grant permission, then save preferences. Both browser/system permission and the CRM preference are required. Only new unread alerts observed after the initial load trigger a desktop alert; returning to the CRM does not replay the entire backlog. Clicking an alert opens its context.

The CRM checks every 30 seconds while open. Browsers and operating systems may delay checks in background windows. There is no closed-app web push, SMS or notification email delivery in this version. Opening a notification does not send mail. Notification preferences do not enable tracking or automatic sync.

## Storage and access

Notification endpoints require the normal authenticated session in hosted mode. Changes require the existing same-origin checks. Server queries scope email alerts and read receipts to the current account; an administrator does not gain access to another user's private alerts. Stored alert data contains a subject and sender/recipient header, timestamps and CRM references, never message bodies, mailbox credentials or tracking tokens. Entries older than 90 days are removed during the owner's next check. Local mode shares the existing local-operator identity until SSO is enabled.

Included in web v0.2.0-beta.5. Existing installations need to deploy the approved release to receive it.
