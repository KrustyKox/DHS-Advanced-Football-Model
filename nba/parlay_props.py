"""ParlayAPI NBA player props adapter."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import requests

MARKETS = {"player_points": "PTS", "player_rebounds": "REB",
           "player_assists": "AST", "player_threes": "3PM",
           "player_steals": "STL", "player_blocks": "BLK",
           "player_pra": "PRA", "player_pts_rebs": "PR",
           "player_pts_asts": "PA", "player_rebs_asts": "RA"}
BOOKS = "draftkings,fanduel,caesars,bovada,betmgm,fanatics,pinnacle"


def fetch_nba_offers(day):
    token = os.environ.get("PARLAY_API_KEY")
    if not token:
        raise RuntimeError("PARLAY_API_KEY not available to NBA workflow")
    params = {"markets": ",".join(MARKETS), "bookmakers": BOOKS,
              "limit": 10000, "offset": 0, "maxAgeSec": 1800}
    response = requests.get("https://parlay-api.com/v1/sports/basketball_nba/props",
                            params=params, headers={"X-API-Key": token}, timeout=40)
    response.raise_for_status()
    if response.headers.get("x-result-truncated", "").lower() == "true":
        raise RuntimeError("ParlayAPI props board truncated; cannot claim full coverage")
    if response.headers.get("x-result-has-more", "").lower() == "true":
        raise RuntimeError("ParlayAPI props board requires pagination")
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError("ParlayAPI returned unexpected props schema")
    offers = []
    for row in rows:
        try:
            if row.get("period") != "FULL":
                continue
            stat = MARKETS.get(row.get("market_key"))
            if not stat or str(row.get("bookmaker", "")).lower() not in BOOKS.split(","):
                continue
            start = datetime.fromisoformat(str(row["commence_time"]).replace("Z", "+00:00"))
            if start.astimezone(ZoneInfo("America/New_York")).date() != day:
                continue
            line = float(row["line"])
            threshold = int(line + 0.5)
            if abs(line - (threshold - 0.5)) > 0.00001:
                continue
            if float(row.get("age_seconds", 999999)) > 1800:
                continue
            price = int(row["over_price"])
            name = str(row["player"]).strip()
            if not name:
                continue
            offers.append({"player": name, "stat": stat, "threshold": threshold,
                           "american_odds": price, "sportsbook": row["bookmaker"],
                           "market": f"Over {line} {stat}"})
        except (KeyError, TypeError, ValueError):
            continue
    return {"date": day.isoformat(), "fetched_utc": datetime.now(timezone.utc).isoformat(),
            "offers": offers}
