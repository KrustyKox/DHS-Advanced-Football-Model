"""Team constrained NBA projection baseline. Unvalidated for betting."""
import math
import requests

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team}/schedule"


def recent_team_scores(team, season, before_date, limit=12):
    """Historical completed team scores, strictly prior to the chosen game date."""
    response = requests.get(URL.format(team=team.lower()), params={"season": int(season)},
                            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=18)
    response.raise_for_status()
    games = []
    for event in response.json().get("events", []):
        date = str(event.get("date", ""))[:10]
        if not date or date >= str(before_date):
            continue
        competition = (event.get("competitions") or [{}])[0]
        status = (event.get("status") or {}).get("type") or (competition.get("status") or {}).get("type") or {}
        if not status.get("completed"):
            continue
        own = next((entry for entry in competition.get("competitors", [])
                    if str((entry.get("team") or {}).get("abbreviation", "")).lower() == team.lower()), None)
        if not own:
            continue
        raw = own.get("score")
        try:
            value = float(raw.get("value") if isinstance(raw, dict) else raw)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and 40 <= value <= 200:
            games.append((date, value))
    games.sort(reverse=True)
    return [value for _, value in games[:limit]]


def allocate(rows, target):
    """Enforce a 240-minute regulation budget and distribute scoring shares."""
    if len(rows) < 5:
        raise ValueError("At least five players with complete logs are needed")
    if not 70 <= target <= 160:
        raise ValueError("Historical scoring target outside supported range (70–160)")
    data = [dict(r) for r in rows]
    if any(not isinstance(r.get("MIN"), (int, float)) or
           not isinstance(r.get("PTS"), (int, float)) or
           not math.isfinite(r["MIN"]) or not math.isfinite(r["PTS"]) or
           r["MIN"] <= 0 or r["PTS"] < 0 for r in data):
        raise ValueError("Missing/invalid minutes or points")
    raw_minutes = sum(r["MIN"] for r in data)
    raw_points = sum(r["PTS"] for r in data)
    remaining = list(range(len(data)))
    minutes = [0.0] * len(data)
    budget = 240.0
    while remaining:
        denominator = sum(data[i]["MIN"] for i in remaining)
        capped = [i for i in remaining if budget * data[i]["MIN"] / denominator > 40]
        if not capped:
            for i in remaining:
                minutes[i] = budget * data[i]["MIN"] / denominator
            break
        for i in capped:
            minutes[i] = 40.0
            budget -= 40.0
        remaining = [i for i in remaining if i not in capped]
    scoring = []
    for row, minutes_new in zip(data, minutes):
        factor = minutes_new / row["MIN"]
        scoring.append(row["PTS"] * factor)
        row["MIN"] = round(minutes_new, 2)
        for stat in ("REB", "AST", "3PM", "STL", "BLK", "TOV"):
            if isinstance(row.get(stat), (int, float)):
                row[stat] = round(row[stat] * factor, 2)
    if sum(scoring) <= 0:
        raise ValueError("No usable scoring rates")
    for row, weight in zip(data, scoring):
        row["PTS"] = round(target * weight / sum(scoring), 2)
        for name, parts in {"PRA": ("PTS","REB","AST"), "PR": ("PTS","REB"),
                            "PA": ("PTS","AST"), "RA": ("REB","AST")}.items():
            if all(isinstance(row.get(k), (int,float)) for k in parts):
                row[name] = round(sum(row[k] for k in parts), 2)
    return data, {"raw_points": round(raw_points, 1), "raw_minutes": round(raw_minutes, 1),
                  "team_points": round(sum(r["PTS"] for r in data), 1),
                  "team_minutes": round(sum(r["MIN"] for r in data), 1)}
