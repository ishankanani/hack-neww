import { ShieldCheck, TriangleAlert } from "lucide-react";
import type { RouteOption } from "../api/types";
import { dt,eur,hm } from "../lib";
export function PlanChangeNotice({saved,proposed}:{saved?:RouteOption;proposed?:RouteOption}){
 if(!saved||!proposed)return null;
 const minutes=Math.round((Date.parse(proposed.eta)-Date.parse(saved.eta))/60000);
 const cost=proposed.cost.transport_eur-saved.cost.transport_eur;
 const distance=proposed.cost.distance_km-saved.cost.distance_km;
 const fuel=proposed.cost.fuel_l-saved.cost.fuel_l;
 const route=saved.path.join()!==proposed.path.join()||saved.route_id!==proposed.route_id;
 const changed=route||Math.abs(minutes)>=15||Math.abs(cost)>=Math.max(.01,saved.cost.transport_eur*.05)||saved.risk.deadline_ok!==proposed.risk.deadline_ok||saved.revision!==proposed.revision||JSON.stringify(saved.components)!==JSON.stringify(proposed.components)||saved.data_sources.transport!==proposed.data_sources.transport;
 const delta=(value:number,suffix:string)=>`${value>0?"+":""}${Math.round(value*10)/10}${suffix}`;
 const metrics=[
  {label:"Arrival",before:dt(saved.eta),after:dt(proposed.eta),delta:delta(minutes," min"),value:minutes},
  {label:"Journey time",before:hm(saved.total_minutes),after:hm(proposed.total_minutes),delta:delta(proposed.total_minutes-saved.total_minutes," min"),value:proposed.total_minutes-saved.total_minutes},
  {label:"Transport",before:eur(saved.cost.transport_eur),after:eur(proposed.cost.transport_eur),delta:`${cost>0?"+":""}${eur(cost)}`,value:cost},
  {label:"Distance",before:`${saved.cost.distance_km} km`,after:`${proposed.cost.distance_km} km`,delta:delta(distance," km"),value:distance},
  {label:"Fuel",before:`${saved.cost.fuel_l} L`,after:`${proposed.cost.fuel_l} L`,delta:delta(fuel," L"),value:fuel},
 ];
 return <section className={`plan-review-comparison ${changed?"requires-review":"is-current"}`} aria-label="Saved and proposed route comparison"><header><div>{changed?<TriangleAlert size={19}/>:<ShieldCheck size={19}/>}<div><h3>{changed?"Review required":"Saved plan"}</h3><p>{route?"Hub connections or road routing changed.":changed?"Journey estimates or conditions changed.":"The selected route matches the saved itinerary."}</p></div></div><span className={`queue-state queue-state--${changed?"review":"planned"}`}>{changed?"Awaiting approval":"No material change"}</span></header><div className="plan-comparison-labels"><span>Saved</span><span>Selected proposal</span></div><div className="plan-comparison-grid">{metrics.map(metric=><div key={metric.label}><small>{metric.label}</small><span>{metric.before}</span><b>{metric.after}</b><em className={metric.value>0?"delta-increase":metric.value<0?"delta-decrease":"delta-neutral"}>{metric.value===0?"Unchanged":metric.delta}</em></div>)}</div>{changed&&<footer>The saved itinerary stays active until you approve a new route.</footer>}</section>;
}
