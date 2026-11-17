import { useState } from "react";
import { Check, Clock3, History, Pause, Pencil, Save, X } from "lucide-react";
import type { Decision, NetNode } from "../api/types";
import { api } from "../api/client";
import { dt } from "../lib";

export function DecisionHistory({decisions,nodes,onChanged,onRevise,disabled=false}: {
  decisions:Decision[]; nodes:NetNode[]; onChanged:()=>Promise<void>; onRevise:(decision:Decision)=>Promise<void>; disabled?:boolean;
}) {
  const [expanded,setExpanded]=useState(false);
  const [edit,setEdit]=useState<Decision|null>(null),[reason,setReason]=useState("");
  const [saving,setSaving]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const ordered=[...decisions].sort((a,b)=>Date.parse(b.created_at??b.updated_at)-Date.parse(a.created_at??a.updated_at));
  const visible=expanded?ordered:ordered.slice(0,5);
  const name=(id:string)=>nodes.find(n=>n.id===id)?.name??id;
  const labels:Record<string,string>={accept:"Route approved",hold:"Hold / stop requested",keep:"Current plan retained",defer:"Review deferred",stop_request:"Safe stop requested"};

  function start(decision:Decision){setEdit(decision);setReason(decision.reason);setError("");setMessage("")}
  async function save(){
    if(!edit||saving||reason.trim().length<3)return;
    setSaving(true);setError("");
    try{await api.editDecision(edit.id,{reason:reason.trim(),expected_updated_at:edit.updated_at});await onChanged();setEdit(null);setMessage("Decision note updated.")}
    catch(e){setError(String(e).replace(/^Error:\s*/,""));await onChanged()}
    finally{setSaving(false)}
  }
  async function revise(decision:Decision){setError("");setMessage("");try{await onRevise({...decision,reason:reason.trim()||decision.reason});setEdit(null)}catch(e){setError(String(e).replace(/^Error:\s*/,""))}}

  return <section className="card manager-history">
    <div className="section-summary"><h2><History size={19}/>Decision history</h2><span className="count-badge">{decisions.length} decisions</span></div>
    {message&&<p className="decision-history-message" role="status">{message}</p>}
    {error&&<p className="decision-history-message is-error" role="alert">{error}</p>}
    {!visible.length&&<div className="events-empty"><History size={24}/><div><b>No decisions yet</b><p>Approvals and hold decisions appear here with your reason.</p></div></div>}
    <ol className="decision-list">{visible.map(d=>{
      const Icon=d.action==="accept"?Check:d.action==="hold"?Pause:Clock3;
      return <li className={`decision-entry decision-entry--${d.action}`} key={d.id}>
        <span className="decision-symbol"><Icon size={17}/></span>
        <div className="decision-content">
          <div className="decision-entry-heading"><b>{labels[d.action]??d.action}</b><span className="shipment-reference">{d.shipment_id}</span>{d.superseded_by&&<span className="decision-revision-badge">Replaced</span>}{d.supersedes_decision_id&&<span className="decision-revision-badge">Revised decision</span>}</div>
          <p>{d.reason}</p><small>{(d.action==="hold"?d.reviewed_path??d.path:d.path).map(name).join(" → ")}</small>
          {edit?.id===d.id?<form className="decision-edit-form" onSubmit={e=>{e.preventDefault();void save()}}>
            <label>Decision note<textarea aria-label="Edit decision note" required minLength={3} maxLength={1000} value={reason} disabled={saving} onChange={e=>setReason(e.target.value)}/></label>
            <div className="decision-edit-buttons"><button className="btn btn--sm" disabled={saving||disabled||reason.trim().length<3}><Save size={13}/>{saving?"Saving…":"Save note"}</button><button className="btn btn--ghost btn--sm" type="button" disabled={saving||disabled||!!d.superseded_by} onClick={()=>void revise(d)}>Change route or decision</button><button className="linkbtn" type="button" disabled={saving} onClick={()=>{setEdit(null);setError("")}}><X size={13}/>Cancel</button></div>
            <small>Changing the route or action opens the journey for a fresh review.</small>
          </form>:<button className="decision-edit-trigger" disabled={saving||disabled} onClick={()=>start(d)}><Pencil size={12}/>Edit decision</button>}
          {!!d.reason_edits?.length&&<details className="decision-note-history"><summary>Previous notes · {d.reason_edits.length}</summary>{d.reason_edits.map((e,i)=><p key={`${e.at}-${i}`}><span>{e.previous_reason}</span><small>Edited {dt(e.at)}</small></p>)}</details>}
        </div>
        <time dateTime={d.updated_at}>{d.reason_edits?.length?"Updated ":""}{dt(d.updated_at)}</time>
      </li>;
    })}</ol>
    {ordered.length>5&&<button className="history-expand" type="button" aria-expanded={expanded} onClick={()=>setExpanded(v=>!v)}>{expanded?"Show recent decisions":`Show all ${ordered.length} decisions`}</button>}
  </section>;
}
