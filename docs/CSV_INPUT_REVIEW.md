# CSV input review — 17 November 2026

All seven supplied `(1).csv` downloads contain the same parsed records, in the
same order, as `data/raw/*.csv`. Byte differences do not introduce new data.
The existing files are retained to avoid duplicating history or changing working
inputs while the route improvements are in progress.

| File | Records | Existing use |
| --- | ---: | --- |
| disposition.csv | 19,980 | Lane history, utilisation, spillover, allocated cost/fuel benchmarks and a handling-time proxy |
| relationen.csv | 30 | Branches, lane distances, trailer tariffs, capacity and utilisation targets |
| kalender.csv | 1,050 | Supplied Baden-Württemberg holiday/calendar records |
| stoerungen.csv | 7 | Historical disruption context in network intelligence |
| kundenstamm.csv | 820 | Available customer master data; not currently joined to individual shipments |
| kundensignale.csv | 72 | Historical customer demand notices; no customer-to-lane mapping supplied |
| vertriebsereignisse.csv | 188 | Historical customer/sales events; no road closure or travel-time measurements |

The three customer files can support a later customer-priority and demand-planning
feature. They do not establish a road delay or a route's driving time. The priority
flag named `top30` is set on **31** records; do not hard-code a total of 30.
Every demand-notice customer ID resolves to a customer-master record.

## Date coverage and limits

- Daily operations: 2 January 2024 to 31 August 2026.
- Calendar: 1 January 2024 to 15 November 2026. Absence of a later calendar row does
  not establish that a future date has no holiday or restriction.
- Latest customer demand notice ends 16 October 2026; these notices are historical
  on the review date, not current operational alerts.
- Sales events end 31 July 2026; historical disruptions end 23 April 2026.
- Several supplied text fields contain replacement characters. No names or event
  descriptions were guessed or silently rewritten.

No CSV was imported a second time, no historical event was activated as live
traffic/weather, and the supplied journey replay patch was not executed during this
UI/data review.
