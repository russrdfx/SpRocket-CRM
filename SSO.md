# OpenID Connect sign-in

Sprocket supports a single configurable OIDC provider and one shared workspace. Admitted users have the same full CRM access. This is not a roles, multi-tenant or production deployment system.

## Configure

1. Create an OIDC web client with your identity provider. Enable authorization code flow, PKCE S256 and `client_secret_basic` token authentication. This version supports RS256-signed ID tokens. Register the exact redirect URI `http://127.0.0.1:8765/auth/callback` for local testing, or your HTTPS origin followed by `/auth/callback` behind a trusted reverse proxy.
2. Install dependencies in a virtual environment:

   ```sh
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

3. Open **Configuration → Security → Single sign-on (SSO)** to save the issuer, client ID, CRM origin and allowed subject IDs. Use **Test provider discovery** to check metadata without activating SSO. Settings are stored in the ignored `data/sso.json` (or `SPROCKET_SSO_CONFIG`). Environment values override saved settings.

   Configure the client secret and administrator subjects through the server environment. You can also configure all settings through environment variables:

   | Variable | Purpose |
   | --- | --- |
   | `OIDC_ISSUER` | Exact HTTPS issuer from provider metadata |
   | `OIDC_CLIENT_ID` | Registered web client ID |
   | `OIDC_CLIENT_SECRET` | Client secret; never commit it |
   | `OIDC_ALLOWED_SUBJECTS` | Comma-separated exact `sub` identifiers permitted access |
   | `OIDC_ADMIN_SUBJECTS` | Comma-separated admitted subject IDs allowed to manage SSO setup after activation |
   | `SPROCKET_ORIGIN` | Browser-facing origin, default `http://127.0.0.1:8765` |

   Obtain subject identifiers from the provider's user directory or administrator. Emails and display names do not grant access. This server does not automatically load `.env` files. Never put credentials in repository files or frontend code.

4. Restart with `.venv/bin/python server.py`, then open the configured origin. A new installation with incomplete SSO configuration fails startup rather than falling back to anonymous mode. Restart after configuration changes.

## Behavior

- No issuer configured: local demo mode, no sign-in. Partial SSO settings are rejected.
- Issuer configured: CRM HTML, JavaScript and all record/settings APIs require an authenticated session. `/api/auth`, login assets and login routes remain public.
- Login uses authorization code flow, PKCE S256, random state, a browser-bound login cookie and nonce. Pending attempts expire after ten minutes and are single-use.
- ID tokens undergo signature, issuer, audience, expiration, issued-at, nonce and authorized-party validation before allowlist admission. Access and refresh tokens are not retained.
- Sessions use random opaque HttpOnly, SameSite=Lax cookies. Secure cookies are used on HTTPS. Plain HTTP is allowed only for local development origins.
- Sessions expire after at most eight hours or the ID token's expiration, whichever comes first. They live in memory; server restart signs everyone out. Writes require an exact same-origin header and JSON content type.
- Sign out revokes the local session. It does not sign out of the identity provider. Provider-wide logout, refresh tokens, user management, roles, persistent sessions and audit history are not implemented.
- The server still binds to loopback. Remote hosting requires separate production hardening and a trusted HTTPS reverse proxy. Do not expose the demo directly.

## Verification

```sh
.venv/bin/python -m unittest discover -p 'test_*.py'
```

Tests use fictional identities and locally generated RSA keys. They cover session revocation and expiry, invalid token claims, browser binding, login replay rejection, startup configuration, anonymous API rejection and cross-origin write protection, alongside the CRM tests. Provider exchanges are mocked; a real provider login remains a required integration check for your deployment.

Protocol references: [OpenID Connect Core](https://www.openid.net/specs/openid-connect-core-1_0.html), [PyJWT API](https://pyjwt.readthedocs.io/en/latest/api.html).
