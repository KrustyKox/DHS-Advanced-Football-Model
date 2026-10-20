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


def _name_key(name):
    return "".join(ch for ch in str(name).casefold() if ch.isalnum())


def _injury_records(payload):
    """ESPN groups injuries by team; each entry may nest an injury object."""
    groups = payload.get("injuries")
    if not isinstance(groups, list):
        raise ValueError("Injury feed has no recognizable injuries list")
    for group in groups:
        if not isinstance(group, dict):
            continue
        entries = group.get("injuries") or group.get("items")
        if isinstance(entries, list):
            for item in entries:
                if isinstance(item, dict):
                    yield item
        elif "athlete" in group or "injury" in group:
            yield group


def _text(value):
    if isinstance(value, dict):
        return str(value.get("description") or value.get("name") or value.get("displayName") or value.get("abbreviation") or "")
    return str(value or "")


def injuries(team_code):
    """Fetch team-scoped injury listings; retain IDs and normalized names."""
    code = str(team_code).upper()
    response = requests.get(f"{BASE}/injuries", params={"team": code},
                            headers=HEADERS, timeout=18)
    response.raise_for_status()
    payload = response.json()
    records = list(_injury_records(payload))
    results_id, results_name = {}, {}
    for item in records:
        injury = item.get("injury") or item
        if not isinstance(injury, dict):
            injury = item
        athlete = item.get("athlete") or injury.get("athlete") or {}
        if not isinstance(athlete, dict):
            athlete = {}
        player_id = str(athlete.get("id") or item.get("athleteId") or "")
        name = athlete.get("displayName") or athlete.get("fullName") or item.get("displayName") or ""
        status = _text(injury.get("status") or item.get("status") or injury.get("type"))
        detail = _text(injury.get("shortComment") or injury.get("longComment") or
                       item.get("shortComment") or item.get("longComment") or injury.get("details"))
        if not status:
            continue
        record = {"availability": status, "injury_detail": detail}
        if player_id:
            results_id[player_id] = record
        if name:
            results_name[_name_key(name)] = record
    return results_id, results_name, len(records)


def get_team_availability(team_code):
    players = roster(team_code)
    checked = datetime.now(timezone.utc).isoformat()
    injury_feed = "Not checked"
    matched = 0
    count = 0
    try:
        by_id, by_name, count = injuries(team_code)
        injury_feed = "Connected (ESPN unofficial; NOT a complete official game-day report)"
        for player in players:
            found = by_id.get(player["player_id"]) or by_name.get(_name_key(player["player"]))
            if found:
                player.update(found)
                matched += 1
            else:
                player["availability"] = "Not listed / Unverified"
    except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
        injury_feed = f"Unavailable: {exc}"
    return {"players": players, "checked_utc": checked, "injury_feed": injury_feed,
            "injury_records": count, "matched_injuries": matched,
            "availability_verified": False}
