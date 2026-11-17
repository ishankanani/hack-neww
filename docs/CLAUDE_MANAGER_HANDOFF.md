# Continue the manager control-room checkpoint

Repository: https://github.com/patelpalash/final-hackathon-project

Checkpoint branch: `codex/manager-control-room-2026-11-17`

Local project: `C:\Users\acer\Documents\ChatGPT\hackathon project\Dachser Company Project 30-09 Final`

The user originally stopped implementation and requested this handoff. Claude's
acceptance commits have since been reviewed and merged into the checkpoint.
The local follow-up below records the subsequent fixes and release checks.

## Local follow-up, 17 Nov 2026 (Codex)

- Confirmed the canonical website was still serving main `7ea0a89`; the manager
  checkpoint only had preview deployments. Publishing this source to main is
  required for the public website to show the rebuilt control room and Postgres.
- Each saved home journey now has its own Review button. An explicit review
  request opens that ID, including repeated visits to the same journey, after
  any ongoing manager operation finishes. Opening a queue item shows its saved
  itinerary; Recalculate is an explicit action.
- Manager forms disable edits during a request. Changes to hubs/departure are
  marked as uncalculated and block approval until the new connection is evaluated.
  Corrected the initial Würzburg fallback, explained direct manager connections,
  and reset the old affected-road overlay when changing the selected road.
- Real browser/local backend/Neon/OSRM/Google Maps workflow: selected the Chemnitz
  alternative for Würzburg to Dresden, saved `SHP-136D0F`, and opened that exact
  journey with the same alternative selected in the control room. Added Nürnberg,
  moved it ahead of Chemnitz and calculated the requested sequence. The saved
  itinerary remained unchanged until approval. Approval changed the stored route,
  showed success, closed the review and moved the journey into Active.
- The unwanted driver-update link and Vehicle progress panel are absent. Planned,
  Review required and Active queues and saved/proposed metrics were inspected.
- Focused manager/alternative/progress checks: 13 passed. Frontend production
  build passed. No broad test suite was run.
- The earlier datetime fill issue reproduced in the in-app automation: the DOM
  value changed but React retained the prior date after blur. This is not evidence
  of a manual input bug; the form's own future defaults were used for proposals.

## User requirements

1. A selected route saved on the home planner must immediately appear in the
   manager control room and survive refreshes/server changes.
2. Managers need to choose and reorder intermediate hubs, including Würzburg,
   calculate their requested connection, select an alternative and approve it.
   When a connection cannot be used, show the reason and alternative arrival,
   journey time, distance, fuel and transport cost. Approved plans must stay in
   effect until a new proposal is approved.
3. Show only the selected road on the home map. Selecting another route in the
   side menu switches that road. Avoid a second alternative/old-road overlay by
   default. Preserve weather simulation and route selection.
4. Remove the control-room driver-update link and Vehicle progress panel. Present
   Planned, Review required and Active journeys clearly, with an attractive,
   compact saved-versus-proposed comparison.

## Implemented in this checkpoint

- App/Planner hand off the full saved shipment and trigger a control-room refresh.
  The queue opens the just-saved itinerary without immediately replacing the
  chosen road with a different recommended route. API responses use no-store.
- `ManagerRoutes.tsx`: existing-shipment hub editor and new manager journey form;
  ordered stops, add/remove/reorder, connection calculation and saving for review.
- `POST /api/shipments/{id}/route-proposal`: stores a pending manager request and
  returns evaluated requested connections plus other options. New route requests
  also support `via_hubs`. Custom saved paths are included during recalculation.
- Unavailable geometry/hubs, weather conflicts, capacity and missed deadlines have
  explicit reasons. A non-feasible connection cannot be approved. Active-vehicle
  changes still require a fresh position; removing its UI did not remove that guard.
- A rebuilt control room, status filters, manager decision form and a five-metric
  saved-versus-proposed comparison. The two unwanted sections are removed.
- Google and backup maps have a `showAlternatives` option. RouteCompare disables
  it and starts the old affected-road comparison hidden.
- A real Neon Postgres resource, **dachser-transit-state**, Free plan, Frankfurt,
  was provisioned and connected to this Vercel project's **production** environment.
  `DATABASE_URL` is configured there. No paid plan was selected.
- `backend/app/persistence.py` stores compressed JSON documents in Postgres table
  `dachser_state`, caches document versions and serializes state-changing requests
  with a transaction advisory lock. Shipment and operational changes commit
  together. Failed requests roll back; unavailable storage returns an error rather
  than a false save success. Local JSON remains the fallback without DATABASE_URL.
- Existing local data (14 journeys) was initialized into Postgres. Existing demo
  operational records migrate from their local files when first accessed.

## Verification already performed

- A frontend production build passed during implementation; a later TypeScript
  check also passed. Some small edits followed, so run one final build.
- `backend/test_manager_routes.py` and `backend/test_route_alternatives.py`:
  **8 passed**. These cover custom Würzburg connections, approval preserving the
  requested path, unavailable hubs/alternatives, duplicate stops and road choices.
- A live Postgres save/read and transaction rollback check passed using a temporary
  test document, which was removed afterward.
- Local `/api/network` reports `storage: postgres`; `/api/shipments` returned 200
  with 14 journeys after migrating demo records.
- Browser testing reached a home-page Würzburg route calculation. It did NOT
  finish the save → manager → custom-route workflow before the user stopped work.
  A datetime-local fill through the browser tool did not retain the requested
  date. Check whether this is an input issue or automation behavior.

## Acceptance session, 17 Nov 2026 (Claude, cloud sandbox)

Run against a local Postgres 16 (not Neon: the production `DATABASE_URL` was not
available or needed), two backend instances sharing that database, and the Vite
frontend in Chromium. OSRM and map tiles are blocked in that sandbox, so routing
used a local stub serving `data/demo_roads.json` geometry, and the map ran in its
offline fallback renderer. Four commits on top of `3c23a72`:

- `833c928` **Postgres adapter.** psycopg skips the commit silently when the
  connection is already closed, so a request could report a save that never
  happened: `session()` now commits explicitly. A failure at commit time left a
  phantom version in the cache, so the worker could keep serving its own
  uncommitted data after another instance wrote: the cache now clears on any
  storage error. Map tiles and `/api/health` no longer reload shared state (one
  database connection and global lock per tile; an outage blanked the map).
- `2f771c2` **Control room after a save.** Saving on the planner and opening the
  control room hung on "Loading journey..." with everything disabled (StrictMode
  remount cancelled the auto-open review and `busy` never cleared). Fixed, and
  saved journeys are pinned so a stale or pre-save queue response cannot hide them.
- `49b3fd0` **Manager routing.** New manager journeys showed no requested-connection
  explanation at all. The panel now covers new and saved journeys, separates
  available / late / needs an alternative, shows all five metrics, and the deadline
  reason uses Berlin local time (it printed UTC beside a local arrival time).
- `aacb52f` **Map.** One basemap-unavailable warning instead of three.

Evidence:

- Two instances, one database: 8 concurrent creates split across both, nothing lost
  (11 + 1 + 8 = 20 on each). Demo events stay in `demo/<session>/operations.json`.
  Database stopped: journey requests return 503 with the "no successful save" message;
  health returns 200; recovery is automatic.
- A Via Wuerzburg route saved on the planner was listed in 0.06 s and opened in 0.56 s
  with that road selected and no `/replan` call. It survived forced pre-save queue
  responses, a reload, a fresh browser session, genuine restarts of both instances
  (new PIDs), and was identical on the second instance (`R16-R29-R21`, 223 points).
- Hub editor: add Nuernberg, add Chemnitz, move Chemnitz earlier, remove Chemnitz, all
  through the real buttons. The proposal left the saved itinerary unchanged; approval
  made `R16-R29-R10-R21` the plan and cleared the pending request.
- New journey from Wuerzburg via Hamburg saved and opened. Late requested route is
  explained as late; with a snow zone over Hamburg it needs an alternative, the clear
  direct road is pre-selected, and Approve stays disabled if the blocked one is chosen.
- A departed vehicle without a fresh position: route proposal returns 422 and the saved
  itinerary is unchanged.
- Departure input: `fill("2026-11-19T08:30")` is retained and sent as `07:30Z`. The
  earlier failure was the automation typing into a `datetime-local` control.
- Fallback map draws only the selected road and switches with the side menu. Weather
  simulation places a zone, re-checks the route and selects a verified clear detour.
- 390 px and 1440 px: no horizontal page scroll, no duplicated warnings, no driver
  link or Vehicle progress panel. `npm run build` passes. Manager tests: 8 passed.

Not verified here, needs a machine with internet:

- Google Maps (needs the API key) and the MapLibre road map with real tiles: whether
  only the selected road is drawn and the camera holds on switching. Code shows
  alternatives are off by default (`showAlternatives=false`).
- Real OSRM geometry, and the deployed site against Neon.
- The offline fallback renderer does not draw weather-zone circles (MapLibre does).

## Remaining work, in priority order

### P0: Finish the save and persistence workflow

1. Review the checkpoint diff, then save a side-menu-selected home route. Open the
   control room and verify that exact ID, hub sequence and road are present
   immediately, without waiting for polling. Check the correct queue selection.
2. Reload and use another browser/session or restarted backend to prove Postgres
   persistence. Do not reset the database or remove existing user journeys.
3. Review persistence transactions, cache invalidation after rollback, concurrent
   worker writes/approvals, demo isolation and storage-unavailable responses.
   The current compressed-document layout is a prototype persistence adapter;
   do not claim a normalized or load-tested production database.
4. Confirm incoming saves cannot be hidden by stale queue responses and that a
   busy manager operation cannot lose the saved-journey handoff.

### P1: Finish manager route customization

1. On a saved journey, add Würzburg and another hub, reorder/remove stops, and
   calculate. Verify the requested path, ETA, time, distance, cost and fuel.
2. Confirm a new manager journey can start at Würzburg and be saved and reviewed.
3. Verify unavailable hub/road, weather and capacity cases explain the problem
   and offer clear alternatives with their own estimates. Reject duplicate stops,
   unknown hubs, invalid times and loops. Keep approval blocked for unsafe options.
4. Approve a valid proposal with a reason; confirm its actual road/path remains
   selected after the fresh approval calculation. Check hold/defer behavior and
   pending requests after choosing an alternative instead of the requested path.
5. Review async form/queue races and stale position handling. Preserve completed
   travel and the fresh-position guard for moving vehicles.

### P2: Finish visual acceptance

1. Confirm only the selected road is drawn on Google and backup maps. Change side
   options and confirm the map changes with no hidden stale road or camera reset.
2. Check weather zones, zoom/pan and simulations still work.
3. Check desktop/mobile control-room layout, queue groups, comparison metrics and
   manager forms. Remove duplicate warnings or excess spacing if needed. The
   driver-update link and Vehicle progress panel must stay off this page.

### Release

Run only focused checks and one final production build. Commit major fixes with
clear messages. Coordinate merging this branch into main; main pushes trigger
Vercel production deployment. Verify the deployed save/refresh flow and Postgres
storage. Preview deployments currently do not have the production database
connection automatically, so do not mistake a JSON-fallback preview for a shared
storage test. Update this handoff with actual completed acceptance evidence.

## Setup and boundaries

- Frontend: React/TypeScript/Vite, port 5176, proxy to FastAPI on port 8004.
- Python venv locally: `C:\Users\acer\Documents\ChatGPT\hackathon project\.venv`.
- Hosted app: https://dachser-transit-planner.vercel.app/
- Vercel project: `dachser-transit-planner`, scope `palash57`.
- Production is still the previous main version until this branch is released.
- Vercel CLI login/link was restored locally. Use the existing database resource;
  do not provision duplicates or switch it to a paid plan.
- Pull credentials through authorized Vercel env commands into an ignored local
  file. Explicitly load that env file for the Python backend. Only VITE_* map
  settings belong in frontend/.env.local. Never commit or paste credentials.
- Local backend is currently launched with an ignored helper
  `.runtime/run_postgres_backend.py`, reading `.runtime/neon-production.env`.
  Those files are machine-specific and are intentionally not in this branch.
- Runtime JSON stores, demo-store directories, presentation build files and
  deliverables were left local; they are not source changes to stage blindly.
- Keep the current design, road routing, weather safeguards and approval workflow.
  Avoid unrelated refactors, paid services and broad test suites.
