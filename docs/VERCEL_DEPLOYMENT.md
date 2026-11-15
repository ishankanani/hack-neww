# Vercel deployment

Deploy from the repository root, using `vercel.json`. Vercel Services (currently Beta) builds the Vite frontend and FastAPI backend together. `/api/*` reaches FastAPI; other paths reach the frontend. The backend uses the repository root so the supplied CSVs and captured demo roads can be included.

## Account setup

Reconnect the Vercel app in Codex if it reports reauthentication. Alternatively complete `vercel login` in your own terminal. Then select the intended personal account/team and create or link the `dachser-transit-planner` project from this repository root. Inspect the resolved project before publishing. Deploy with `vercel --prod`; review the returned deployment's build logs and check `/api/health`, `/api/network`, map tiles and a route calculation before sharing its URL.

## Environment and state

- Optional `TOMTOM_API_KEY`: add directly to the Vercel backend's environment. It must never be a `VITE_` variable. The cloud API disables public key editing and hides key fragments.
- The frontend calls relative `/api` URLs, so no localhost address is shipped to the browser.
- `.vercelignore` excludes credentials, local shipment/scenario stores, caches, dependencies and generated presentations.
- The cloud demo starts without auto-seeded shipments, avoiding routing-provider calls during cold startup. CSV analytics still load normally.
- Vercel execution files are read-only; runtime JSON and tile caches use temporary storage. The UI labels this mode. Records can disappear on restart and differ between instances. This is a demonstration configuration, not durable shared operations.
- For a company pilot, move shipments, operational scenarios, approvals and reservations to transactional shared storage and reload state consistently per request. A connected database and authenticated users are required before relying on these records operationally. Deploying the current JSON store to `/tmp` does not supply that persistence.

## Verification

Local frontend and API were started on ports 5176 / 8004. Deployment is complete only after Vercel returns a ready deployment and its API is checked. Account reauthentication and remote build verification cannot be replaced by a local build.

Preparation checks passed: production frontend build; cloud-mode FastAPI startup with 32 facilities, no imported local shipments, and blocked public API-key editing. The authenticated Vercel connector currently requires reauthentication. An anonymous temporary deployment was also attempted from an isolated source copy; its Windows build failed with `spawn cmd.exe ENOENT`. No successful hosted URL has been verified.
