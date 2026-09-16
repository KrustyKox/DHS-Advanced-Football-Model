from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
for league in ("nfl","cfb"):
    path=ROOT/"data"/"output"/f"{league}.json";data=json.loads(path.read_text())
    assert isinstance(data.get("games"),list);assert data.get("generated_at");assert int(data.get("feature_count",0))>5
    for game in data["games"]:
        for key in ("game_id","kickoff","home","away","projected_margin_home","projected_total","home_win_probability","data_reliability"):assert key in game
print("Output validation passed")

underdogs=json.loads((ROOT/"data"/"output"/"underdog_ml_picks.json").read_text())
assert isinstance(underdogs.get("picks"),list)
cannot_miss=json.loads((ROOT/"data"/"output"/"cannot_miss.json").read_text())
assert len(cannot_miss.get("current",[]))==2
assert all(row.get("status") in {"QUALIFIED","PASS"} for row in cannot_miss["current"])
