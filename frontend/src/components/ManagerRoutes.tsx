import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Plus, Route, Trash2 } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, Operations, RouteOption, RouteResp, Shipment } from "../api/types";
import { dt, eur, hm, localInput } from "../lib";
import { RouteCompare } from "./RouteCompare";

const feasible=(o:RouteOption)=>o.route_feasible!==false&&o.capacity?.feasible!==false&&["CLEAR","NO_ZONE"].includes(o.avoidance_status??"");
const movingShipment=(s?:Shipment)=>!!s&&(!!s.movement_started_at||["IN TRANSIT","DELAYED","ARRIVAL EXPECTED"].includes(s.status));
const shipmentStops=(s?:Shipment)=>s?.manager_route_request?.via_hubs??(movingShipment(s)&&s?.vehicle_position?s.vehicle_position.remaining_path.filter(n=>n!==s.destination&&n!=="@vehicle"):s?.route.slice(1,-1).filter(n=>n!=="@vehicle"))??[];
export function ManagerRoutes({nodes,shipment,ops,onProposed,onCreated,disabled=false,onBusyChange,onDraftChange}:{nodes:NetNode[];shipment?:Shipment;ops:Operations|null;onProposed:(s:Shipment)=>void;onCreated:(s:Shipment)=>void;disabled?:boolean;onBusyChange?:(busy:boolean)=>void;onDraftChange?:(dirty:boolean)=>void}){
 const [origin,setOrigin]=useState(shipment?.origin??nodes.find(n=>n.name==="Würzburg")?.id??"R29");
 const [destination,setDestination]=useState(shipment?.destination??"R21");
 const [via,setVia]=useState<string[]>(()=>shipmentStops(shipment));
 const [add,setAdd]=useState("");
 const [depart,setDepart]=useState(()=>{const planned=Date.parse(shipment?.manager_route_request?.depart_at??shipment?.planned_departure??"");return localInput(new Date(planned>Date.now()?planned:Date.now()+10*60000))});
 const [weight,setWeight]=useState("12000"),[value,setValue]=useState("180000");
 const [deadline,setDeadline]=useState(()=>localInput(new Date(Date.now()+3*86400000)));
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 const [result,setResult]=useState<RouteResp|null>(null),[selected,setSelected]=useState(0);
 const [calculated,setCalculated]=useState<Parameters<typeof api.route>[0]|null>(null);
 const [draft,setDraft]=useState(false);
 const [latitude,setLatitude]=useState(""),[longitude,setLongitude]=useState("");
 const [stopped,setStopped]=useState(!!shipment?.hold);
 useEffect(()=>{if(shipment){setVia(shipmentStops(shipment));setDraft(false)}},[shipment?.id,shipment?.manager_route_request?.requested_at,shipment?.approved_at,shipment?.vehicle_position?.id]);
 const moving=movingShipment(shipment);
 const freshPosition=!moving||!!shipment?.vehicle_position&&Date.now()-Date.parse(shipment.vehicle_position.reported_at)<900000;
 const name=(id:string)=>nodes.find(n=>n.id===id)?.name??"Vehicle position";
 const clearDraft=()=>{setResult(null);setCalculated(null);setDraft(true);setError("");onDraftChange?.(true)};
 const changeVia=(next:string[])=>{setVia(next);clearDraft()};
 // A saved journey carries its request on the shipment; a new journey only has the
 // calculation result. Explain the requested connection in both cases.
 const requested=draft?undefined:shipment?.manager_route_request?shipment.options?.filter(o=>o.manager_requested):result?.options.filter(o=>o.manager_requested||o.path.join() === [calculated?.origin,...(calculated?.via_hubs??[]),calculated?.destination].join());
 const bestRequested=requested?.find(feasible)??requested?.[0];
 const requestedState=!bestRequested?"":!feasible(bestRequested)?"unavailable":!bestRequested.risk.deadline_ok?"late":"ok";
 async function calculate(updateLocation=false){
  if(busy)return;
  setBusy(true);onBusyChange?.(true);setError("");
  try{
   let nextVia=add&&!via.includes(add)?[...via,add]:via;
   if(nextVia.length>6)throw Error("Choose no more than six intermediate hubs.");
   setVia(nextVia);setAdd("");
   if(origin===destination)throw Error("Choose different origin and destination hubs.");
   if(!moving&&(!depart||!Number.isFinite(Date.parse(depart))||Date.parse(depart)<=Date.now()))throw Error("Choose a future departure date and time.");
   if(!shipment&&(!deadline||Date.parse(deadline)<=Date.parse(depart)))throw Error("Delivery deadline must be later than departure.");
   if(shipment){
    if(updateLocation){
     const lat=Number(latitude),lon=Number(longitude);
     if(!latitude.trim()||!longitude.trim()||!Number.isFinite(lat)||!Number.isFinite(lon)||lat< -85||lat>85||lon< -180||lon>180)throw Error("Enter valid coordinates from the latest driver report.");
     const positioned=await api.reportPosition(shipment.id,{lat,lon,source:"MANAGER REPORTED",movement_state:stopped?"STOPPED":"MOVING"});
     const oldStops=new Set(shipment.route.slice(1,-1)),remaining=new Set(positioned.vehicle_position?.remaining_path??[]);
     nextVia=nextVia.filter(id=>!oldStops.has(id)||remaining.has(id));setVia(nextVia);onProposed(positioned);
    }
    const s=await api.proposeRoute(shipment.id,{via_hubs:nextVia,...(!moving?{depart_at:new Date(depart).toISOString()}:{})});onProposed(s)
   }
   else{
    const body={origin,destination,via_hubs:nextVia,depart_at:new Date(depart).toISOString(),required_delivery:new Date(deadline).toISOString(),weight_kg:Number(weight),value_eur:Number(value),optimization:"fastest"};
    const r=await api.route(body);setResult(r);setCalculated(body);
    const preferred=r.options.findIndex(o=>o.manager_requested&&feasible(o));setSelected(preferred>=0?preferred:0);
   }
   setDraft(false);onDraftChange?.(false);
  }catch(e){setError(String(e).replace(/^Error:\s*/,""))}finally{setBusy(false);onBusyChange?.(false)}
 }
 async function save(){if(!result||!calculated||busy)return;setBusy(true);onBusyChange?.(true);setError("");try{const chosen=result.options[selected];const s=await api.createShipment({...calculated,planned_departure:calculated.depart_at,selected_path:chosen.path,selected_route_id:chosen.route_id});onCreated(s);setResult(null)}catch(e){setError(String(e))}finally{setBusy(false);onBusyChange?.(false)}}
 return <section className="manager-route-builder" aria-label="Manager route builder">
  <div className="manager-builder-heading"><div><Route size={18}/><h3>{shipment?"Choose your hub connections":"Plan a manager journey"}</h3></div><span>Stops are visited in this order</span></div>
  <form onSubmit={e=>{e.preventDefault();void calculate()}}>
   <fieldset className="manager-builder-fields" disabled={busy||disabled}>
   <div className="manager-route-endpoints"><label>Origin{shipment?<b>{moving?"Reported vehicle position":name(origin)}</b>:<select aria-label="Manager origin" value={origin} onChange={e=>{setOrigin(e.target.value);changeVia([])}}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select>}</label><span>→</span><label>Destination{shipment?<b>{name(destination)}</b>:<select aria-label="Manager destination" value={destination} onChange={e=>{setDestination(e.target.value);changeVia([])}}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select>}</label>{!moving&&<label>Departure<input type="datetime-local" aria-label="Manager departure" value={depart} required onChange={e=>{setDepart(e.target.value);clearDraft()}}/></label>}</div>
   <ol className="manager-hub-stops">{via.map((id,index)=><li key={id}><span className="hub-stop-number">{index+1}</span><b>{name(id)}</b><div><button type="button" aria-label={`Move ${name(id)} earlier`} disabled={index===0||busy} onClick={()=>{const n=[...via];[n[index-1],n[index]]=[n[index],n[index-1]];changeVia(n)}}><ArrowUp size={14}/></button><button type="button" aria-label={`Move ${name(id)} later`} disabled={index===via.length-1||busy} onClick={()=>{const n=[...via];[n[index+1],n[index]]=[n[index],n[index+1]];changeVia(n)}}><ArrowDown size={14}/></button><button type="button" aria-label={`Remove ${name(id)} stop`} disabled={busy} onClick={()=>changeVia(via.filter(n=>n!==id))}><Trash2 size={14}/></button></div></li>)}</ol>
   <div className="manager-add-stop"><label>Intermediate hub<select aria-label="Add intermediate hub" value={add} onChange={e=>{setAdd(e.target.value);clearDraft()}} disabled={busy||via.length>=6}><option value="">Choose a hub</option>{nodes.filter(n=>n.id!==origin&&n.id!==destination&&!via.includes(n.id)).map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select></label><button className="btn btn--ghost" type="button" disabled={!add||busy||via.length>=6} onClick={()=>{changeVia([...via,add]);setAdd("")}}><Plus size={14}/>Add stop</button></div>
   <div className="manager-route-chain">{[moving?"Reported position":name(origin),...via.map(name),name(destination)].join(" → ")}</div>
   {!shipment&&<div className="manager-new-details"><label>Shipment weight · kg<input aria-label="Manager shipment weight" type="number" required min="1" max="23800" value={weight} onChange={e=>{setWeight(e.target.value);clearDraft()}}/></label><label>Shipment value · €<input aria-label="Manager shipment value" type="number" min="0" max="100000000" value={value} onChange={e=>{setValue(e.target.value);clearDraft()}}/></label><label>Deliver by<input aria-label="Manager delivery deadline" type="datetime-local" required value={deadline} onChange={e=>{setDeadline(e.target.value);clearDraft()}}/></label></div>}
   {!moving&&Date.parse(depart)<=Date.now()&&<p className="manager-route-warning">Departure has passed. <button className="linkbtn" type="button" onClick={()=>{setDepart(localInput(new Date(Date.now()+10*60000)));clearDraft()}}>Use a departure in 10 minutes</button></p>}
   {!freshPosition&&<div className="manager-position-update"><b>Current location needed</b><p>Enter the latest driver-reported coordinates to change the remaining journey.</p><div><label>Latitude<input aria-label="Rerouting latitude" type="number" step="any" min="-85" max="85" value={latitude} onChange={e=>setLatitude(e.target.value)}/></label><label>Longitude<input aria-label="Rerouting longitude" type="number" step="any" min="-180" max="180" value={longitude} onChange={e=>setLongitude(e.target.value)}/></label></div><label className="ack"><input type="checkbox" checked={stopped} disabled={!!shipment?.hold} onChange={e=>setStopped(e.target.checked)}/>Vehicle reported stopped</label><button type="button" className="btn btn--ghost" disabled={busy||disabled} onClick={()=>void calculate(true)}>Update location & calculate</button></div>}
   {error&&<p className="manager-route-warning" role="alert">{error}</p>}
   {draft&&shipment&&<p className="manager-draft-note" role="status">Hub connections changed. Calculate the new route before approval.</p>}
   <button className="btn" disabled={busy||disabled||!freshPosition}>{busy?"Calculating connections…":"Calculate requested route & alternatives"}</button>
   </fieldset>
  </form>
  {bestRequested&&<div className={`requested-route-feedback ${requestedState==="ok"?"is-feasible":"is-unavailable"}`} role="status"><div><b>{requestedState==="unavailable"?"Requested connection needs an alternative":requestedState==="late"?"Requested connection is available but misses the delivery deadline":"Requested connection is available"}</b><span>{bestRequested.path.map(name).join(" → ")}</span></div><div className="requested-route-metrics"><span><small>Arrival</small><b>{dt(bestRequested.eta)}</b></span><span><small>Journey time</small><b>{hm(bestRequested.total_minutes)}</b></span><span><small>Distance</small><b>{bestRequested.cost.distance_km} km</b></span><span><small>Fuel</small><b>{bestRequested.cost.fuel_l} L</b></span><span><small>Transport</small><b>{eur(bestRequested.cost.transport_eur)}</b></span></div>{bestRequested.unavailable_reasons?.map(reason=><p key={reason}>{reason}</p>)}{requestedState!=="ok"&&<p>Compare the other options below — each shows its own arrival, journey time and cost.</p>}</div>}
  {result&&<><RouteCompare nodes={nodes} options={result.options} operationalEvents={ops?.events} operationalRevision={ops?.revision} selected={selected} onSelect={setSelected} showJourneyTools={false} weatherZones={ops?.weather_zones}/><div className="manager-save-route"><button className="btn" disabled={busy} onClick={()=>void save()}>Save selected route for review</button></div></>}
 </section>;
}
