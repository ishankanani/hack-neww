import { useEffect, useState } from "react";
import { FlaskConical } from "lucide-react";
import { api } from "../api/client";
import type { JourneyExample } from "../api/types";

export function JourneyExamples({ onLoad, disabled }: { onLoad:(example:JourneyExample)=>void; disabled:boolean }) {
  const [examples,setExamples]=useState<JourneyExample[]>([]);
  const [selected,setSelected]=useState("");
  const [error,setError]=useState("");
  useEffect(()=>{let active=true;api.journeyExamples().then(r=>{if(active){setExamples(r.examples);setSelected(r.examples[0]?.id??"")}}).catch(()=>{if(active)setError("Sample journeys are unavailable.")});return()=>{active=false}},[]);
  const chosen=examples.find(e=>e.id===selected);
  return <details className="journey-examples"><summary><FlaskConical size={14}/>Sample journeys <span>{examples.length} scenarios</span></summary>
    <div className="example-picker"><label>Choose a sample<select aria-label="Sample journey" value={selected} onChange={e=>setSelected(e.target.value)}>{examples.map(e=><option key={e.id} value={e.id}>{e.title}</option>)}</select></label>
      <button type="button" className="btn btn--ghost" disabled={disabled||!chosen} onClick={()=>{if(chosen)onLoad(chosen)}}>Load sample</button></div>
    {error&&<p role="status">{error}</p>}
  </details>;
}
