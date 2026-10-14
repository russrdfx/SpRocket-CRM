# Deal forecasting

Included in web v0.2.0-beta.6.

Open **More tools → Sales → Forecast**, or use **Open deal forecast** in Reports. Forecast can be pinned to the sidebar.

Choose this month, this quarter, next quarter, this year or custom inclusive close dates. Filter by deal pipeline and owner, including unassigned deals. Owner-name and known email aliases are treated as the same person. Filters remain selected during this browser session, but are not saved as a personal report.

- **Open pipeline:** entered amounts of open deals with close dates in the selected period.
- **Weighted open:** open amount multiplied by configured stage probability.
- **Closed won:** entered amounts of won deals with close dates in the period.
- **Projected total:** closed won plus weighted open.
- **Closed lost:** shown separately and excluded from projected total.

Monthly and stage breakdowns use the same filters. These are live estimates, not accounting revenue, a historical snapshot, a quota or a guaranteed outcome. Values use the workspace currency; there is no currency conversion. Closed-won grouping uses the entered close date, not the date a stage was changed.

**Needs attention** includes open deals with past close dates and deals with missing/invalid close dates, missing amounts, or missing pipelines/stages. This view intentionally includes records outside the selected close-date period, so missing and overdue dates are discoverable. Owner/pipeline filters still apply. Zero is a valid entered amount. Missing amounts contribute no value and are marked for review. Click a deal to open its details and edit it separately.

## Stage outcomes

In **Configuration → Pipelines → Edit pipeline & stages**, each stage now has **Open**, **Won** or **Lost** in addition to its probability. This preserves correct behavior when stages are renamed or use different terminology. The Home sales view uses the same classification.

Existing stages are unchanged until saved. Without an explicit outcome, the legacy labels Won/Closed Won and Lost/Closed Lost supply the default; other labels are open. Neither 0% nor 100% probability alone closes a deal. Saving a pipeline preserves its stage IDs and existing record associations. Outcome values are validated by the server.

Forecast viewing does not change deals. Stage edits still require the existing administrator permissions in hosted workspaces.
