from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _utc(value: Any) -> datetime | None:
    try:
        stamp=pd.Timestamp(value)
        if pd.isna(stamp): return None
        if stamp.tzinfo is None: stamp=stamp.tz_localize("UTC")
        return stamp.tz_convert("UTC").to_pydatetime()
    except Exception:
        return None


def update_locks(path: Path, projections: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    existing=[]
    if path.exists():
        try: existing=json.loads(path.read_text(encoding="utf-8")).get("games",[])
        except Exception: existing=[]
    by_id={str(x.get("game_id")):x for x in existing}
    for projection in projections:
        gid=str(projection.get("game_id")); kickoff=_utc(projection.get("kickoff"))
        if not gid or kickoff is None: continue
        if kickoff > now:
            snapshot=dict(projection);snapshot["snapshot_at"]=now.isoformat();snapshot["kickoff_locked"]=False
            by_id[gid]=snapshot
        elif gid in by_id:
            by_id[gid]["kickoff_locked"]=True
    for snapshot in by_id.values():
        kickoff=_utc(snapshot.get("kickoff"))
        if kickoff is not None and kickoff <= now:snapshot["kickoff_locked"]=True
    games=sorted(by_id.values(),key=lambda x:(x.get("kickoff", ""),x.get("game_id", "")))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"updated_at":now.isoformat(),"games":games},indent=2,default=str),encoding="utf-8")
    return games
