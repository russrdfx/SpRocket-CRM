# Team access and recovery

Web administrators manage users under **Configuration → Users & Teams**. Members can use shared records; administrators also manage workspace settings and access. Deactivation preserves CRM records and account history, ends current sessions and skips that user's background mail/calendar work. Reactivation requires a fresh sign-in. Role changes end current sessions too.

Your own role/active status cannot be changed here. Ask another administrator; the server serializes access changes and protects the last active administrator. User removal is intentionally not included.

Pending invitations can be revoked or replaced. Replacement invalidates the previous link. Links expire after 24 hours. No invitation email is sent automatically.

After independently verifying the person's identity, an administrator can create a **single-use recovery link**, valid for 30 minutes. Share it privately with that person. It is bound to their workspace email. They enter their own new password; using it ends all existing sessions and consumes all their recovery links. Deactivation or another access change invalidates recovery links. Linked Google identities and personal provider connections remain intact. Self-service emailed password recovery is not included.

The last 100 account access events are visible to administrators. Audit events contain actor, action, target email and time; never passwords, invitation URLs, recovery tokens or provider credentials. This is an account access log, not a full record-change audit.
