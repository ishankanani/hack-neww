# Dispatch improvements — implementation and rollback plan

Starting checkpoint: `checkpoint-before-dispatch-upgrades-2026-10-18` (`bfa928a`).

## Priority and sequence

### 1. Connection warnings and honest journey status
- Keep the shared ETA engine as the authority for loading, traffic, weather, closures, restrictions and departure timetables.
- Expose hub arrival, readiness, cutoff, service departure, remaining buffer and next-service wait on each option.
- Compare refreshed services with the approved itinerary to identify missed connections and downstream delivery impact.
- Replace clock-inferred delivery with `ARRIVAL EXPECTED`. Require recorded confirmation before `DELIVERED`; preserve old records and identify inferred legacy delivery.
- Add focused checks for connection cutoffs and status transitions. Commit this foundation separately.

### 2. Dispatch attention and decisions
- Rank journeys by blocked/held state, missed connection, delivery risk and decision urgency. Explain every priority; keep demo journeys labelled.
- Offer continuing on the approved itinerary, a clear reroute, and a time-limited wait when calculable. Use the same ETA engine for all actions.
- Show signed kilometres, fuel, transport cost and arrival differences. Unknown alternatives remain unavailable.
- Preserve approval snapshots. Require a fresh quote, manager reason and acknowledgement of a missed deadline.
- Review pending weather and operational events together. Make search exhaustion explicit rather than claiming every possible road is blocked.
- Commit the Control Room workflow separately.

### 3. Vehicle progress and realistic remaining-road routing
- Record timestamped manual or simulated vehicle positions; require a fresh position for in-transit changes.
- Snap progress to the approved road and retain the completed prefix. Never restart at the original loading hub.
- Recalculate the remaining road with the existing ETA engine; skip origin loading and departed services, retain required future hubs for continuing and allow direct/via-hub alternatives for rerouting.
- Keep completed cost/time separate from remaining estimates; use comparable remaining costs for decisions.
- In-transit hold means a stop request until acknowledged by the driver. A request does not assert that the vehicle has stopped.
- Commit progress and decision support separately.

### 4. Capacity, reliability and driver reporting
- Allow managers to enter service and hub availability with an effective window and loading-metre limits; show source and do not imply carrier booking confirmation.
- Exclude capacity-infeasible alternatives from recommendations and approvals. Revalidate availability at approval; do not double-count this shipment's reservation.
- Show lane-specific actual arrival error and an empirical arrival window only with sufficient comparable reported outcomes. Daily aggregate CSV data does not establish arrival timestamps.
- Add a compact mobile-friendly driver update view for departure, position, safe-stop acknowledgement, arrival confirmation and delivery reference.
- Store update history with timestamps and distinguish simulation, reported actuals and planned status. Keep demo updates out of actual performance.
- Commit capacity and driver/reliability work in separate checkpoints.

## Presentation and technical boundaries

- Extend existing screens and visual styles; use progressive disclosure for details.
- Retain the current FastAPI / React / TypeScript / MapLibre stack and existing routing providers.
- Manual availability and driver reporting work without privileged DACHSER integrations. Live telematics, carrier capacity feeds, authenticated driver identities and deployment hardening require a later integration/pilot.
- Continue to label routing fallbacks and modelled costs accurately.
- Runtime shipment/scenario stores, generated presentations and credentials stay outside source commits.
- Run focused regression checks for changed decision rules, then one frontend build and a short browser check. Avoid broad repeated checks without a new failure.

## Research basis

The priorities build on the official sources in `DACHSER_MANAGER_RESEARCH.md`, particularly delivery-window planning, available resources and network resilience. They are product recommendations, not requirements confirmed by DACHSER.

## Delivery record

Update this section as each checkpoint lands. Use `git revert <commit>` for shared-history rollback; the starting tag preserves the prior code.

- Starting code and annotated checkpoint pushed to GitHub before implementation.
- `d99678f`: connection cutoff evidence and confirmed-delivery lifecycle; 38 relevant regression checks passed.
- Attention queue and continue / reroute / bounded-wait comparisons implemented using the same ETA engine. Screening remains distinct from recalculation; unavailable actions have no invented figures.
- `73c6f72`: ranked attention queue and action comparisons.
- `15f2ffb`: fresh reported/simulated positions, completed-road preservation and remaining-road approvals; stop requests do not assert a stopped vehicle.
- `dc564b9`: hub/service availability limits, reservations, recommendation filtering and approval-time overbooking protection.
- Driver update view implemented: recorded departure, delay, position, safe-stop acknowledgement and delivery reference. Open from a journey review or **More → Driver updates**. The view is a prototype without authenticated driver identities or external notifications.
- Arrival evidence implemented: matching origin/destination and planning stage over 180 days; at least 20 usable reported deliveries required for a descriptive middle-80% error range. No calibrated probability or fabricated history is claimed.
- Simulation use stays attached to the journey for reporting, even if the simulated route was never approved. Such journeys remain excluded from operational actuals.
- UI reviews can move a missed, unstarted departure to five minutes ahead. The saved approval remains intact; isolated historical demos retain their timeline.
- Final verification: 53 focused backend checks passed, TypeScript and production frontend build passed. Browser review confirmed operational/demo queue order, current route comparisons, unavailable arrival ranges without observations and the manager-to-driver handoff; no client errors were recorded in that walkthrough.
- Current live providers remain independently dependent on credentials and availability. The browser walkthrough used OSRM road geometry where truck routing was unavailable; the UI identifies that fallback. No external capacity, driver authentication or telematics integration is claimed.

## Demonstration walkthrough

1. Plan a current journey and inspect the cutoff/readiness evidence when a departure timetable is configured.
2. Save it and open the Control Room. Inspect the priority reasons, then compare continuing, a clear reroute and a bounded departure wait (when an event end makes waiting calculable).
3. Record a manager reason and approve the selected clear, capacity-feasible option. A changed quote or position requires a new review.
4. Open the journey's driver view and report departure. Record a current position, or use **Simulate progress** on a separate demo journey. Reopen the review to see only remaining-road alternatives and the grey completed prefix.
5. Request a safe stop. In the driver view record a fresh stopped position and identify the stopping location, then acknowledge. The shipment is held only after acknowledgement; release requires a fresh clear approval.
6. Enter an availability limit for an intermediate hub or scheduled service. Recalculate to see infeasible options excluded. Approvals reserve capacity inside the prototype and recheck competing reservations.
7. Confirm arrival with a delivery reference. Add actual cost only when known and when departure is recorded. Inspect **Savings → Actual outcomes**; arrival ranges stay unavailable until enough matching actuals exist.

Do not use simulation on a journey intended to represent real operational performance. A map animation or passed ETA is never proof of delivery. Capacity and cost remain modelled/manual until carrier systems are integrated.
