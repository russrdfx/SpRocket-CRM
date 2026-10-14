# Email open tracking: research and proposed implementation

Research date: October 13, 2026. The first release has now been included in web v0.2.0-beta.4. See [the user guide](EMAIL_TRACKING.md). Workspace tracking remains off by default.

## Findings from other CRMs

| Product | Behavior to consider |
| --- | --- |
| HubSpot | Adds a one-pixel image before sending, displays engagement notifications and handles suspected automated interactions. Image blocking and multiple recipients make attribution incomplete. |
| Pipedrive | Default settings plus a per-message control; tracking in inbox and linked record details. External Sent-folder viewing can cause false opens. |
| Zoho CRM | Email Insights surfaces engagement status and analytics; tracking depends on recipient image loading. |

Official sources:
- [HubSpot tracking mechanics and limitations](https://knowledge.hubspot.com/connected-email/understand-hubspot-sales-email-open-and-click-tracking)
- [Pipedrive email tracking](https://support.pipedrive.com/en/article/email-tracking)
- [Zoho Email Insights](https://help.zoho.com/portal/en/kb/crm/connect-with-customers/email/reports-and-analytics/articles/email-insights-overview)

Apple Mail Privacy Protection downloads remote content in the background, independent of whether the recipient engages. Gmail mediates image loading and allows recipients to block images. Consequently, pixel requests are signals, not proof of reading, identity or location. Counting requests cannot reliably count people or reading sessions.

- [Apple's explanation](https://www.apple.com/sg/legal/privacy/data/en/mail-privacy-protection/)
- [Gmail image behavior](https://support.google.com/mail/answer/145919)

## Fit with SpRocket

The current send adapter already assembles multipart text/HTML messages for Gmail and Microsoft, has persistent send-attempt IDs, and logs sent messages onto CRM records. This is a suitable insertion point for a tracking image. Keep the plain-text alternative unchanged and preserve the existing no-retry policy.

The Gmail message API exposes mailbox messages and labels, without a general recipient-read status field. Therefore, our sync cannot infer recipient opens from the sender's message being marked read. Tracking must be inserted before delivery. Gmail-composed emails and historical imported messages remain untracked until a separate Gmail integration can insert tracking at composition time.

- [Gmail message resource](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages)

## Recommended first release

1. **Hosted web version first.** Use the installation's stable public HTTPS domain. A standalone desktop app's localhost address is unreachable to recipients. No central SpRocket domain or third-party tracking service is required.
2. **Explicit controls.** Administrator enables tracking capability; default off. Users choose tracking per message and may set an inbox default. Respect a contact-level tracking exclusion. Explain what is collected and allow administrators to disable future collection for outstanding messages.
3. **Minimal collection.** Store message association and first/last image-request timestamps. Use opaque, unguessable expiring tokens without email addresses or names in the URL. Do not persist recipient IPs, location or browser fingerprints in application data. Document that hosting access logs may independently record requests.
4. **Narrow public endpoint.** An unauthenticated route returns only a transparent image. It exposes no CRM data. All settings, reports and event details retain normal authentication and workspace visibility. Handle unknown/expired tokens identically, use cache controls and bounded storage, and ignore HEAD probes. Avoid making access to the authenticated app public.
5. **Honest status.** Show “Tracking off,” “Not opened yet,” and “Opened N times,” with a clickable list of timestamps and relative ages in sent-mail details and contact/deal email activity. Show timestamps and a brief explanation of proxy/preload limitations; Counts are image-load signals, explained in a small tooltip rather than the primary label. Keep confirmed replies separate.
6. **Avoid self-triggering.** Remove our tracking pixel from CRM cached previews, signatures, quoted replies and forwards composed in the CRM. Opening the message in Gmail Sent can still trigger a request; disclose this limitation rather than promise perfect filtering.
7. **Safe send association.** Create a token after reserving the existing send-attempt ID and before provider delivery. Activate accepted sends without automatically retrying failures. Account for early image requests and uncertain delivery outcomes; do not record an image signal as proof of delivery.
8. **No automatic follow-up from opens initially.** Proxy loading is too ambiguous to drive outreach. Consider reply indicators and optional link tracking as subsequent work, with scanner limitations made clear.

## Hosting implications

An always-available service is preferable. Render free web services spin down after inactivity and take time to restart on a request; a recipient's image request might time out during startup. This can cause missing signals. A tracking endpoint on a stable paid web instance avoids that particular cold-start risk but cannot remove email-client limitations.

- [Render free-service behavior](https://render.com/docs/free)

## Validation before release

Use controlled test sends and a disposable database: opt-in/off cases, endpoint authorization boundaries, token expiry and disabled collection, send-attempt idempotency, HTML/plain-text alternatives, forwarded/quoted pixel stripping, stale-token behavior, concurrent image requests and workspace visibility. Verify real Gmail image loading and Apple privacy behavior with consenting test inboxes. No actual email should be sent during automated tests.

The existing deployment can support this design. Complexity is moderate: collecting an image request is straightforward; safe message association, private previews, honest status and reliable hosting are the main work.
