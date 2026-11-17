# Sample planning journeys

`journeys.json` is the five-scenario dataset supplied with the journey-runner patch:
clear delivery, snow diversion, a Saturday departure, a storm front, and a rain
trade-off. It is suitable for scenario demonstrations, not as historical arrivals,
GPS telemetry, measured costs, or machine-learning training data.

In **Route planner → Sample journeys**, select an example, click **Load sample**,
then **Find best routes**. Select **Preview weather impact** and calculate again
to compare its weather scenario. Exit the sample to plan a normal shipment.

The API validates the dataset and exposes `/api/journey-examples`. Local departure
times use Europe/Berlin, including daylight-saving changes. Weather is positioned
by distance along returned road geometry, or at the supplied fixed coordinates.
Its effective window follows the example's planned departure, including future
Saturday examples. These are planning previews; `script` and injection-progress
fields remain available as source material for a future interactive replay.

Each preview uses a copy of operational state with its own weather zones. It does
not create shipments, change shared scenarios, approve decisions, or record actual
outcomes. Live road/forecast providers and existing cost, calendar, capacity and
ranking logic are used. Results depend on provider availability and current inputs;
the dataset's written expectations are not proof of a particular measured result.

The supplied runner was not installed: it automatically approves decisions and
records accelerated simulated arrivals and estimated costs as actual outcomes.
Those actions need a dedicated simulation lifecycle before they belong in the app.
