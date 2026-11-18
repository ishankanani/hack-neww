export interface NetNode { id: string; name: string; type: "hub" | "branch"; lat: number; lon: number; relation?: string; source: string; }
export interface Edge { id: string; from: string; to: string; km: number; base_drive_minutes: number; cost_eur: number; cost_special_eur: number; capacity_ldm: number; relation: string; source: string; }
export interface NetworkDoc { deployment?:{hosting:string;storage:string;message:string|null}; hub_id: string; nodes: NetNode[]; edges: Edge[]; }

export interface TransferStat { samples: number; spillover_rate: number; avg_utilisation: number; avg_transfer_minutes: number; median_transfer_minutes: number; range_minutes: number[]; source: string; }
export interface RelationHistory { samples: number; avg_utilisation: number; spillover_rate: number; special_trip_rate: number; avg_line_trailers: number; avg_daily_cost_eur: number; avg_daily_fuel_l: number; avg_volume_ldm: number; reliability_pct: number; source: string; }
export interface OperationalDelay { minutes: number; reason: string; note?: string; status: string; at: string; }
export interface Hub extends NetNode { transfer: TransferStat | Record<string, never>; history: RelationHistory | Record<string, never>; operational_delay: OperationalDelay | null; expected_transfer_minutes: number; }

export interface JourneyStep { type: "handling" | "drive" | "legal_wait" | "hub_delay" | "weekend_hold" | "weather" | "schedule_wait" | "manager_wait" | "driver_break" | "driver_rest" | "weekly_rest"; location: string; location_name: string; start: string; end: string; minutes: number; detail: string; source: string; }
export interface Components { driver_break?:number; driver_rest?:number; weekly_rest?:number; transport: number; transfer: number; hub_delay: number; traffic: number; legal_wait: number; weekend_hold?: number; weather?: number; schedule_wait?: number; manager_wait?: number; }
export interface CostLeg { from: string; to: string; transport_eur: number; tariff_eur: number; km: number; ldm_share: number; basis: "lane_tariff" | "distance_estimate"; }
export interface OptCost { transport_eur: number; fuel_l: number; fuel_eur: number; distance_km: number; cost_per_kg: number | null; detour_surcharge_eur?: number; legs?: CostLeg[]; }
export interface OptRisk { level: string; score: number; reasons: string[]; exposure_eur: number; deadline_ok: boolean; }
export interface OptHistory { avg_cost_eur: number; avg_fuel_l: number; reliability_pct: number; samples: number; }
export interface LiveWeather { id:string; lat:number; lon:number; status:string; source:string; name?:string; condition?:string; temperature_c?:number; rain_mm?:number; wind_kmh?:number; visibility_m?:number; level?:string; delay_minutes?:number; valid_at:string; fetched_at?:string; message?:string; }
export interface Incident { id:string; geometry:{type:string;coordinates: number[] | number[][]}; description:string; delay_minutes:number; source:string; }
export interface MapConditions { weather:LiveWeather[]; incidents:{status:string;items:Incident[];fetched_at?:string}; traffic_configured:boolean; at:string; fetched_at:string; }
export interface TruckProfile { height_m:number; width_m:number; length_m:number; gross_weight_kg:number; }
export interface RouteOption {
  planning_rules?:PlanningRules;
  driver_plan?:{assumption:string;break_minutes:number;rest_minutes:number;requires_review:string[]}|null;
  road_legs?: {from:string;to:string;departure?:string;arrival?:string;source?:string;km?:number}[];
  route_feasible?:boolean;unavailable_reasons?:string[];manager_requested?:boolean;
  arrival_evidence?:ArrivalEvidence;
  capacity?:CapacityEvidence;
  remaining_only?:boolean;position_id?:string;vehicle_start?:{lat:number;lon:number;reported_at:string;source:string};completed_geometry?:number[][];completed_estimates?:OptCost;remaining_cost?:OptCost;
  dispatch_action?:"wait";dispatch_wait_until?:string;
  connections?:ConnectionWarning[];
  quote_id:string; route_id?:string; evaluated_at:string; valid_until:string; is_demo?:boolean; vehicle_constraints?:string;
  avoidance_status?:"CLEAR"|"IMPACTED"|"NO_ZONE"|"NO_CLEAR_DETOUR"; zone_impacts?:{id:string;kind:string;radius_km:number;delay_minutes:number}[]; detour_km?:number;
  weather_detours?:{from:string;to:string;original_segment:number[][];detour_segment:number[][];divert_at:number[];rejoin_at:number[];extra_km:number}[];
  badges?:string[]; optimization?:string; live_weather?:LiveWeather[]; traffic_status?:string;
  traffic_sections?:{geometry:number[][];delay_minutes:number;description:string}[];
  comparison?:{baseline:string;money_saved_eur:number;minutes_saved:number;fuel_saved_l:number};
  baseline_snapshot?:{path?:string[];total_minutes?:number;cost?:OptCost;components?:Components};
  historical_comparison?:{scope:string;matched:boolean;relations:string[];samples:number;normalized_cost_eur:number|null;cost_difference_eur:number|null;reliability_pct:number|null;note:string};
  revision?: number; weather_alerts?: WeatherRecord[];
  intermediate_hub?: { hub: string; name: string; reason: string; distance_to_destination_km: number; route_deviation_km: number } | null;
  recommendation_note?: string;
  origin: string; destination: string; path: string[]; depart_at: string; eta: string; total_minutes: number;
  components: Components; steps: JourneyStep[]; data_sources: Record<string, string>; label: string; kind: string;
  cost: OptCost; risk: OptRisk; ldm: number; historical: OptHistory | null; geometry?: number[][] | null;
}
export interface Savings { money_eur: number; fuel_l: number; time_min: number; note: string; }
export interface WeatherObs { node: string; name?: string; observed?: boolean; temp_c?: number; wind_kmh?: number; status: string; error?: string; }
export interface Provider { key: string; name: string; status: string; configured: boolean; kind: string; last_success: string | null; last_attempt: string | null; data_timestamp: string | null; error: string | null; }
export interface RouteResp { revision?: number; options: RouteOption[]; recommended: number | null; savings: Savings | null; weather: WeatherObs[]; providers: Provider[]; evaluated_at: string; sample?: {id:string;title:string;weather_applied:boolean}|null; weather_zones?:WeatherZone[]; }
export interface JourneyExample { id:string; title:string; description:string; weather_zone_count:number; request:{origin:string;destination:string;depart_at:string;required_delivery:string;weight_kg:number;value_eur:number;optimization:string}; }

export interface Shipment {
  selected_option?:number;
  manager_route_request?:{via_hubs:string[];path:string[];depart_at:string|null;requested_at:string;source:string};
  simulation_used?:boolean;
  actual_departure?:string;driver_updates?:{kind:string;reported_at:string;at?:string;source:string;reference?:string;minutes?:number}[];reported_delay?:{minutes:number;reason:string;at:string;until:string;source:string};
  vehicle_position?:VehiclePosition;movement_started_at?:string;stop_request?:{status:"REQUESTED"|"ACKNOWLEDGED";reason:string;at:string;reference?:string};
  dispatch?:DispatchAttention;dispatch_actions?:DispatchAction[];
  delivery_confirmation?:{at:string;source:string;reference:string|null};
  hold?:{reason:string;at:string;route_id?:string;path:string[];previous_status:string;plan:RouteOption};
  disruption_savings?:DisruptionSavings|null;
  accepted_plan?:RouteOption; approved_at?:string; data_kind?:string; demo_session?:string; plan_change?:PlanChange|null; actual?:ActualOutcome;
  id: string; origin: string; destination: string; current_location: string; route: string[]; next_hub: string | null;
  status: string; planned_departure: string; scheduled_departure: string | null; current_eta: string; required_delivery: string | null;
  distance_km: number; weight_kg: number; container: string | null; value_eur: number; est_cost_eur: number; est_fuel_l: number;
  cost_per_kg: number | null; risk_level: string; customer_segment: string | null; alert: string | null; delay_minutes: number; created_at: string;
  options?: RouteOption[]; pending_hub_delay_minutes?:number; pending_hub_events?:string[]; pending_traffic_minutes?:number; pending_traffic_events?:string[]; pending_closure_events?:string[]; projected_eta?:string|null;
}
export interface Holiday { date: string; name: string; region: string; country: string; transport_impact: string; }
export interface AuditEvent { at: string; type: string; detail: string; source: string; }
export interface RelationStat extends RelationHistory { relation: string; destination: string; km: number; cost_line_eur: number; cost_special_eur: number; }
export interface Disruption { from: string; to: string; type: string; description: string; volume_effect: number; recovery_next_day: number; source: string; }
export interface HighValue { id: string; value_eur: number; origin: string; destination: string; current_location: string; route: string[]; required_delivery: string | null; current_eta: string; risk_level: string; exposure_eur: number; reasons: string[]; recommended_action: string; }
export interface Dashboard { counts: Record<string, number>; total: number; at_risk: number; high_value: number; active_hub_delays: number; next_holiday: Holiday | null; estimated_savings_eur: number; providers: Provider[]; generated_at: string; }
export interface SavingsTotals {
  money_eur: number; fuel_l: number; time_min: number; optimized: number;
  time_value_eur: number; disruption_eur: number; exposure_avoided_eur: number;
  economic_benefit_eur: number; fuel_eur: number;
}
export type SavingsScenarioObjective = "match_dispatch" | "clear_demand";
export type SavingsScenarioKind = "efficient" | "special_trips" | "freight_backlog" | "surplus_trailers";
export interface ScenarioDispatch {
  regular: number;
  special: number;
  dispatched_ldm: number;
  deferred_ldm: number;
  cost_eur: number;
}
export interface SavingsScenario {
  kind: SavingsScenarioKind;
  date: string;
  demand_ldm: number;
  target_dispatch_ldm: number;
  capacity_used_ldm: number;
  historical_utilisation_pct: number;
  recorded_surplus: number;
  historical: ScenarioDispatch;
  simulation: ScenarioDispatch;
  difference_eur: number;
  additional_dispatch_ldm: number;
}
export interface SavingsScenarios {
  lane: string;
  lanes: {id: string; name: string}[];
  reserve: number;
  objective: SavingsScenarioObjective;
  rated_capacity_ldm: number;
  target_capacity_ldm: number;
  regular_rate_eur: number;
  special_rate_eur: number;
  rows_scanned: number;
  rows_excluded: number;
  lane_summary: {
    days: number;
    first_date: string;
    last_date: string;
    recorded_cost_eur: number;
    simulated_cost_eur: number;
    saving_eur: number;
    cheaper_days: number;
    equal_days: number;
    costlier_days: number;
    additional_dispatch_ldm: number;
  } | null;
  scenarios: SavingsScenario[];
}
export interface DisruptionSavings {
  minutes_avoided: number; cost_delta_eur: number; fuel_delta_l: number;
  deadline_rescued: boolean; exposure_avoided_eur: number;
  previous_path: string[]; new_path: string[];
  counterfactual_eta: string; approved_eta: string; recorded_at: string;
  basis: string; value_eur: number;
}
export interface SavingsRow {
  id: string; container: string | null; route: string[]; status: string;
  basis: "quote" | "snapshot" | "derived" | "legacy"; basis_label: string;
  money_eur: number; fuel_l: number; time_min: number; time_value_eur: number;
  disruption_eur: number; exposure_avoided_eur: number; benefit_eur: number;
  comparable: boolean; disruption: DisruptionSavings | null;
  data_kind:"estimated"|"demo"; excluded_reason:string|null;
  evidence:{quote_id:string|null;approved_at:string|null;manager_reason:string|null;evaluated_at:string|null;baseline:string|null;source:string|null;revision:number|null;arrival:string|null;outcome_recorded:boolean};
}
export interface SavingsResp {
  scope:"estimated"|"demo"; excluded_count:number; unapproved_count:number; demo_excluded_count:number;
  total: SavingsTotals; avg_per_shipment_eur: number; per_shipment: SavingsRow[];
  legacy_count: number; rerouted_count: number;
  assumptions: { value_of_time_eur_per_hour: number; note: string };
  note: string; source: string; repaired?: number;
}
export interface RerouteResp {
  status: "ROUTED" | "PARTIAL" | "UNAVAILABLE";
  geometry: number[][] | null; distance_km: number; drive_minutes: number;
  hold_minutes: number; total_minutes: number; eta: string; via: string | null;
  legs: { distance_km: number; duration_minutes: number; source: string; routed: boolean }[];
  source: string; note: string; weather_clear?:boolean;
  weather_detours?:{original_segment:number[][];detour_segment:number[][];divert_at:number[];rejoin_at:number[];extra_km:number}[];
}

export interface WeatherInput { node: string; start: string; end: string; temperature_c: number; condition: string; rain_mm: number; snow_cm: number; visibility_m: number; wind_kmh: number; severity: string; }
export interface WeatherRecord extends WeatherInput { id: string; alert: boolean; level: string; delay_minutes: number; message: string; action: string; source: string; }
export interface ScenarioEvent { id: string; kind: string; node?: string; origin?: string; destination?: string; start: string; end: string; minutes: number; reason: string; affected_count?:number; affected_shipments?:string[]; }
export interface Decision { id: string; shipment_id: string; action: string; reason: string; updated_at: string; created_at?:string; path: string[]; reviewed_path?:string[]; eta: string; superseded_by?:string; supersedes_decision_id?:string; reason_edits?:{previous_reason:string;reason:string;at:string}[]; decided_by?:string|null; previous_route?:string[]; reviewed_eta?:string; acknowledge_deadline?:boolean; }
export interface WeatherZoneInput { kind:"snow"|"rain"|"tornado"; lat:number; lon:number; radius_km:number; start:string; end:string; }
export interface WeatherZone extends WeatherZoneInput {id:string; updated_at:string;}
export interface Operations { revision: number; weather: WeatherRecord[]; weather_zones: WeatherZone[]; events: ScenarioEvent[]; decisions: Decision[]; }

export interface Service { id:string; origin:string; destination:string; weekdays:number[]; departure_time:string; timezone:string; cutoff_minutes:number; source:string; }
export interface ArrivalEvidence {samples:number;minimum_samples:number;lookback_days:number;status:string;remaining_only:boolean;median_error_minutes:number|null;arrival_mae_minutes:number|null;lower_error_minutes:number|null;upper_error_minutes:number|null;window_start:string|null;window_end:string|null;source:string;note:string;}
export interface CapacityRecord { id:string;kind:"hub"|"service";node:string|null;service_id:string|null;start:string;end:string;available_ldm:number;reason:string;source:string; }
export interface CapacityEvidence { feasible:boolean;status:string;requested_ldm:number;source:string;checks:{kind:string;resource:string;from?:string;to?:string;available_ldm:number;reserved_ldm:number;requested_ldm:number;feasible:boolean;source:string;reason:string}[];unverified_resources:{kind:string;resource:string}[]; }
export interface ConnectionWarning { service_id:string;from:string;to:string;arrival:string;ready_at:string;cutoff_at:string;cutoff_minutes:number;buffer_minutes:number;wait_minutes:number;departure:string;source:string;status:"MISSED"|"TIGHT"|"ON TRACK";previous_departure:string|null;connection_delay_minutes:number; }
export interface VehiclePosition { id:string;lat:number;lon:number;reported_at:string;source:string;movement_state:"MOVING"|"STOPPED";base_quote_id:string;offset_km:number;completed_geometry:number[][];remaining_path:string[];completed_estimates:OptCost;note:string; }
export interface DispatchAttention { priority:string;score:number;reasons:string[];connections:(ConnectionWarning&{projected_buffer_minutes:number})[];weather_zone_ids:string[];decision_by:string|null;note?:string; }
export interface DispatchAction { action:"continue"|"reroute"|"wait";option_index:number|null;available:boolean;reason:string;eta:string|null;deadline_ok:boolean|null;distance_km:number|null;transport_eur:number|null;fuel_l:number|null;wait_until:string|null;delta:{km:number;transport_eur:number;fuel_l:number;arrival_minutes:number}|null; }
export interface PlanChange { material:boolean; reasons:string[]; eta_minutes:number; cost_eur:number; previous_eta?:string; proposed_eta?:string; previous_cost?:number; proposed_cost?:number; evaluated_at?:string; }
export interface ActualOutcome { actual_departure:string; actual_arrival:string; actual_cost_eur:number; arrival_error_minutes:number; cost_error_eur:number; on_time:boolean|null; source:string; }
export interface ActualEvidence { id:string;route:string[];quote_id:string;approved_at:string;recorded_at:string|null;approved_eta:string;actual_arrival:string;actual_cost_eur:number;approved_cost_eur:number;arrival_error_minutes:number;cost_error_eur:number;on_time:boolean|null;source:string; }
export interface Performance { samples:number; minimum_samples:number; status:string; arrival_mae_minutes:number|null; cost_error_eur:number|null; on_time_pct:number|null; deadline_samples:number; source:string; excluded_records:number;outcomes:ActualEvidence[]; }
export interface AppSettings { tomtom_configured: boolean; tomtom_masked: string; traffic_status: string; traffic_mode: string; }

export interface PlanningRules {region:string;company_sunday_hold:boolean;trailer_attached:boolean}
export interface TransportCalendarDay {date:string;weekday:number;sunday:boolean;holiday:string|null;truck_ban:boolean;ban_start:string|null;ban_end:string|null;company_hold:boolean;summer_route_review:boolean}
export interface TransportCalendarDoc {year:number;month:number;region:string;region_name:string;timezone:string;days:TransportCalendarDay[];regions:{id:string;name:string}[];scope:string;notes:string[];source:string}
