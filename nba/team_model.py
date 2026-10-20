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


def allocate(rows, target, histories=None, rotation_size=10):
    """Select likely rotation from observed recent minutes; conserve 240 minutes.

    History includes only completed games prior to tipoff, supplied by caller.
    Rotation is an estimate, NOT verified starters or confirmed active players.
    """
    if len(rows) < 8:
        raise ValueError("Need at least eight eligible players for rotation allocation")
    if not 70 <= target <= 160:
        raise ValueError("Team target outside supported 70–160 point range")
    histories = histories or {}
    data = [dict(row) for row in rows]
    for row in data:
        m = row.get("MIN")
        if not isinstance(m, (int, float)) or not math.isfinite(m) or m <= 0:
            raise ValueError("Missing valid historical minutes")
        games = histories.get(row["Player"], [])
        recent = [float(g["MIN"]) for g in games[:10]
                  if isinstance(g.get("MIN"), (int, float)) and
                  math.isfinite(g["MIN"]) and g["MIN"] >= 0]
        recent_five = recent[:5]
        # Recent rotation usage is a better signal than career averages.
        row["Recent MIN"] = round(sum(recent_five)/len(recent_five), 1) if recent_five else round(m, 1)
        row["Historical MIN"] = round(m, 1)
        row["_minutes_weight"] = (0.7 * row["Recent MIN"] + 0.3 * m)
    data.sort(key=lambda r: r["_minutes_weight"], reverse=True)
    rotation = data[:min(rotation_size, len(data))]
    # If no dependable rotation exists, fail rather than invent active players.
    if len(rotation) < 8:
        raise ValueError("Insufficient rotation")
    original_points = sum(r.get("PTS", 0) for r in data)
    original_minutes = sum(r["MIN"] for r in data)
    remaining = list(range(len(rotation)))
    minutes = [0.0] * len(rotation)
    budget = 240.0
    while remaining:
        denom = sum(rotation[i]["_minutes_weight"] for i in remaining)
        if denom <= 0:
            raise ValueError("No usable rotation minutes")
        capped = [i for i in remaining if budget * rotation[i]["_minutes_weight"] / denom > 40]
        if not capped:
            for i in remaining:
                minutes[i] = budget * rotation[i]["_minutes_weight"] / denom
            break
        for i in capped:
            minutes[i] = 40.0
            budget -= 40.0
        remaining = [i for i in remaining if i not in capped]
    scoring_weights = []
    for row, new_minutes in zip(rotation, minutes):
        historical_minutes = row["Historical MIN"]
        row["Projected MIN"] = round(new_minutes, 2)
        row["MIN"] = round(new_minutes, 2)
        # Non-scoring stats preserve individual per-minute rates, without
        # being forced to match team scoring (REB/AST aren't conserved like PTS).
        ratio = new_minutes / historical_minutes
        for stat in ("REB", "AST", "3PM", "STL", "BLK", "TOV"):
            if isinstance(row.get(stat), (int, float)):
                row["Historical " + stat] = row[stat]
                row[stat] = round(row[stat] * ratio, 2)
        scoring_weights.append(max(0, row.get("PTS", 0) * ratio))
    denom = sum(scoring_weights)
    if denom <= 0:
        raise ValueError("No usable scoring opportunities")
    for row, weight in zip(rotation, scoring_weights):
        row["Historical PTS"] = row.get("PTS")
        row["PTS"] = round(target * weight / denom, 2)
        for name, parts in {"PRA": ("PTS", "REB", "AST"), "PR": ("PTS", "REB"),
                            "PA": ("PTS", "AST"), "RA": ("REB", "AST")}.items():
            if all(isinstance(row.get(part), (int, float)) for part in parts):
                row[name] = round(sum(row[part] for part in parts), 2)
        row.pop("_minutes_weight", None)
    return rotation, {
        "raw_points": round(original_points, 1),
        "raw_minutes": round(original_minutes, 1),
        "team_points": round(sum(r["PTS"] for r in rotation), 1),
        "team_minutes": round(sum(r["MIN"] for r in rotation), 1),
        "rotation_count": len(rotation),
        "omitted_players": [r["Player"] for r in data[len(rotation):]],
    }
