# Road alternatives, refreshes and sample journey data

## Route candidates and ranking

The planner considers a direct road, eligible operational transfer facilities,
verified weather detours, and up to two additional provider road alternatives.
TomTom requests `maxAlternatives=2` and `alternativeType=anyRoute` with the truck
profile and expected road departure. OSRM requests `alternatives=2` as a fallback;
its car profile does not certify truck restrictions. Providers may return fewer
roads. This is a bounded candidate search, not a proof of the global optimum.

Additional roads pass through the same ETA, calendar, weather, capacity, cost and
deadline engine. Their geometry is also used for fuel and estimated distance-based
cost. A weather exclusion cannot win just by being cheaper or faster. Eligible
on-time options rank first; fastest, lowest transport cost, or transport cost plus
transit hours at EUR 50/hour determines their order. Existing tariffs and model
assumptions still apply; these are planning estimates.

Road alternatives have geometry-based IDs, so selecting and saving one preserves
the chosen road through approval recalculation. Alternative calculations are cached
at the provider; independent candidates are evaluated concurrently. `/api/route`
uses a snapshot of operational data instead of holding the shared state lock while
waiting for remote providers. A result returns its evaluated revision, and the UI
rejects results overtaken by a newer scenario revision.

Google Maps displays wider colored alternative lines, numbered selection labels,
and matching card/legend numbers. The initial view includes all roads. Routine
refreshes and option selection preserve the camera. **Fit route** explicitly fits
the current options again. Transfer options can legitimately share road sections.

## Refresh behavior

The app polls operational state every 15 seconds and refreshes route quotes/live
conditions every two minutes. These are application timers. Background refreshes
keep the current result visible, retain the selected road ID, and avoid clearing
conditions on the same road. Hidden planner pages skip automatic route searches.
Sample previews have no automatic quote refresh.

This change does not add persistent cloud storage. Local records use JSON files;
Vercel restores the existing hosted snapshot into temporary storage. Cloud writes
can still reset or differ between server instances. That is separate from a map
camera/quote refresh.

## Supplied dataset

See `data/journeys/README.md`. Five validated examples load through
**Route planner > Sample journeys**. Weather preview is isolated from shared
shipments, scenarios, approvals and actual outcomes. Relative times are resolved
in Europe/Berlin and weather windows follow the planned departure. Route-fraction
placement uses distance along real returned road geometry. The supplied automated
runner was reviewed but not installed; its accelerated approval/outcome recording
does not belong in normal manager operations.

## Focused validation

- Frontend TypeScript and production build passed.
- Five new regression checks cover provider alternative caching and truck request formatting, ranking and saving/
  approving the chosen road, sample isolation, and Saturday/DST scheduling.
- Existing vehicle-progress checks passed. An existing bounded-wait dispatch check
  fails in both the prior commit and this version because its fixed October 2026
  departure now requires a fresh in-transit position. No stale-position guard was
  weakened to make that dated check pass.
- Local browser checks exercised road selection, a snow example and refresh camera
  preservation. Live results vary with provider availability.
