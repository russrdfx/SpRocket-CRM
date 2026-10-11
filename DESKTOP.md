# SpRocket CRM desktop

The desktop edition packages the existing CRM and Python server inside Electron. Users do not need to install Python or Node. The initial installer targets **Apple Silicon Macs** and is an **ad-hoc signed development build, without Developer ID signing or notarization**. Windows, Intel Mac builds, automatic updates, signing and Apple notarization remain planned.

## Build produced in this workspace

The application bundle and ZIP distribution were built. The DMG attempt was blocked by the execution environment: `hdiutil: create failed - Device not configured`. Use the ZIP now; extract it and move **SpRocket CRM.app** into Applications. The DMG command remains available for a normal Mac development environment. The ZIP uses an ad-hoc development signature and passes strict signature integrity verification. It is not notarized.

## GitHub download

The [v0.1.3 preview release](https://github.com/russrdfx/SpRocket-CRM/releases/tag/v0.1.3) provides `SpRocket-CRM-0.1.3-arm64.zip` and a SHA-256 checksum. This Apple Silicon Mac build uses an ad-hoc development signature and is not notarized. Source pushes do not update release downloads; each package is published separately. Avoid the defective v0.1.0 package.

## Install and use

Download and unzip `SpRocket-CRM-0.1.3-arm64.zip`. Quit any running SpRocket CRM, then move **SpRocket CRM.app** into Applications, replacing the previous copy. Launch the app. The workspace starts empty; existing development data is not included in the installer. macOS may block this development build. For a build you trust, use the approval option in System Settings → Privacy & Security. Public distribution should use a signed and notarized release.

The app starts its own server at `http://127.0.0.1:18765` and stops it on quit. Opening the application again focuses the existing window. If another process occupies that port, startup fails instead of connecting to another server. The browser development server on port 8765 can run separately.

## Data and backups

The Mac data folder is `~/Library/Application Support/sprocket-crm-desktop`. Use **File → Open data folder** to find the actual folder. It contains `sprocket.db`, optional `sso.json`, a private `mail-token.key`, and optional `desktop-config.json`. App upgrades preserve these files. Removing the application does not remove its data. Database contents remain local and are not encrypted at rest; email authorization tokens are encrypted with the separate key.

**File → Back up database…** makes a consistent SQLite snapshot, including records, activity and cached mail. Keep a separate secure copy of `mail-token.key` and configuration if you need to restore connected email accounts. To restore, quit the app, preserve a copy of current data, then replace `sprocket.db` with the backup in the data folder. Restore its corresponding key if retaining email connections. Do not copy a live database file directly.

To migrate a browser installation, quit both servers and copy its database to the desktop data folder before launch. Copy its SSO configuration and existing email encryption key when applicable. Desktop and browser installations otherwise have separate workspaces.

## Email and SSO

Sign-in opens the system browser. Short-lived, single-use handoffs transfer an authenticated SSO session back to the app; normal provider token verification and identity allowlists still apply. Email connection bootstraps the system browser with the current signed-in identity and mailbox binding cookie. Return to the app after approval; the view refreshes on focus. If approval fails, reconnect from the Inbox. Provider credentials and live-provider approval are still required; automated verification uses mocked providers and does not send mail.

Provider callback registrations for desktop:

- SSO: `http://127.0.0.1:18765/auth/callback`
- Google: `http://127.0.0.1:18765/mail/callback/google`
- Microsoft: `http://127.0.0.1:18765/mail/callback/microsoft`

Use the provider application registration appropriate for these loopback callbacks. See [SSO](SSO.md) and [email](EMAIL.md) for required permissions and provider limitations.

For graphical launches, put provider configuration into `desktop-config.json` in the data folder. It accepts string values for `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `OIDC_ALLOWED_SUBJECTS`, `OIDC_ADMIN_SUBJECTS`, `GOOGLE_MAIL_CLIENT_ID`, `GOOGLE_MAIL_CLIENT_SECRET`, `MICROSOFT_MAIL_CLIENT_ID` and `MICROSOFT_MAIL_CLIENT_SECRET`. Restrict this file to your user (`chmod 600`). Restart after changes. The launcher fixes the local origin, database path and token encryption key; these cannot be overridden by the configuration file.

## Build from source

Build on the destination OS and architecture. The current Mac commands produce arm64 output and require an arm64 Python and Node installation. From the repository root:

```sh
python3 -m venv .desktop-venv
source .desktop-venv/bin/activate
pip install -r requirements.txt -r desktop/requirements-build.txt
python desktop/scripts/build_backend.py
cd desktop
npm ci
npm run build:mac
# ZIP alternative when disk-image creation is unavailable:
npm run build:mac:zip
```

Output is in `desktop/dist/`. The Python executable and static assets are embedded through `extraResources`; databases, secrets and development dependencies are excluded. The full-color supplied SpRocket application icon is used in the bundle and installer. Build cache and output are ignored by Git.

For development, install Python requirements and desktop dependencies, then run `SPROCKET_PYTHON=/absolute/path/to/venv/bin/python npm start` from `desktop/`. The wrapper uses its separate desktop workspace even during development.

## Verification and release work

Run `python -m unittest discover -v` from the repository root and `node --check desktop/main.cjs`. Check packaged startup, static assets, health ownership, backup integrity and shutdown in addition to tests. Desktop bridge tests cover launcher authentication, expiry, replay protection and a mocked SSO browser callback that transfers the verified cookie only to the launcher. Existing tests cover provider verification, mailbox ownership and CRM operations.

A public release still needs Developer ID signing, notarization, a clean-machine install check, live Google/Microsoft/OIDC callback verification and a release/update policy. Windows needs a Windows-built Python backend and an installer target, then platform-specific tests. An unsigned development installer should not be presented as a production release.

For an isolated test workspace, set `SPROCKET_DESKTOP_DATA_DIR` to an absolute directory before launching the app. It overrides Electron's normal data folder. The database remains empty unless you add or migrate data.

The locked packaging toolchain currently reports eight moderate development dependency audit findings associated with the builder's download tooling. These dependencies are excluded from the installed application. Review available upstream fixes before public release; do not force a downgrade that introduces more severe dependency findings.

Verified for the initial ZIP: 52 automated Python tests, launcher syntax, packaged backend startup and static assets, launcher-only health checks, live SQLite backup integrity, visible packaged CRM launch, server shutdown after app quit, ZIP integrity, and absence of databases or private keys from the archive. Live provider sign-in and clean-machine installation remain unverified.

## v0.1.1 packaging correction

The v0.1.0 ZIP failed macOS signature integrity verification after download. It must not be treated as an installable release. The v0.1.1 build uses an explicit ad-hoc development signature (`identity: "-"`) instead of skipping signing. This repairs integrity metadata without claiming a verified developer identity. Developer ID signing and notarization remain required for normal public distribution. Gatekeeper may still block this development build; do not remove quarantine attributes or disable Gatekeeper as a packaging workaround.

Before publishing any new Mac artifact, require `codesign --verify --deep --strict --verbose=2` on the bundle and again on a fresh extraction of its ZIP. This checks integrity, not notarization or clean-machine installability.

The packaging hook removes only Finder information and resource-fork metadata from generated bundles before signing, because these attributes cause code-signature creation to fail. It preserves quarantine and other security attributes. ZIP builds run fresh-extraction signature verification automatically.

Cloud-backed folders can restore Finder metadata during signing. If this occurs, build into an ordinary local temporary folder using `--config.directories.output=/private/tmp/sprocket-build` and verify a ZIP extracted into a temporary local folder. Copy the finished ZIP to its distribution location after verification.

v0.1.1 verification: strict signature integrity passed for the built app and a fresh ZIP extraction; the corrected application displayed the CRM and the test instance was closed. Developer ID and notarization are still absent, and Gatekeeper approval from a browser-downloaded copy remains unverified.

## 0.1.2

Adds date-range email import previews and batched imports, automatic ownership for newly imported contacts, owner choices for the signed-in user and connected inbox addresses, and direct contact property editing. Existing CRM data and assigned contact owners are retained. Published as a GitHub preview release for Apple Silicon Macs. All 55 tests pass; the packaged backend backup smoke test and fresh ZIP signature verification pass. Developer ID signing and notarization are not included.

## v0.1.3

Adds client-style email activity headers and bodies, sandboxed Google HTML email, compact dashboard previews, and a Contacts Lead stage column using Lifecycle stage. New imported contacts start at Lead. Existing imports can be re-imported to enrich formatted content without duplicate activities. All 57 backend tests and the email presentation checks pass. Published as an Apple Silicon Mac preview release, with an ad-hoc development signature and no Apple notarization.

## v0.1.4 local build

Adds editable CRM profiles (display name, job title and phone), inherits Gmail Send mail as display names using existing permissions, provides an optional per-inbox sender-name override and identity check, and logs the selected sender name. Existing account addresses and access roles remain fixed. All 60 backend tests and email presentation checks pass. These changes are included in the v0.1.5 source update; the v0.1.4 package was not published.

## v0.1.5

Profile editing is available from both the top-right menu and Configuration → General → Profile. Adds foreground automatic email checks, reviewed contact/company cleanup, task completion and reminders, and shared rich-text email/signature editing. This desktop preview includes the v0.1.4 profile/sender changes and is published as an Apple Silicon Mac ZIP on GitHub. Existing application data remains in the same application-support folder. The build uses ad-hoc signing and is not notarized.

Validation: all 69 backend tests pass, including pagination/batch/deduplication checks. Email presentation and reminder timing checks passed. Isolated browser checks verified task completion, merge preview, signature persistence and bold composition. The freshly extracted ZIP passes strict deep signature verification, and its packaged backend serves state, cleanup, reminders and the productivity script. Real-provider send and operating-system notification delivery still need user testing.
