# Sales insights

Open **Reports → Open sales insights** or **More tools → Sales → Sales Analytics**. The page shows current open/won/lost counts, current win share, time tracked in each current stage, closed-lost reasons and up to 90 daily snapshot rows.

Win share is won divided by won plus lost among currently stored deals. It is not a historical cohort conversion funnel. Outcomes follow explicit pipeline Open/Won/Lost settings, with legacy Won/Lost-name fallback. No probability alone closes a deal. Add **Closed lost reason** in the deal editor; blank reasons remain visible as Not recorded.

Stage observation starts with this update. Existing deals receive a baseline at first observation, not their old updated/creation time. Saving stage changes or applying reviewed CSV deal updates records the transition. Changing unrelated fields leaves stage time intact. Earlier stage history is unavailable and is not inferred.

The first observation per UTC day stores aggregate outcome counts, currency and weighted open value across all close dates. Enabled background jobs capture observations; visiting this report also captures an observation when today's snapshot is absent. Days without a running worker or report visit have no snapshot. Snapshots retain their captured currency and values, even if deals or settings change later. This is an observed pipeline trend, not accounting revenue, a date-window forecast or a complete funnel report. Deleted deals are excluded from current summaries; prior aggregate snapshots remain.
