# Vercel deployment

Deploy from the repository root, using `vercel.json`. Vercel Services (currently Beta) builds the Vite frontend and FastAPI backend together. `/api/*` reaches FastAPI; other paths reach the frontend. The backend uses the repository root so the supplied CSVs and captured demo roads can be included.

## Account setup

Reconnect the Vercel app in Codex if it reports reauthentication. Alternatively complete `vercel login` in your own terminal. Then select the intended personal account/team and create or link the `dachser-transit-planner` project from this repository root. Inspect the resolved project before publishing. Deploy with `vercel --prod`; review the returned deployment's build logs and check `/api/health`, `/api/network`, map tiles and a route calculation before sharing its URL.

## Environment and state

- Optional `TOMTOM_API_KEY`: add directly to the Vercel backend's environment. It must never be a `VITE_` variable. The cloud API disables public key editing and hides key fragments.
- Optional `VITE_GOOGLE_MAPS_EMBED_API_KEY`: a browser-restricted Maps Embed API key, read during the frontend build. Street View links work without a key; see [Street View setup](STREET_VIEW.md) before enabling embedded panoramas.
- The frontend calls relative `/api` URLs, so no localhost address is shipped to the browser.
- `.vercelignore` excludes credentials, local shipment/scenario stores, caches, dependencies and generated presentations.
- The cloud demo starts without auto-seeded shipments, avoiding routing-provider calls during cold startup. CSV analytics still load normally.
- Vercel execution files are read-only; runtime JSON and tile caches use temporary storage. `/api/network` reports the storage mode. Records can disappear on restart and differ between instances. This is a demonstration configuration, not durable shared operations.
- For a company pilot, move shipments, operational scenarios, approvals and reservations to transactional shared storage and reload state consistently per request. A connected database and authenticated users are required before relying on these records operationally. Deploying the current JSON store to `/tmp` does not supply that persistence.

## Verification

Local frontend and API were started on ports 5176 / 8004. Deployment is complete only after Vercel returns a ready deployment and its API is checked. Account reauthentication and remote build verification cannot be replaced by a local build.

Preparation checks passed: production frontend build; cloud-mode FastAPI startup with 32 facilities, no imported local shipments, and blocked public API-key editing.

## Verified production deployment — 15 November 2026

- URL: https://dachser-transit-planner.vercel.app
- Vercel project: `dachser-transit-planner` (`prj_yVvUKcWUMoDuXjfPAzhkxth228qz`).
- Deployment: `dpl_Ce9NF27bvXKUoxKBUhyErVw6eNkb`, built from commit `e0b737945f12b8484dccc465549d62dc0eb34b3b` after reconnecting the Vercel account.
- Vercel reported `READY`. Unauthenticated HTTPS requests to `/`, `/api/health`, `/api/network` and a basemap tile returned 200. The network response contained 32 facilities and explicitly identified temporary storage.
- A POST to `/api/route` returned four route options, a recommended option and road geometry. This verifies a route calculation, not every operational workflow or durable shared state.
- The anonymous Windows deployment fallback had failed; the successful deployment used the authenticated Vercel connector and GitHub source with remote Linux builds.

## Previous dataset upload

At the user's explicit request, the local baseline was uploaded to Vercel: 14 saved journeys, seven operational events, five weather zones, five manager decisions and three demo-session operation files. The compressed snapshot is uploaded directly to Vercel; it is not committed to the public GitHub repository. Credentials and local caches are excluded.

The production environment references the upload through `HOSTED_SNAPSHOT_URL` and `HOSTED_SNAPSHOT_SHA1`. `scripts/fetch_hosted_snapshot.py` verifies and bundles it during the backend build. Each cold instance restores missing store files from that bundled baseline. Existing files in a warm instance are preserved. `data/hosted_snapshot*` are generated files ignored by Git; the deployment's `/api/network` metadata reports the bundled baseline counts.

The uploaded baseline remains part of that deployment, but subsequent edits still use ephemeral hosted-demo storage. A server reset returns those records to the uploaded baseline. This does not add a transactional shared database, live telematics or carrier capacity integration.
