import { useEffect, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Coffee, Moon } from "lucide-react";
import { api } from "../api/client";
import type { PlanningRules, RouteOption, TransportCalendarDoc } from "../api/types";
import { dt, hm } from "../lib";
import "../transport-calendar.css";

const berlinDay = (value:string) => new Intl.DateTimeFormat("sv-SE", {timeZone:"Europe/Berlin",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date(value));
export function TransportCalendar({departure, rules, onRulesChange, onSelectDate, option}: {
  departure?:string; rules?:PlanningRules; onRulesChange?:(rules:PlanningRules)=>void;
  onSelectDate?:(date:string)=>void; option?:RouteOption;
}) {
  const config=rules??option?.planning_rules??{region:"DE-BW",company_sunday_hold:true,trailer_attached:true};
  const selectedDay=departure?.slice(0,10)??(option?berlinDay(option.depart_at):berlinDay(new Date().toISOString()));
  const [month,setMonth]=useState(()=>selectedDay.slice(0,7));
  const [doc,setDoc]=useState<TransportCalendarDoc|null>(null),[error,setError]=useState("");
  const [refresh,setRefresh]=useState(0);
  const [year,monthNumber]=month.split("-").map(Number);
  useEffect(()=>setMonth(selectedDay.slice(0,7)),[selectedDay]);
  useEffect(()=>{
    let alive=true;setError("");setDoc(null);
    api.transportCalendar(year,monthNumber,config.region,config.company_sunday_hold).then(d=>{if(alive)setDoc(d)}).catch(e=>{if(alive)setError(String(e))});
    return()=>{alive=false};
  },[year,monthNumber,config.region,config.company_sunday_hold,refresh]);
  const steps=option?.steps.filter(step=>["legal_wait","weekend_hold","driver_break","driver_rest","weekly_rest"].includes(step.type))??[];
  const arrivalDay=option?berlinDay(option.eta):selectedDay;
  const move=(delta:number)=>{const next=new Date(Date.UTC(year,monthNumber-1+delta,15));if(next.getUTCFullYear()>=1900&&next.getUTCFullYear()<=2100)setMonth(next.toISOString().slice(0,7))};
  const monthName=new Date(Date.UTC(year,monthNumber-1,15)).toLocaleDateString("en-GB",{month:"long",year:"numeric",timeZone:"UTC"});
  return <details className="transport-calendar" open={!option}>
    <summary><span><CalendarDays size={17}/>{option?"Calendar & driver breaks":"Transport calendar"}</span><small>{option?`${steps.length} planned stops / restrictions`:monthName}</small></summary>
    <div className="transport-calendar-body">
      {onRulesChange&&<div className="calendar-rule-settings">
        <label>Holiday region<select aria-label="Holiday region" value={config.region} onChange={e=>onRulesChange({...config,region:e.target.value})}>{(doc?.regions??[{id:config.region,name:config.region}]).map(r=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
        <label className="calendar-check"><input type="checkbox" checked={config.trailer_attached} onChange={e=>onRulesChange({...config,trailer_attached:e.target.checked})}/>Trailer attached</label>
        <label className="calendar-check"><input type="checkbox" checked={config.company_sunday_hold} onChange={e=>onRulesChange({...config,company_sunday_hold:e.target.checked})}/>Company hold · Sat 15:00 to Mon 05:00</label>
      </div>}
      <div className="calendar-layout"><div>
        <div className="calendar-month-nav"><button type="button" aria-label="Previous calendar month" onClick={()=>move(-1)}><ChevronLeft size={17}/></button><h3>{monthName}</h3><button type="button" aria-label="Next calendar month" onClick={()=>move(1)}><ChevronRight size={17}/></button></div>
        {error?<div role="alert">Calendar unavailable. {error}<button type="button" className="linkbtn" onClick={()=>setRefresh(v=>v+1)}>Retry</button></div>:!doc?<p role="status">Loading calendar…</p>:<>
          <div className="calendar-grid" aria-label={`${monthName} transport calendar`}>
            {["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].map(d=><b key={d} className="calendar-weekday">{d}</b>)}
            {Array.from({length:doc.days[0].weekday},(_,i)=><span key={`blank-${i}`}/>)}
            {doc.days.map(day=>{
              const inJourney=option&&day.date>=selectedDay&&day.date<=arrivalDay;
              const companyHours=day.company_hold ? (day.weekday===5 ? "from 15:00" : day.sunday ? "all day" : "until 05:00") : "";
              const description=`${day.date}${day.holiday?` · ${day.holiday}`:""}${day.truck_ban?" · Truck ban 00:00–22:00":""}${companyHours?` · Company hold ${companyHours}`:""}${day.summer_route_review?" · Summer road restrictions: review required":""}`;
              return <button type="button" key={day.date} aria-label={description} aria-pressed={day.date===selectedDay} title={description}
                className={`calendar-day ${day.truck_ban?"is-ban":day.holiday?"is-holiday":""} ${inJourney?"is-journey":""} ${day.date===selectedDay?"is-selected":""}`}
                onClick={()=>onSelectDate?.(day.date)}><b>{Number(day.date.slice(-2))}</b><small>{day.truck_ban?"Ban 0–22":day.summer_route_review?"Review":day.holiday?"Holiday":companyHours?"Company hold":""}</small></button>;
            })}
          </div>
          <div className="calendar-key"><span>Red · driving ban</span><span>Blue · public holiday without this ban</span>{option&&<span>Green border · journey dates</span>}</div>
          <ul className="calendar-holidays">{doc.days.filter(d=>d.holiday).map(d=><li key={d.date}><b>{d.date.slice(-2)} · {d.holiday}</b><span>{d.truck_ban?"Truck ban 00:00–22:00":"No additional StVO §30 truck ban"}</span></li>)}</ul>
        </>}
      </div><aside className="calendar-driver-rules">
        <h3><Coffee size={17}/>Driver planning</h3><p><b>45 min break</b><span>After at most 4½ hours of driving.</span></p><p><b>9 hours driving</b><span>Conservative daily limit; no 10-hour extensions assumed.</span></p><p><b><Moon size={15}/>11 hours daily rest</b><span>Regular rest, carried across hub connections.</span></p>
        {option?.driver_plan&&<p className="calendar-assumption">{option.driver_plan.assumption} Planned rest during parked waiting must be confirmed.</p>}
        {!option&&<p className="calendar-assumption">Assumes one fully rested driver. Loading is work, not a driving break. Duty-roster and working-time checks require manager review.</p>}
        <p><b>Weekly limits</b><span>56h per week · 90h per fortnight. Regular weekly rest: 45h outside the vehicle.</span></p>
        <p className="calendar-scope">{doc?.scope??"Calendar uses the selected German federal state."}</p>
        {doc?.days.some(d=>d.summer_route_review)&&<p className="calendar-review">July/August Saturdays: specified roads have additional 07:00–20:00 restrictions. Review the road before dispatch.</p>}
      </aside></div>
      {!!steps.length&&<ol className="calendar-journey-stops">{steps.map((step,i)=><li key={`${step.start}-${i}`}><b>{step.type.replace(/_/g," ")} · {hm(step.minutes)}</b><span>{dt(step.start)} → {dt(step.end)}</span><small>{step.detail}</small></li>)}</ol>}
      <div className="calendar-sources"><a href="https://www.gesetze-im-internet.de/stvo_2013/__30.html" target="_blank" rel="noreferrer">German truck-ban rules</a><a href="https://transport.ec.europa.eu/transport-modes/road/social-provisions/driving-time-and-rest-periods_en" target="_blank" rel="noreferrer">EU driving and rest rules</a><span>Europe/Berlin · special exemptions and municipal holidays require review</span></div>
    </div>
  </details>;
}
