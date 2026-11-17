import type {ArrivalEvidence as Evidence} from "../api/types";
import {dt} from "../lib";

export function ArrivalEvidence({evidence:e}:{evidence?:Evidence}) {
 if(!e)return null;
 return <details className="capacity-evidence" open><summary>Arrival reliability · {e.samples} matched reported deliveries</summary>{e.status==="EMPIRICAL"?<><p><b>Observed-error arrival range</b><br/>{dt(e.window_start)} → {dt(e.window_end)}</p><p>Median arrival error: {e.median_error_minutes} min · mean absolute error: {e.arrival_mae_minutes} min</p></>:<p>{e.samples} of {e.minimum_samples} matched outcomes needed to show a lane-specific arrival range. Record actual outcomes to build this evidence.</p>}<p className="fineprint">{e.source}<br/>{e.note}</p></details>;
}
