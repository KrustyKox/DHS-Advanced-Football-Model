"""Fetch real NBA games from ESPN's public date-scoped scoreboard feed.

This feed is unofficial and may change or block hosted requests. The UI displays
an explicit error instead of substituting fabricated matchups.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

EASTERN = ZoneInfo("America/New_York")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; DHS-NBA/1.0)",
    "Accept": "application/json",
}


def eastern_today():
    return datetime.now(EASTERN).date()


def load_schedule(target_date=None, timeout=18):
    """Retrieve games for a single Eastern-calendar date, including postseason."""
    if target_date is None:
        target_date = eastern_today()
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    response = requests.get(
        SCOREBOARD_URL,
        params={"dates": target_date.strftime("%Y%m%d"), "limit": 100},
        headers=HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    events = payload.get("events")
    if not isinstance(events, list):
        raise ValueError("ESPN schedule response has no events list")

    games = []
    for event in events:
        competitions = event.get("competitions") or []
        competition = competitions[0] if competitions else {}
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
            continue
        home_team, away_team = home.get("team") or {}, away.get("team") or {}
        stamp = event.get("date") or competition.get("date") or ""
        status = (event.get("status") or {}).get("type") or {}
        games.append({
            "date": target_date.isoformat(),
            "game_id": str(event.get("id", "")),
            "away": away_team.get("abbreviation") or away_team.get("displayName") or "Away",
            "home": home_team.get("abbreviation") or home_team.get("displayName") or "Home",
            "tipoff_et": str(stamp),
            "status": status.get("shortDetail") or status.get("description") or "Scheduled",
        })
    return sorted(games, key=lambda g: g["tipoff_et"])


def games_for_date(games, target_date):
    """Compatibility helper for the Streamlit app."""
    target = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    return [g for g in games if g["date"] == target]
