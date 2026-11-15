# Google Street View

Open a calculated journey, choose **Street View** in the map toolbar, then select Start, Midpoint, End or a distance along the road. During a journey replay, **Truck position** selects the truck's current simulated location. A blue marker identifies the point on the route map. Selection resets when the road geometry changes.

**Open Street View** opens Google's interactive panorama in a new tab. This uses the official Maps URLs interface and needs no Google API key. Street View is recorded imagery, with coverage determined by Google. It does not display our simulated weather or update routing, costs or approvals.

## Optional embedded panorama

The in-app iframe is implemented but stays disabled until an Embed API key is configured. No panorama requests are made until a manager chooses **Load panorama**. Moving the inspection point does not repeatedly reload Google; **Update panorama** loads the new point.

1. In your Google Cloud project, enable billing and **Maps Embed API**.
2. Create a browser key restricted to **Maps Embed API** and your allowed websites. For this deployment use `https://dachser-transit-planner.vercel.app/*`; add `http://127.0.0.1:5176/*` and `http://localhost:5176/*` only if local use is needed. Add exact preview origins separately when needed.
3. Local development: add `VITE_GOOGLE_MAPS_EMBED_API_KEY=your_restricted_key` to `frontend/.env.local` and restart Vite. This file is ignored by Git.
4. Vercel: add the same environment variable for the frontend build in Production, then redeploy. Vite reads it at build time. Do not commit the actual key.

This is an intentionally browser-visible, restricted key. Never reuse a server credential or the TomTom API key. Keep Google's attribution and controls visible. Iframe dimensions are at least 200 × 200 pixels and the origin referrer is supplied for website restrictions.

Google currently lists Maps Embed API requests as free and unlimited, while requiring a valid API key and Cloud billing setup. This does not mean other Google APIs or Dynamic Street View are free. The embedded integration cannot be verified with a real panorama until a valid, restricted key is supplied. An iframe load event does not prove panorama availability; Google displays its own coverage or configuration messages. The external Maps link remains available.

Official references: [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started), [Street View embedding](https://developers.google.com/maps/documentation/embed/embedding-map#streetview_mode), [Embed usage and billing](https://developers.google.com/maps/documentation/embed/usage-and-billing), [Cloud setup](https://developers.google.com/maps/documentation/embed/cloud-setup).
