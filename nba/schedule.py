"""NBA public schedule ingestion. No credentials required.

The NBA CDN can be unavailable or change its schema; errors are surfaced instead
of silently displaying invented games.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import requests

SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DHS-NBA/1.0)", "Accept": "application/json"}
EASTERN = ZoneInfo("America/New_York")


def load_schedule(timeout=18):
    response = requests.get(SCHEDULE_URL, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    league = payload.get("leagueSchedule", {})
    dates = league.get("gameDates")
    if not isinstance(dates, list):
        raise ValueError("NBA schedule response is missing leagueSchedule.gameDates")
    games = []
    for day in dates:
        for game in day.get("games", []):
            home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
            if not home or not away:
                continue
            stamp = game.get("gameDateTimeEst") or game.get("gameDateTimeUTC") or ""
            date_str = str(stamp)[:10] or str(day.get("gameDate", ""))[:10]
            try:
                game_date = date.fromisoformat(date_str)
            except ValueError:
                continue
            games.append({
                "date": game_date.isoformat(),
                "game_id": str(game.get("gameId", "")),
                "away": away.get("teamTricode") or away.get("teamName") or "Away",
                "home": home.get("teamTricode") or home.get("teamName") or "Home",
                "tipoff_et": str(stamp),
                "status": game.get("gameStatusText") or str(game.get("gameStatus", "")),
            })
    if not games:
        raise ValueError("NBA schedule returned no parseable games")
    return games


def games_for_date(games, target_date):
    target = target_date.isoformat() if hasattr(target_date, "isoformat") else str(target_date)
    return sorted((g for g in games if g["date"] == target),
                  key=lambda g: g["tipoff_et"])


def eastern_today():
    return datetime.now(EASTERN).date()
