# Google Calendar

Open **Settings → Calendar**, or **More → Sales → Calendar**. Calendar is an independent read-only Google connection; connecting Gmail does not grant calendar access.

## Administrator setup

1. In the Google Cloud project used for email, enable **Google Calendar API**.
2. Use the existing web OAuth client configured through `GOOGLE_MAIL_CLIENT_ID` and `GOOGLE_MAIL_CLIENT_SECRET`. Calendar tokens use the same `MAIL_TOKEN_KEY` encryption key but are stored separately from mail tokens.
3. Add the authorized redirect URI `http://127.0.0.1:18765/calendar/callback/google` for the desktop app. For a server, use `${SPROCKET_ORIGIN}/calendar/callback/google`.
4. Add the read-only `https://www.googleapis.com/auth/calendar.events.readonly` scope to the consent screen. Calendar also requests OpenID/email identity scopes. Add intended Google test users while the OAuth app is in testing.
5. Restart the CRM after changing server credentials. Press **Connect Google Calendar**, and complete Google's permission screen yourself.

## Usage and privacy

Choose a start and end date (up to one year), then sync. All result pages are processed in batches of 100 events. The primary calendar is supported, including expanded recurring-event instances. Cached events are private to the sign-in identity; the local operator shares a single identity when SSO is disabled.

Choose **Review CRM logging** on an event. The confirmation lists matching contact emails and associated deals. Logging writes a shared Meeting activity to those records. Calendar never creates contacts automatically. Private events also require this explicit review. Repeat logging does not create duplicates. Subsequent sync updates already-logged meetings and retains cancelled status in their history.

Disconnect removes the private cache and encrypted calendar token, preserving previously shared meeting history. The account email and logging identifiers remain so reconnecting can retain meeting deduplication. Revoke access separately in your Google account if desired. Calendar writeback, booking links, additional calendars, background sync and Microsoft Calendar are future work.

Implementation follows [Google's Events list API](https://developers.google.com/workspace/calendar/api/v3/reference/events/list) and [Google account identity documentation](https://developers.google.com/identity/openid-connect/openid-connect). Provider responses are mocked in automated tests; live consent and calendar sync remain a user integration test.
