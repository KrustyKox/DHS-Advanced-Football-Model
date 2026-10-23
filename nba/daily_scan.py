"""Precompute NBA trends for a selected Eastern date and write an atomic JSON snapshot."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schedule import load_schedule, games_for_date
from availability import get_team_availability
from stats import game_log
from trends import eligible_games, scan_player, rank_trends


def season_year(day):
    return day.year + (day.month >= 7)


def fetch_player(athlete, team, day):
    status = str(athlete.get("availability") or "Unverified")
    if any(term in status.lower() for term in
           ("out", "inactive", "suspended", "doubtful", "injured reserve")):
        return [], False
    games = []
    for year in (season_year(day), season_year(day) - 1):
        try:
            games.extend(game_log(athlete["player_id"], year)["games"])
        except Exception:
            continue
    clean = eligible_games(games, day)
    if len(clean) < 15:
        return [], False
    return scan_player(athlete["player"], team, status, clean, min_games=15), True


def main():
    from datetime import date
    day = date.fromisoformat(os.environ.get("NBA_SCAN_DATE") or
                            datetime.now(ZoneInfo("America/New_York")).date().isoformat())
    games = games_for_date(load_schedule(day), day)
    teams = list(dict.fromkeys(t for g in games for t in (g["away"], g["home"])))
    errors, candidates, players = [], [], []
    for team in teams:
        try:
            players.extend((p, team) for p in get_team_availability(team)["players"])
        except Exception as exc:
            errors.append(f"{team}: {exc}")
    processed = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_player, p, team, day): p for p, team in players}
        for future in as_completed(futures):
            try:
                rows, usable = future.result()
                candidates.extend(rows)
                processed += int(usable)
            except Exception as exc:
                errors.append(f'{futures[future].get("player")}: {exc}')
    qualified = [x for x in candidates if x["Trend Score"] >= 75]
    snapshot = {"date": day.isoformat(), "generated_utc": datetime.now(timezone.utc).isoformat(),
                "matchups": games, "teams": len(teams), "players_analyzed": processed,
                "candidates": len(candidates), "qualified": len(qualified),
                "errors": errors[:100], "trends": rank_trends(qualified, top_n=25, max_per_player=2)}
    if games and processed < max(8, len(teams) * 3):
        raise RuntimeError(f"Insufficient player coverage: {processed} across {len(teams)} teams; refusing incomplete snapshot")
    target = Path(__file__).resolve().parent / "data" / (day.isoformat() + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(snapshot, indent=2, allow_nan=False), encoding="utf-8")
    temp.replace(target)
    print(f"Wrote {target}: {len(snapshot['trends'])} trends, {processed} players")


if __name__ == "__main__":
    main()
