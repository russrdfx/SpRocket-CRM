# Guided company setup

Included in web v0.2.0-beta.6.

After initial company deployment and administrator sign-in, **Home** offers a compact setup reminder. Choose **Continue setup**, or open **Configuration → Getting started**. Existing installations can use the same guide; company setup and database creation are never repeated.

Five essential steps cover:

1. Review workspace name, currency and default phone country.
2. Review the editable sales pipeline, probabilities and stage outcomes.
3. Review record fields and custom properties.
4. Create or import the first contact, company or deal.
5. Confirm a tested backup and recovery process, including retaining the encryption key.

Workspace, pipeline and field steps require an explicit review acknowledgement. The first-record step is derived from existing data. The backup checkbox is the administrator's acknowledgement: the CRM cannot inspect hosting backup policies or certify recovery. Opening backup guidance does not create a backup.

Email, Calendar and team invitations are optional. Existing personal account connections are detected automatically. A pending team invitation or another active user completes the team step in the private web edition. Optional steps may be skipped and re-enabled. Provider configuration, OAuth consent, invitations and imports still use their existing screens; the guide performs none of these actions automatically.

Progress and Home reminder visibility are saved for the signed-in administrator. Hide the reminder without losing progress, then restore it from Getting started. The Home reminder also disappears when all essentials are complete. If a required pipeline is removed later, its step becomes incomplete again.

The API and UI restrict the company guide to administrators. Progress changes require the normal authenticated session and same-origin checks. Saving progress never changes records or workspace configuration, enables integrations, sends invitations, or changes hosting plans.

Local demo mode supports the guide for the local operator; hosted team invitations are shown as unavailable there. The guide does not replace the deployment instructions in GETTING_STARTED.md or WEB.md.
