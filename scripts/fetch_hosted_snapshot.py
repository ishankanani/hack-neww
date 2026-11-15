"""Bundle an explicitly uploaded data snapshot without committing it to GitHub."""
import gzip
import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlparse


def main():
    url=os.environ.get("HOSTED_SNAPSHOT_URL")
    if not url:
        print("No hosted snapshot configured; starting with an empty hosted store.")
        return
    expected=os.environ.get("HOSTED_SNAPSHOT_SHA1","")
    if urlparse(url).scheme!="https" or len(expected)!=40:
        raise ValueError("Snapshot requires HTTPS and an expected file digest")
    with urlopen(url,timeout=60) as response:blob=response.read(50*1024*1024+1)
    if len(blob)>50*1024*1024 or hashlib.sha1(blob).hexdigest()!=expected:
        raise ValueError("Uploaded snapshot integrity check failed")
    records=json.loads(gzip.decompress(blob))
    for name,value in records.items():
        path=Path(name)
        if path.is_absolute() or ".." in path.parts or not name.endswith(".json") or not isinstance(value,dict):
            raise ValueError("Invalid snapshot member")
        if name not in {"shipments.json","operations.json"} and not (len(path.parts)==3 and path.parts[0]=="demo" and path.parts[-1]=="operations.json"):
            raise ValueError("Unexpected snapshot member")
    target=Path(__file__).resolve().parents[1]/"data"
    target.mkdir(exist_ok=True)
    (target/"hosted_snapshot.json.gz").write_bytes(blob)
    manifest={"sha1":expected,"shipments":len(records["shipments.json"]),"events":len(records["operations.json"].get("events",[])),"weather_zones":len(records["operations.json"].get("weather_zones",[])),"decisions":len(records["operations.json"].get("decisions",[])),"files":sorted(records)}
    (target/"hosted_snapshot.manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    print(f"Bundled previous dataset: {manifest['shipments']} journeys, {manifest['events']} events, {manifest['weather_zones']} weather zones.")


if __name__=="__main__":main()
