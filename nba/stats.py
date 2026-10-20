"""Read real player game logs from ESPN's public, unofficial NBA API.

Return only rows with recognizable statistical labels; schema mismatches are
surfaced explicitly, never replaced by fabricated player statistics.
"""
from datetime import datetime, timezone
import requests

BASE = "https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DHS-NBA/1.0)", "Accept": "application/json"}
STATS = {"MIN": ("min", "minutes"), "PTS": ("pts", "points"), "REB": ("reb", "rebounds"),
         "AST": ("ast", "assists"), "3PM": ("3pt", "3pm", "3ptm", "threepointfieldgoalsmade"),
         "STL": ("stl", "steals"), "BLK": ("blk", "blocks"), "TOV": ("to", "tov", "turnovers")}


def _key(label):
    return "".join(c for c in str(label).lower() if c.isalnum())


def game_log(player_id, season=None):
    """Fetch ESPN gamelog for a player and season, returning validated rows."""
    player_id = str(player_id)
    if not player_id.isdigit():
        raise ValueError("Invalid player ID")
    params = {"season": int(season)} if season is not None else {}
    response = requests.get(f"{BASE}/{player_id}/gamelog", params=params,
                            headers=HEADERS, timeout=18)
    response.raise_for_status()
    payload = response.json()
    labels = payload.get("labels") or []
    if not isinstance(labels, list) or not labels:
        raise ValueError("Game log missing statistical column labels")
    positions = {}
    for stat, aliases in STATS.items():
        for i, label in enumerate(labels):
            if _key(label) in {_key(alias) for alias in aliases}:
                positions[stat] = i
                break
    if not {"PTS", "REB", "AST"}.issubset(positions):
        raise ValueError(f"Game log missing essential stats (available: {labels})")
    events = payload.get("events") or {}
    rows = []
    for season_type in payload.get("seasonTypes") or []:
        for category in season_type.get("categories") or []:
            for entry in category.get("events") or []:
                event_id = str(entry.get("eventId") or entry.get("id") or "")
                stats = entry.get("stats") or []
                if not isinstance(stats, list) or not stats:
                    continue
                row = {"event_id": event_id}
                for stat, idx in positions.items():
                    raw = str(stats[idx]).strip() if idx < len(stats) else ""
                    try:
                        row[stat] = float(raw)
                    except ValueError:
                        row[stat] = None
                if row.get("PTS") is not None:
                    event = events.get(event_id, {}) if isinstance(events, dict) else {}
                    row["date"] = event.get("gameDate") or event.get("date") or ""
                    row["opponent"] = (event.get("opponent") or {}).get("abbreviation", "")
                    rows.append(row)
    if not rows:
        raise ValueError("No parseable completed games returned by player gamelog feed")
    return {"player_id": player_id, "season": season,
            "checked_utc": datetime.now(timezone.utc).isoformat(), "games": rows,
            "labels": labels}
