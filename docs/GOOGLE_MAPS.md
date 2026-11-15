# Google Maps basemap

The route planner, Control Room and shipment route comparisons use the Google Maps JavaScript renderer when `VITE_GOOGLE_MAPS_API_KEY` is configured at frontend build time. Google Maps renders the main map directly; it is not a Street View link or iframe. The old Street View toolbar action is removed.

The same backend road geometry, forecast samples, route traffic sections, weather-zone records and journey replay clock drive the map. This integration does not call paid Google routing, Places or weather endpoints. Routing remains TomTom or the OSRM fallback. Google map loads still count toward Google's key quota.

Supported interactions:

- Selected and alternative road routes, with click-to-select alternatives.
- Road, satellite, hybrid and terrain basemaps; fit, zoom, full screen and facility details.
- Completed road, weather-affected comparison road and abandoned replay legs.
- Forecast markers and traffic restricted to the selected road corridor.
- Snow, rain and tornado zones: click or drop onto the map, drag the pin, change radius, remove or cancel. All active zones still reach the existing rerouting engine together.
- Native Google circle overlays and animated weather in the Google overlay pane, below Google's controls and attribution. Dragging moves both the circle and its animation; a rejected save restores the prior position.
- Smooth truck replay, rotation and follow-camera using the same simulation clock. Handling and rest periods remain stationary.
- Read-only weather display in the Control Room. Manager route approval and hold logic are unchanged.

## No-billing prototype setup

Google's [Maps Demo Key](https://developers.google.com/maps/documentation/javascript/demo-key) supports map rendering, markers, events and drawing for prototypes without adding billing information. It requires a personal Google account, eligibility checks and acceptance of the Maps Demo Project Terms. Daily limits may change; reaching the limit pauses access rather than charging. It is not intended for production operations.

After the account owner approves those terms and the key is issued:

1. Restrict the browser key to Maps JavaScript API and the website origins actually used: `https://dachser-transit-planner.vercel.app`, `http://127.0.0.1:5176` and `http://localhost:5176`. The loader sends the origin referrer. Keep unrelated APIs disabled on this key.
2. Save it to ignored `frontend/.env.local` as `VITE_GOOGLE_MAPS_API_KEY`. Set `VITE_GOOGLE_MAP_ID=DEMO_MAP_ID` for the prototype. Restart Vite because build environment variables are not hot reloaded.
3. Set the same variables in the Vercel project's Production build environment and redeploy. The browser key is intentionally visible in the frontend bundle; website and API restrictions are the protection. Never reuse the backend TomTom credential.
4. Confirm a real Google basemap renders, switch routes, place and move a weather zone, play/pause the truck and try the follow-camera. Verify that active zones still affect the backend route responses.

If no Google key is configured, the existing map remains usable. Google load/authentication failures display an error and offer the backup map. They are not reported as a successful Google integration. Neither signing into Google nor accepting its legal terms is performed silently.

## Setup checkpoint

On 15 November 2026, the account owner explicitly approved the Maps Demo Project Terms and creation of a no-billing demo key. The generated key was limited to **Maps JavaScript API** and the three origins above. Its value is stored in ignored local configuration and Vercel's encrypted Production environment; it is not committed to Git. No billing account was added.

The real Google basemap and a 5 km tornado scenario were verified locally. The backend returned a weather-clear detour with 59.5 km additional road distance, and the map retained Google's basemap while rendering that road and the tornado overlay. This validates the integration path for that scenario, not every possible road or weather outcome.

Truck playback and pause were verified on the real Google map. A routine quote refresh now retains the replay's starting plan and progress, instead of resetting because the quote ID changed. The Google camera refits for road or layout changes, not for an identical road in a refreshed quote. Reset loads the newest replay plan; changing the road, departure, truck profile, deadline or weather scenario resets the replay automatically.

## Company pilot

For operational use, replace the demo key with a restricted Google Cloud key, configure the project's own map ID, quotas and billing, and review current Google pricing and applicable terms. A free usage allowance is not a guarantee of zero charges on a billing-enabled account. Durable shared records and authenticated manager/driver identities are also needed before this prototype becomes an operational system.

References: [Google loader](https://developers.google.com/maps/documentation/javascript/load-maps-js-api), [advanced markers](https://developers.google.com/maps/documentation/javascript/advanced-markers/add-marker), [custom overlays](https://developers.google.com/maps/documentation/javascript/customoverlays), [pricing](https://developers.google.com/maps/documentation/javascript/usage-and-billing).
