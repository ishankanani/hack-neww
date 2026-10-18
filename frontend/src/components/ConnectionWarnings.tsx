import type {ConnectionWarning,NetNode} from "../api/types";
import {dt,hm} from "../lib";

export function ConnectionWarnings({connections=[],nodes}:{connections?:ConnectionWarning[];nodes:NetNode[]}) {
 const name=(id:string)=>nodes.find(n=>n.id===id)?.name??id;
 if(!connections.length)return null;
 return <section className="connection-panel"><h3>Hub connections &amp; departure cutoffs</h3>{connections.map((c,i)=><article className={`connection-row ${c.status==="ON TRACK"?"":"connection-risk"}`} key={`${c.service_id}-${i}`}><div><b>{name(c.from)} → {name(c.to)}</b><span className="mini">{c.status}</span></div><dl><div><dt>Hub arrival</dt><dd>{dt(c.arrival)}</dd></div><div><dt>Ready after handling</dt><dd>{dt(c.ready_at)}</dd></div><div><dt>Loading cutoff</dt><dd>{dt(c.cutoff_at)}</dd></div><div><dt>Service departure</dt><dd>{dt(c.departure)}</dd></div></dl><p>{c.status==="MISSED"?`Previously approved departure ${dt(c.previous_departure)} is missed. Next service adds ${hm(c.connection_delay_minutes)}.`:`${hm(c.buffer_minutes)} readiness buffer before cutoff · ${hm(c.wait_minutes)} total service wait.`}</p><small>{c.source}</small></article>)}</section>;
}
