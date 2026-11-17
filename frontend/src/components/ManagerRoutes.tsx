import { useState } from "react";
import { ArrowDown, ArrowUp, Plus, Route, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, Operations, RouteOption, RouteResp, Shipment } from "../api/types";
import { dt, eur, hm, localInput } from "../lib";
import { RouteCompare } from "./RouteCompare";

const feasible=(o:RouteOption)=>o.route_feasible!==false&&o.capacity?.feasible!==false&&["CLEAR","NO_ZONE"].includes(o.avoidance_status??"");
export function ManagerRoutes({nodes,shipment,ops,onProposed,onCreated,disabled=false,onBusyChange}:{nodes:NetNode[];shipment?:Shipment;ops:Operations|null;onProposed:(s:Shipment)=>void;onCreated:(s:Shipment)=>void;disabled?:boolean;onBusyChange?:(busy:boolean)=>void}){
 const [origin,setOrigin]=useState(shipment?.origin??nodes.find(n=>n.name==="Würzburg")?.id??"R16");
 const [destination,setDestination]=useState(shipment?.destination??"R21");
 const [via,setVia]=useState<string[]>(shipment?.manager_route_request?.via_hubs??shipment?.route.slice(1,-1).filter(n=>n!=="@vehicle")??[]);
 const [add,setAdd]=useState("");
 const [depart,setDepart]=useState(()=>localInput(new Date(Math.max(Date.parse(shipment?.planned_departure??"")||0,Date.now()+10*60000))));
 const [weight,setWeight]=useState("12000"),[value,setValue]=useState("180000");
 const [deadline,setDeadline]=useState(()=>localInput(new Date(Date.now()+3*86400000)));
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 const [result,setResult]=useState<RouteResp|null>(null),[selected,setSelected]=useState(0);
 const [calculated,setCalculated]=useState<Parameters<typeof api.route>[0]|null>(null);
 const moving=!!shipment&&(!!shipment.movement_started_at||["IN TRANSIT","DELAYED","ARRIVAL EXPECTED"].includes(shipment.status));
 const freshPosition=!moving||!!shipment?.vehicle_position&&Date.now()-Date.parse(shipment.vehicle_position.reported_at)<900000;
 const name=(id:string)=>nodes.find(n=>n.id===id)?.name??"Vehicle position";
 const clearDraft=()=>{setResult(null);setCalculated(null)};
 const changeVia=(next:string[])=>{setVia(next);clearDraft()};
 // A saved journey carries its request on the shipment; a new journey only has the
 // calculation result. Explain the requested connection in both cases.
 const requested=shipment?.manager_route_request?shipment.options?.filter(o=>o.manager_requested):result?.options.filter(o=>o.manager_requested);
 const bestRequested=requested?.find(feasible)??requested?.[0];
 const requestedState=!bestRequested?"":!feasible(bestRequested)?"unavailable":!bestRequested.risk.deadline_ok?"late":"ok";
 async function calculate(){
  setBusy(true);onBusyChange?.(true);setError("");
  try{
   if(origin===destination)throw Error("Choose different origin and destination hubs.");
   if(shipment){const s=await api.proposeRoute(shipment.id,{via_hubs:via,...(!moving?{depart_at:new Date(depart).toISOString()}:{})});onProposed(s)}
   else{
    const body={origin,destination,via_hubs:via,depart_at:new Date(depart).toISOString(),required_delivery:new Date(deadline).toISOString(),weight_kg:Number(weight),value_eur:Number(value),optimization:"fastest"};
    const r=await api.route(body);setResult(r);setCalculated(body);
    const preferred=r.options.findIndex(o=>o.manager_requested&&feasible(o));setSelected(preferred>=0?preferred:0);
   }
  }catch(e){setError(String(e).replace(/^Error:\s*/,""))}finally{setBusy(false);onBusyChange?.(false)}
 }
 async function save(){if(!result||!calculated)return;setBusy(true);setError("");try{const chosen=result.options[selected];const s=await api.createShipment({...calculated,planned_departure:calculated.depart_at,selected_path:chosen.path,selected_route_id:chosen.route_id});onCreated(s);setResult(null)}catch(e){setError(String(e))}finally{setBusy(false)}}
 return <section className="manager-route-builder" aria-label="Manager route builder">
  <div className="manager-builder-heading"><div><Route size={18}/><h3>{shipment?"Choose your hub connections":"Plan a manager journey"}</h3></div><span>Stops are visited in this order</span></div>
  <form onSubmit={e=>{e.preventDefault();void calculate()}}>
   <div className="manager-route-endpoints"><label>Origin{shipment?<b>{moving?"Reported vehicle position":name(origin)}</b>:<select aria-label="Manager origin" value={origin} onChange={e=>{setOrigin(e.target.value);changeVia([])}}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select>}</label><span>→</span><label>Destination{shipment?<b>{name(destination)}</b>:<select aria-label="Manager destination" value={destination} onChange={e=>{setDestination(e.target.value);changeVia([])}}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select>}</label>{!moving&&<label>Departure<input type="datetime-local" aria-label="Manager departure" value={depart} required onChange={e=>{setDepart(e.target.value);clearDraft()}}/></label>}</div>
   <ol className="manager-hub-stops">{via.map((id,index)=><li key={id}><span className="hub-stop-number">{index+1}</span><b>{name(id)}</b><div><button type="button" aria-label={`Move ${name(id)} earlier`} disabled={index===0||busy} onClick={()=>{const n=[...via];[n[index-1],n[index]]=[n[index],n[index-1]];changeVia(n)}}><ArrowUp size={14}/></button><button type="button" aria-label={`Move ${name(id)} later`} disabled={index===via.length-1||busy} onClick={()=>{const n=[...via];[n[index+1],n[index]]=[n[index],n[index+1]];changeVia(n)}}><ArrowDown size={14}/></button><button type="button" aria-label={`Remove ${name(id)} stop`} disabled={busy} onClick={()=>changeVia(via.filter(n=>n!==id))}><Trash2 size={14}/></button></div></li>)}</ol>
   <div className="manager-add-stop"><label>Intermediate hub<select aria-label="Add intermediate hub" value={add} onChange={e=>setAdd(e.target.value)} disabled={busy||via.length>=6}><option value="">Choose a hub</option>{nodes.filter(n=>n.id!==origin&&n.id!==destination&&!via.includes(n.id)).map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select></label><button className="btn btn--ghost" type="button" disabled={!add||busy||via.length>=6} onClick={()=>{changeVia([...via,add]);setAdd("")}}><Plus size={14}/>Add stop</button></div>
   <div className="manager-route-chain">{[moving?"Reported position":name(origin),...via.map(name),name(destination)].join(" → ")}</div>
   {!shipment&&<div className="manager-new-details"><label>Shipment weight · kg<input aria-label="Manager shipment weight" type="number" required min="1" max="23800" value={weight} onChange={e=>{setWeight(e.target.value);clearDraft()}}/></label><label>Shipment value · €<input aria-label="Manager shipment value" type="number" min="0" max="100000000" value={value} onChange={e=>{setValue(e.target.value);clearDraft()}}/></label><label>Deliver by<input aria-label="Manager delivery deadline" type="datetime-local" required value={deadline} onChange={e=>{setDeadline(e.target.value);clearDraft()}}/></label></div>}
   {!freshPosition&&<p className="manager-route-warning">A fresh vehicle position is needed to calculate a road change for this active journey.</p>}
   {error&&<p className="manager-route-warning" role="alert">{error}</p>}
   <button className="btn" disabled={busy||disabled||!freshPosition}>{busy?"Calculating connections…":"Calculate requested route & alternatives"}</button>
  </form>
  {bestRequested&&<div className={`requested-route-feedback ${requestedState==="ok"?"is-feasible":"is-unavailable"}`} role="status"><div><b>{requestedState==="unavailable"?"Requested connection needs an alternative":requestedState==="late"?"Requested connection is available but misses the delivery deadline":"Requested connection is available"}</b><span>{bestRequested.path.map(name).join(" → ")}</span></div><div className="requested-route-metrics"><span><small>Arrival</small><b>{dt(bestRequested.eta)}</b></span><span><small>Journey time</small><b>{hm(bestRequested.total_minutes)}</b></span><span><small>Distance</small><b>{bestRequested.cost.distance_km} km</b></span><span><small>Fuel</small><b>{bestRequested.cost.fuel_l} L</b></span><span><small>Transport</small><b>{eur(bestRequested.cost.transport_eur)}</b></span></div>{bestRequested.unavailable_reasons?.map(reason=><p key={reason}>{reason}</p>)}{requestedState!=="ok"&&<p>Compare the other options below — each shows its own arrival, journey time and cost.</p>}</div>}
  {result&&<><RouteCompare nodes={nodes} options={result.options} selected={selected} onSelect={setSelected} showJourneyTools={false} weatherZones={ops?.weather_zones}/><div className="manager-save-route"><button className="btn" disabled={busy} onClick={()=>void save()}>Save selected route for review</button></div></>}
 </section>;
}
