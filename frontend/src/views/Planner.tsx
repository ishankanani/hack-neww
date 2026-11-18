import { useEffect, useRef, useState } from "react";
import { ArrowUpRight, ArrowRightLeft, ShieldCheck, Loader2, Save } from "lucide-react";
import { api } from "../api/client";
import type { NetNode, RouteResp, Operations, TruckProfile, WeatherZoneInput, JourneyExample, Shipment } from "../api/types";
import { RouteCompare } from "../components/RouteCompare";
import { SavedJourneys } from "../components/SavedJourneys";
import { localInput } from "../lib";
type TruckInput = Record<keyof TruckProfile, string>;
const truckRules = [
 ["height_m", "Height", 1.5, 4.5],
 ["width_m", "Width", 1.5, 2.6],
 ["length_m", "Length", 3, 20],
 ["gross_weight_kg", "Gross vehicle weight", 1000, 50000],
] as const;
function rangeError(raw:string,min:number,max:number,label:string){
 if(!raw.trim())return `${label} is required.`;
 const n=Number(raw);
 if(!Number.isFinite(n))return `Enter a valid ${label.toLowerCase()}.`;
 if(n<min||n>max)return `${label} must be between ${min.toLocaleString()} and ${max.toLocaleString()}${label.includes("weight")?" kg":""}.`;
 return "";
}
function validatePlannerInputs(v:{origin:string;destination:string;depart:string;deadline:string;weight:string;value:string;truck:TruckInput}){
 const errors:Record<string,string>={};
 if(v.origin===v.destination)errors.destination="Choose a destination different from the origin.";
 if(!v.depart)errors.depart="Choose a departure date and time.";
 else if(!Number.isFinite(Date.parse(v.depart)))errors.depart="Enter a valid departure date and time.";
 if(v.deadline&&!Number.isFinite(Date.parse(v.deadline)))errors.deadline="Enter a valid delivery deadline.";
 else if(v.deadline&&v.depart&&Date.parse(v.deadline)<=Date.parse(v.depart))errors.deadline="Delivery deadline must be later than departure.";
 errors.weight=rangeError(v.weight,1,23800,"Shipment weight");
 if(!v.value.trim())errors.value="";
 else errors.value=rangeError(v.value,0,100000000,"Shipment value");
 for(const [key,label,min,max] of truckRules)errors[key]=rangeError(v.truck[key],min,max,label);
 const weight=Number(v.weight),gross=Number(v.truck.gross_weight_kg);
 if(Number.isFinite(weight)&&Number.isFinite(gross)&&weight>gross)errors.gross_weight_kg="Gross vehicle weight must be at least the shipment weight.";
 return Object.fromEntries(Object.entries(errors).filter(([,message])=>message)) as Record<string,string>;
}
export function Planner({nodes,revision,onChange,onReview,onSaved}:{nodes:NetNode[];revision:number;onChange:()=>void;onReview:(id?:string)=>void;onSaved?:(shipment:Shipment)=>void}){
 const [origin,setOrigin]=useState("R16"),[dest,setDest]=useState("R21");
 const [depart,setDepart]=useState(()=>localInput(new Date())),[deadline,setDeadline]=useState(()=>localInput(new Date(Date.now()+3*86400000)));
 const [weight,setWeight]=useState("12000"),[value,setValue]=useState("180000");
 const [resp,setResp]=useState<RouteResp|null>(null),[ops,setOps]=useState<Operations|null>(null);
 const [loading,setLoading]=useState(false),[saving,setSaving]=useState(false),[err,setErr]=useState(""),[message,setMessage]=useState("");
 const [selected,setSelected]=useState(0);
 const [saveTick,setSaveTick]=useState(0);
 const selection=useRef<string|undefined>();selection.current=resp?.options[selected]?.route_id;
 const [optimization,setOptimization]=useState("fastest");
 const plannerPanel=useRef<HTMLElement|null>(null);
 const [refreshing,setRefreshing]=useState(false);
 const [sample,setSample]=useState<JourneyExample|null>(null),[sampleWeather,setSampleWeather]=useState(false);
 const [truck,setTruck]=useState<TruckInput>({height_m:"4",width_m:"2.55",length_m:"16.5",gross_weight_kg:"40000"});
 const truckProfile:TruckProfile={height_m:Number(truck.height_m),width_m:Number(truck.width_m),length_m:Number(truck.length_m),gross_weight_kg:Number(truck.gross_weight_kg)};
 const inputErrors=validatePlannerInputs({origin,destination:dest,depart,deadline,weight,value,truck});
 const inputInvalid=Object.keys(inputErrors).length>0;
 const requestId=useRef(0);const lastBody=useRef<Parameters<typeof api.route>[0]|null>(null);
 const running=useRef(false),mounted=useRef(true),latestBody=useRef("");
 const preferClear=useRef(false);
 const pendingRefresh=useRef(false);const autoRun=useRef(false);
 // Sample results are reused for 5 minutes so switching between samples is instant.
 const sampleCache=useRef(new Map<string,{at:number;r:Awaited<ReturnType<typeof api.route>>}>());const latestGo=useRef<(automatic?:boolean)=>Promise<void>>(async()=>{});
 const wantedRevision=useRef(revision);wantedRevision.current=Math.max(wantedRevision.current,revision);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;requestId.current++}},[]);
 const body=()=>({origin,destination:dest,depart_at:new Date(depart).toISOString(),required_delivery:deadline?new Date(deadline).toISOString():undefined,weight_kg:Number(weight),value_eur:value.trim()?Number(value):0,optimization,truck:truckProfile,...(sample?{sample_id:sample.id,sample_weather:sampleWeather}:{})});
 try{latestBody.current=JSON.stringify(body())}catch{latestBody.current="invalid"}
 async function go(automatic=false){
  if(inputInvalid)return;
  if(running.current){if(automatic)pendingRefresh.current=true;return}running.current=true;
  const id=++requestId.current;if(automatic)setRefreshing(true);else setLoading(true);setErr("");if(!automatic)setMessage("");
  const selectedRoute=selection.current;
  let completedRevision=-1,completedKey="";
  try{const b=body();const key=JSON.stringify(b);
   const hit=b.sample_id?sampleCache.current.get(key):undefined;
   const r=hit&&Date.now()-hit.at<300000?hit.r:await api.route(b);
   if(b.sample_id&&!(hit&&Date.now()-hit.at<300000))sampleCache.current.set(key,{at:Date.now(),r});
   completedRevision=r.revision??-1;completedKey=key;
   if(mounted.current&&id===requestId.current&&key===latestBody.current){
    if(!b.sample_id&&completedRevision<wantedRevision.current){pendingRefresh.current=true;return}
    const safeIndex=r.options.findIndex(o=>(o.avoidance_status==="CLEAR"||o.avoidance_status==="NO_ZONE")&&o.capacity?.feasible!==false);
    const previousIndex=r.options.findIndex(o=>o.route_id===selection.current);
    const samePathIndex=r.options.findIndex(o=>o.route_id?.split(":")[0]===selectedRoute?.split(":")[0]);
    setResp(r);
    setSelected(automatic?(preferClear.current&&safeIndex>=0?safeIndex:previousIndex>=0?previousIndex:safeIndex>=0?safeIndex:samePathIndex>=0?samePathIndex:0):safeIndex>=0?safeIndex:0);
    preferClear.current=false;lastBody.current=b
   }
  }catch(e){if(mounted.current&&id===requestId.current)setErr(String(e))}
  finally{
   running.current=false;if(mounted.current&&id===requestId.current){setLoading(false);setRefreshing(false)}
   if(mounted.current&&pendingRefresh.current){
    pendingRefresh.current=false;
    // A weather edit and workspace refresh often ask for the same revision.
    // Queue another search only when the finished result is actually outdated.
    if(completedRevision<wantedRevision.current||completedKey!==latestBody.current)void latestGo.current(true);
   }
  }
 }

 latestGo.current=go;
 // Loading a sample or switching its weather preview calculates straight away; the current map stays until the new result arrives.
 useEffect(()=>{if(autoRun.current&&sample){autoRun.current=false;void go()}},[sample,sampleWeather]);
 useEffect(()=>{let active=true;api.operations().then(r=>{if(active)setOps(r)}).catch(e=>{if(active)setErr(String(e))});return()=>{active=false}},[revision]);
 useEffect(()=>{if(resp&&(resp.revision??-1)<revision&&JSON.stringify(lastBody.current)===latestBody.current) void go(true)},[revision]);
 async function scenarioChanged(){const o=await api.operations();setOps(o);onChange();if(!resp)await go()}
 async function weatherChanged(preferClearRoute=true){preferClear.current=preferClearRoute;const o=await api.operations();wantedRevision.current=Math.max(wantedRevision.current,o.revision);setOps(o);onChange();await go(true)}
 async function addZone(body:WeatherZoneInput){await api.addWeatherZone(body);await weatherChanged()}
 async function updateZone(id:string,body:WeatherZoneInput){await api.updateWeatherZone(id,body);await weatherChanged()}
 async function deleteZone(id:string){await api.deleteWeatherZone(id);await weatherChanged(false)}
 async function cancelWeatherZones(ids:string[]){
  try{for(const id of ids) await api.deleteWeatherZone(id)}
  finally{await weatherChanged(false)}
 }
 async function save(recommended=false){if(inputInvalid)return;setSaving(true);setErr("");try{const b=lastBody.current;if(!b)throw Error("Calculate a route first");const chosen=resp?.options[recommended?(resp.recommended??0):selected];const ship=await api.createShipment({...b,planned_departure:b.depart_at,selected_path:chosen?.path,selected_route_id:chosen?.route_id});onSaved?.(ship);setMessage(`${ship.id} saved. It is listed below and in the control room review queue.`);setSaveTick(n=>n+1);onChange()}catch(e){setErr(String(e))}finally{setSaving(false)}}
 const dirty=resp&&JSON.stringify(lastBody.current)!==JSON.stringify((()=>{try{return body()}catch{return null}})());
 const refreshLatest=useRef(()=>{});refreshLatest.current=()=>{if(resp&&!sample&&!dirty&&!running.current&&!saving&&!document.hidden&&plannerPanel.current?.offsetParent)void go(true)};
 useEffect(()=>{const timer=setInterval(()=>refreshLatest.current(),120000);return()=>clearInterval(timer)},[]);
 return <>
 <section className="card planning-card" ref={plannerPanel}>
  <div className="card__h"><div><h2>Plan a journey</h2></div></div>
  {sample&&<div className="example-preview"><div><b>Sample simulation · {sample.title}</b><span>{sampleWeather?"Sample weather applied.":"Without weather."} {(()=>{const o=resp?.options?.[0];if(!o)return null;const live=(o.live_weather??[]).filter(w=>w.status==="FORECAST").length;const t=o.traffic_status==="LIVE_OR_PREDICTED"?"live (TomTom)":"simulated — add a TomTom key for live traffic";return <>Roads: {(o.road_legs??[]).some(l=>/OSRM|TomTom/.test(l.source??""))?"live":"estimated"} · Weather forecast: {live?`live (Open-Meteo, ${live} points)`:"not available"} · Traffic: {t}</>})()}</span></div>{sample.weather_zone_count>0&&<label><input type="checkbox" checked={sampleWeather} disabled={loading||refreshing} onChange={e=>{autoRun.current=true;setSampleWeather(e.target.checked)}}/>Preview weather impact</label>}<button className="linkbtn" disabled={loading||refreshing} onClick={()=>{setSample(null);setSampleWeather(false);setResp(null)}}>Exit sample</button></div>}
  <form onSubmit={e=>{e.preventDefault();void go()}}>
   {inputInvalid&&<div className="planner-validation" role="alert"><b>Route search paused.</b> Correct the highlighted entries before calculating or selecting routes.</div>}
   <div className="plan-fields">
    <label>Origin<select aria-label="Origin" value={origin} onChange={e=>setOrigin(e.target.value)}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
    <button type="button" className="swap-button" aria-label="Swap origin and destination" onClick={()=>{setOrigin(dest);setDest(origin)}}><ArrowRightLeft size={16}/></button>
    <label>Destination<select aria-label="Destination" aria-invalid={!!inputErrors.destination} value={dest} onChange={e=>setDest(e.target.value)}>{nodes.map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select>{inputErrors.destination&&<small className="field-error">{inputErrors.destination}</small>}</label>
    <label>Departure · local time<input required aria-label="Departure" aria-invalid={!!inputErrors.depart} type="datetime-local" value={depart} onChange={e=>setDepart(e.target.value)}/>{inputErrors.depart&&<small className="field-error">{inputErrors.depart}</small>}</label>
    <button className="btn btn--mint" disabled={loading||refreshing||inputInvalid||!nodes.length}>{loading?<Loader2 className="spin" size={17}/>:<ArrowUpRight size={17}/>} {loading?"Calculating…":"Find best routes"}</button>
   </div>
   <details className="shipment-settings" open>
    <summary>Shipment details &amp; optimization <span>{weight} kg · {optimization}</span></summary>
    <div className="plan-secondary">
     <label>Weight · kg<input aria-label="Weight kg" aria-invalid={!!inputErrors.weight} required type="number" min="1" max="23800" step="1" value={weight} onChange={e=>setWeight(e.target.value)}/>{inputErrors.weight&&<small className="field-error">{inputErrors.weight}</small>}</label>
     <label>Shipment value · €<input aria-label="Shipment value" aria-invalid={!!inputErrors.value} type="number" min="0" max="100000000" step="0.01" value={value} onChange={e=>setValue(e.target.value)}/>{inputErrors.value&&<small className="field-error">{inputErrors.value}</small>}</label>
     <label>Deliver by · local time<input aria-label="Deliver by" aria-invalid={!!inputErrors.deadline} type="datetime-local" value={deadline} onChange={e=>setDeadline(e.target.value)}/>{inputErrors.deadline&&<small className="field-error">{inputErrors.deadline}</small>}</label>
     <label>Optimize for<select aria-label="Optimization goal" value={optimization} onChange={e=>setOptimization(e.target.value)}><option value="fastest">Fastest arrival</option><option value="cost">Lowest cost within deadline</option><option value="balanced">Balanced · €50 per transit hour</option></select></label>
    </div>
   </details>
   <details className="truck-settings" open>
    <summary>Truck details</summary>
    <div className="truck-fields">{truckRules.map(([key,label,min,max])=><label key={key}>{label}{key==="gross_weight_kg"?" (kg)":" (m)"}<input aria-label={label} aria-invalid={!!inputErrors[key]} required type="number" min={min} max={max} step="any" value={truck[key]} onChange={e=>setTruck({...truck,[key]:e.target.value})}/>{inputErrors[key]&&<small className="field-error">{inputErrors[key]}</small>}</label>)}</div>
   </details>
  </form>
 </section>
 {err&&<div role="alert" className="notice notice--warn">{err}</div>}{message&&<div role="status" className="notice notice--info">{message}<button className="linkbtn" onClick={()=>onReview()}>Open control room ↗</button></div>}
 {resp&&!inputInvalid?<section className={`card results-card ${loading?"is-updating":""}`}>{dirty&&<div className="notice notice--warn">Inputs changed. Calculate again to update these results.</div>}<RouteCompare nodes={nodes} options={resp.options} savings={resp.savings} operationalEvents={resp.sample?[]:ops?.events} operationalRevision={resp.sample?undefined:ops?.revision} selected={selected} onSelect={setSelected} onRefresh={()=>{if(!running.current)void go(true)}} deadline={deadline?new Date(deadline).toISOString():null} truck={truckProfile} onScenario={resp.sample?undefined:()=>{void scenarioChanged()}} weatherZones={resp.sample?resp.weather_zones:ops?.weather_zones} onAddWeatherZone={resp.sample?undefined:addZone} onUpdateWeatherZone={resp.sample?undefined:updateZone} onDeleteWeatherZone={resp.sample?undefined:deleteZone} onCancelWeatherZones={resp.sample?undefined:cancelWeatherZones} showJourneyTools={!resp.sample}/>{refreshing&&<div className="route-refresh-status" role="status">Updating estimates…</div>}{!resp.sample&&<div className="results-actions"><span><ShieldCheck size={16}/> Updated estimates · Manager approval before dispatch.</span><button className="btn btn--ghost" onClick={()=>onReview()}>Open control room</button><button className="btn btn--ghost" disabled={saving||loading||refreshing||!!dirty||resp.revision!==revision||resp.recommended===null} onClick={()=>save(true)}>Save recommended</button><button className="btn" disabled={saving||loading||refreshing||!!dirty||resp.revision!==revision} onClick={()=>save(false)}><Save size={15}/>{saving?"Saving…":"Save plan for review"}</button></div>}</section>:null}
 <SavedJourneys nodes={nodes} refreshKey={saveTick} onReview={onReview}/>
 </>
}
