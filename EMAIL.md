# Personal email integration

SpRocket supports Google / Gmail and Microsoft 365 / Outlook through a shared personal inbox. Open **Inbox** in the main navigation, or **Configuration → Integrations / Inboxes**. Configure each provider independently; either or both can be enabled.

## Implemented

- Authorization-code connection with browser-bound state and PKCE S256.
- Server-side token exchange and refresh, encrypted persisted tokens, and reconnect support.
- Owner-scoped accounts and cached messages when SSO is enabled; CRM activity copies are shared automatically. Ownership includes the OIDC issuer and subject.
- Manual date-range imports: choose the last 7, 30 or 90 days, or inclusive custom dates (UTC), preview the matching message count, then press Import. Provider pages are processed in batches with progress and cancellation between batches. Re-importing does not duplicate CRM email activities. The selected range is saved for the next import; the inbox displays the 200 newest cached messages.
- Plain-text viewing, compose, reply and signatures. Gmail preserves thread ID and reply headers; Microsoft uses Graph's reply endpoint.
- Match contact email addresses and show deals linked to those contacts in either direction.
- Sync automatically logs messages on matching contact/deal timelines, creates missing contacts and creates/links companies by correspondent email domain. Repeated sync does not duplicate contacts, domain companies or message activities. **Log on newly matched records** adds links discovered after sync.
- Follow-up task creation with due date and matched record links. Repeating it returns the existing task.
- Disconnect removes stored tokens and the account's message cache. Synced CRM logs, contacts, companies and follow-up tasks remain.

This version does not run background sync, process webhooks/delta cursors, render HTML, download attachments, edit/delete remote mail, support shared mailboxes, or offer multiple recipients, CC/BCC or rich-text composition. Imports page through all messages in the selected range. Preview jobs expire after one hour or a server restart; preview again to resume an interrupted import without duplicate activities. Provider-accepted send is not proof of final delivery. Microsoft sent-message previews use a local identifier until sync retrieves the provider copy; those may appear twice in the cache.

## Server prerequisites

Install the optional dependencies:

```sh
python3 -m pip install -r requirements.txt
```

Generate an encryption key once and save it in your server's secret environment or secret manager:

```sh
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set these environment variables before starting the server:

```text
MAIL_TOKEN_KEY=<generated Fernet key>
SPROCKET_ORIGIN=http://127.0.0.1:8765
GOOGLE_MAIL_CLIENT_ID=<Google OAuth web client ID>
GOOGLE_MAIL_CLIENT_SECRET=<Google OAuth client secret>
MICROSOFT_MAIL_CLIENT_ID=<Microsoft application client ID>
MICROSOFT_MAIL_CLIENT_SECRET=<Microsoft application client secret value>
```

Set only the client variables for providers you need. Restart after changing configuration. Never commit secrets or the local database. The key must remain stable across restarts; losing it requires restoring it or disconnecting/reconnecting accounts. Back up the database and key separately. Provider credentials are read from the environment and never returned by the API.

`SPROCKET_ORIGIN` must match the browser origin and each registered callback exactly. HTTPS is required outside loopback. The local server still binds only to loopback; this feature does not make the CRM a production deployment.

## Google setup

1. Create a Google Cloud project, enable the Gmail API, and configure its OAuth consent screen.
2. Create a **Web application** OAuth client. Add this authorized redirect URI:
   `http://127.0.0.1:8765/mail/callback/google`
3. Request these scopes: `https://www.googleapis.com/auth/gmail.readonly` and `https://www.googleapis.com/auth/gmail.send`. Add your account as a test user while the OAuth app is in testing.
4. Set the Google client variables above. Open Inbox and choose **Connect Google**, then review and grant provider permissions yourself.
5. Choose **Sync recent mail** after connecting.

Google's mail-reading scopes are restricted. Public distribution may require Google's verification and security assessment process; an individual operator must configure their own OAuth app and follow Google's policies. Testing-mode refresh tokens can expire; reconnect when access expires or is revoked.

Sources: [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server), [Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes), [Gmail send API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send).

## Microsoft setup

1. Register an application in Microsoft Entra. The adapter uses the `common` authority; choose the supported organizational/personal account types you intend to allow.
2. Add a **Web** redirect URI:
   `http://127.0.0.1:8765/mail/callback/microsoft`
3. Add delegated Microsoft Graph permissions **User.Read**, **Mail.Read**, **Mail.Send**, plus **offline_access**. Tenant policy may require administrator consent.
4. Create a client secret; place its **value**, not its ID, in `MICROSOFT_MAIL_CLIENT_SECRET`.
5. Open Inbox, choose **Connect Microsoft**, review and grant permissions yourself, then sync.

Sources: [Microsoft authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow), [Graph permissions](https://learn.microsoft.com/en-us/graph/permissions-reference), [List messages](https://learn.microsoft.com/en-us/graph/api/user-list-messages?view=graph-rest-1.0), [Send mail](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0).

## Privacy and security

Connecting email is independent of CRM SSO. With SSO, inbox access is scoped to the signed-in issuer/subject. In local demo mode there is no authenticated identity: anyone using that local workspace can access its connected inboxes. Switching to SSO does not transfer local-operator mail to a signed-in user; disconnect local accounts before changing modes. Changing SSO issuer likewise does not transfer existing inbox ownership.

Tokens are encrypted using Fernet; cached message text remains in the ignored local SQLite database. CRM record APIs do not expose the personal cache or credentials. Sync and accepted outgoing sends automatically copy messages into shared contact/deal activity timelines. Missing correspondents are created as contacts and linked to domain-based companies. Existing records are reused without overwriting their names or details. Your own connected addresses are excluded from automatic contact creation. Received mail creates the sender; sent mail creates recipients (including Cc). Domain companies are named for the domain and labeled as unverified; consumer providers such as gmail.com also produce domain-based companies. This is a domain association, not verified business enrichment. Tasks contain the subject and matched relationships rather than the message body. Shared CRM records remain accessible to all admitted workspace users under the existing role model.

OAuth state expires after ten minutes, is single-use, bound to the browser cookie and initiating CRM identity, and carries no tokens to the browser. Outbound provider requests use fixed HTTPS hosts and reject redirects. Email writes require same-origin JSON requests. Incoming HTML is displayed only as text or a provider snippet; scripts and remote images are not executed. Callback request URLs are not logged.

Send attempts have a persistent request ID and are never automatically retried. After a network failure or unknown delivery state, check provider Sent mail before composing again. A disabled Send button after an error prevents a casual duplicate; closing/reopening compose creates a new request. The UI does not send email during testing or merely by logging an Email activity.

Disconnect removes local credentials; it does not revoke the provider grant. Revoke app access in your Google account or Microsoft account/tenant settings as well if desired.

## Verification status

Automated tests mock provider responses and cover state/browser/owner checks, PKCE parameters, scopes, token encryption and refresh rotation, private cache isolation, message matching, automatic contact/domain company creation, sync upserts, activity/task deduplication, MIME replies, both sending adapters, redirect rejection and duplicate/uncertain sends. Real Google and Microsoft consent, sync and delivery must be verified using registered apps and consenting test accounts before operational use. No real mailbox has been connected or message sent by the implementation tests.

## Desktop installation

The desktop app uses port 18765 and system-browser authorization. Provider setup, private local configuration and callback URLs are documented in [DESKTOP.md](DESKTOP.md).

New contacts created during import are assigned to the signed-in CRM user. In local mode they are assigned to the connected email address. Existing contact owners are preserved. Connected email addresses and the current signed-in user are available in owner selectors. Click a contact property on its record to edit and Save or Cancel without opening the full edit dialog.
