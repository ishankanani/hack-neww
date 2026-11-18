# Transport calendar and driver-time planning

The regional calendar and driver hour model were developed on
`codex/calendar-driver-rules-2026-11-17` and integrated with the current planner.
Official references are linked below.

## User-visible changes

- The route planner has a month calendar, federal-state selector, trailer flag,
  and optional company Sunday hold. Selecting a date updates departure. Existing
  deadline validation still prevents a departure after the delivery deadline.
- Sundays and applicable holiday truck bans are red. A public holiday without a
  StVO holiday truck ban is blue. Dates are generated beyond the old CSV coverage.
- Route comparison includes a calendar of journey dates and the actual planned
  restrictions, breaks and rests. These stops change ETA and therefore deadline
  feasibility and time-based ranking. They do not add duplicate transport charges.
- Rules saved with a journey survive manager hub changes and recalculation.
  Journeys saved without planning rules continue to use the legacy model, so
  reopening an older approved itinerary does not change its assumptions.

## Implemented planning model

- StVO Sunday/holiday bans use 00:00–22:00 Europe/Berlin. The planner defaults
  to the existing company hold from Saturday 15:00 through Monday 05:00.
  Disable that setting to compare under the statutory calendar alone.
- The freight-ban applicability test uses gross weight above 7.5 tonnes or an
  attached trailer. No special exemption is automatically assumed.
- Public holidays are distinguished from the holidays enumerated by StVO §30(4).
  For example, Epiphany is a public holiday in BW but is not itself a StVO holiday
  truck-ban date. State-specific Corpus Christi/Reformation/All Saints bans differ.
- One clock spans all legs: at most 4.5 hours driving before a 45-minute break,
  a conservative 9-hour daily driving ceiling, and regular 11-hour daily rest.
  No 10-hour extension, reduced daily rest, or split-break concession is assumed.
- Calendar midnight and intermediate handling do not reset the driving clock.
  Daily/weekly rest and 56-hour weekly / 90-hour fortnightly driving ceilings are
  represented. Regular weekly rest is 45 hours; available parked restriction
  time can contain prospectively assigned off-duty rest, without adding it twice.
- Schedule eligibility uses the selected weekend policy. The planner rejects a
  scheduled departure when its updated route cannot clear the weekend window.

## Boundaries that must remain visible

This is a prospective route-time model, not a tachograph or legal-compliance
certificate. It starts with one fully rested driver and zero earlier driving.
In-transit replanning does not import an actual driver's tachograph balances.
Known handling is not credited as a driving break. General working-time breaks,
night-work rules and averaged working-time limits require a duty-roster model;
they are not certified by this driving-time calculation.

Regional holiday scope is selected manually and applied conservatively to the
whole journey. The planner does not determine exact federal-state boundary
crossings or apply bans only to the affected road segments. Multi-state journeys
need review of all states crossed. Municipal holidays and temporary exemptions
are not inferred.

July/August Saturdays are flagged for review: the additional 07:00–20:00
Ferienreiseverordnung bans affect specified roads, not every German road. Road
eligibility is not automatically certified. Regular weekly rest requires suitable
accommodation outside the vehicle; actual rest/parking locations are unverified.

## Evidence

- 23 focused backend checks passed: new calendar/driver cases plus existing
  manager-route and alternative-route checks.
- Production frontend build passed.
- Browser preview: choosing 18 November updated departure, a real route calculation
  exposed the planned driver stops, and December displayed both Christmas bans.
- Isolated preview: `http://127.0.0.1:5181/`, local API port 8008, local preview store.
  It uses no production database or production API credentials.

## Official references

- [StVO §30](https://www.gesetze-im-internet.de/stvo_2013/__30.html): commercial freight
  Sunday/holiday bans, applicability, listed holidays and exceptions.
- [EU Commission: driving and rest periods](https://transport.ec.europa.eu/transport-modes/road/social-provisions/driving-time-and-rest-periods_en):
  driving ceilings, breaks, daily and weekly rest.
- [EU: road transport workers](https://europa.eu/youreurope/business/hiring-managing-staff/transport-sector-workers/road-transportation-workers/index_en.htm):
  separate working-time duties and the need for working-time records.
- [Ferienreiseverordnung §1](https://www.gesetze-im-internet.de/ferienreisev_1985/__1.html):
  additional summer Saturday road restrictions.
