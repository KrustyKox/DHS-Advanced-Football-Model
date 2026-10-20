"""Free NBA roster and injury feed adapter (ESPN, unofficial).

Never interpret an absent injury record as proof a player is available.
Do not make betting projections when roster or availability is unverified.
"""
from datetime import datetime, timezone
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DHS-NBA/1.0)", "Accept": "application/json"}
STATUS_TERMS = ("out", "doubtful", "questionable", "probable", "day-to-day", "injured reserve")


def _json(url):
    response = requests.get(url, headers=HEADERS, timeout=18)
    response.raise_for_status()
    return response.json()


def _athletes(data):
    """Flatten ESPN's roster athlete arrays (including grouped roster responses)."""
    for entry in data.get("athletes") or []:
        if "items" in entry:
            yield from entry["items"]
        else:
            yield entry


def roster(team_code):
    code = str(team_code).lower().strip()
    if not code.isalnum() or len(code) > 4:
        raise ValueError("Invalid NBA team identifier")
    payload = _json(f"{BASE}/teams/{code}/roster")
    players = []
    for athlete in _athletes(payload):
        person = athlete.get("athlete") or athlete
        player_id = str(person.get("id") or "")
        name = person.get("displayName") or person.get("fullName")
        if not player_id or not name:
            continue
        players.append({
            "player_id": player_id,
            "player": name,
            "position": (person.get("position") or {}).get("abbreviation", ""),
            "jersey": person.get("jersey", ""),
            "team": code.upper(),
            "availability": "Unverified",
            "injury_detail": "",
        })
    if not players:
        raise ValueError(f"No roster players returned for {code.upper()}; refusing to show an empty roster as valid")
    return players


def injuries():
    """Best-effort injuries feed; absence of entries never means healthy."""
    payload = _json(f"{BASE}/injuries")
    results = {}
    # ESPN may return team groups or direct injury entries depending on API version.
    groups = payload.get("injuries") or payload.get("items") or []
    if not isinstance(groups, list):
        raise ValueError("Unexpected injury feed structure")
    for group in groups:
        entries = group.get("injuries") or group.get("items") or [group]
        for item in entries:
            athlete = item.get("athlete") or {}
            pid = str(athlete.get("id") or item.get("athleteId") or "")
            status_obj = item.get("status") or item.get("type") or ""
            status = status_obj.get("description", "") if isinstance(status_obj, dict) else str(status_obj)
            detail = item.get("shortComment") or item.get("longComment") or item.get("details") or ""
            if pid and status:
                results[pid] = {"availability": status, "injury_detail": str(detail)}
    return results


def get_team_availability(team_code):
    players = roster(team_code)
    checked = datetime.now(timezone.utc).isoformat()
    try:
        injury_map = injuries()
        injury_feed = "Connected (unofficial; completeness not guaranteed)"
        for player in players:
            if player["player_id"] in injury_map:
                player.update(injury_map[player["player_id"]])
            else:
                player["availability"] = "Not listed — NOT confirmed active"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        injury_feed = f"Unavailable: {exc}"
    return {"players": players, "checked_utc": checked, "injury_feed": injury_feed,
            "availability_verified": False}
