from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from .config import SETTINGS
from .math_utils import american_to_probability, no_vig_two_way, normal_probability_above


def fetch_market_board(league: str) -> dict[str, Any]:
    key = os.getenv("PARLAY_API_KEY", "").strip()
    if not key:
        return {"generated_at": datetime.now(timezone.utc).isoformat(), "league": league, "events": [], "warning": "PARLAY_API_KEY is not configured"}
    path = SETTINGS.nfl_odds_path if league == "nfl" else SETTINGS.cfb_odds_path
    url = os.getenv("PARLAY_API_BASE", "https://parlay-api.com").rstrip("/") + path
    response = requests.get(
        url,
        params={"bookmakers": ",".join(SETTINGS.sportsbooks), "markets": "h2h,spreads,totals", "limit": 10000},
        headers={"Accept": "application/json", "X-API-Key": key, "User-Agent": "DHS-Advanced-Football/0.1"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload if isinstance(payload, list) else payload.get("data", payload.get("events", payload.get("results", [])))
    if not isinstance(rows, list):
        raise RuntimeError(f"Unexpected ParlayAPI {league} response structure")
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "league": league, "events": rows}


def _num(value: Any) -> float | None:
    try:
        value = float(value)
        return value if value == value else None
    except (TypeError, ValueError):
        return None


def _name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("display_name") or value.get("team") or "")
    return str(value or "")


def normalize_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize common event-odds shapes while preserving raw records for diagnostics."""
    normalized: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            continue
        home = _name(event.get("home_team") or event.get("home"))
        away = _name(event.get("away_team") or event.get("away"))
        event_id = str(event.get("id") or event.get("event_id") or event.get("game_id") or "")
        kickoff = event.get("commence_time") or event.get("start_time") or event.get("date")
        books = event.get("bookmakers") or event.get("sportsbooks") or event.get("books") or []
        if isinstance(books, dict):
            books = [{"key": key, **(value if isinstance(value, dict) else {})} for key, value in books.items()]
        for book in books:
            if not isinstance(book, dict):
                continue
            book_name = str(book.get("key") or book.get("name") or book.get("bookmaker") or "").lower().replace(" ", "")
            markets = book.get("markets") or book.get("odds") or []
            if isinstance(markets, dict):
                markets = [{"key": key, "outcomes": value} for key, value in markets.items()]
            row = {"provider_event_id": event_id, "kickoff": kickoff, "home": home, "away": away, "sportsbook": book_name}
            for market in markets:
                if not isinstance(market, dict):
                    continue
                key = str(market.get("key") or market.get("market") or market.get("type") or "").lower()
                outcomes = market.get("outcomes") or market.get("selections") or []
                if isinstance(outcomes, dict):
                    outcomes = [{"name": k, **(v if isinstance(v, dict) else {"price": v})} for k, v in outcomes.items()]
                for outcome in outcomes:
                    if not isinstance(outcome, dict):
                        continue
                    name = _name(outcome.get("name") or outcome.get("team") or outcome.get("side"))
                    price = _num(outcome.get("price") or outcome.get("odds") or outcome.get("american_odds"))
                    point = _num(outcome.get("point") or outcome.get("line") or outcome.get("handicap"))
                    lname = name.lower()
                    if key in {"h2h", "moneyline", "money_line", "ml"}:
                        if name == home: row["home_moneyline"] = price
                        elif name == away: row["away_moneyline"] = price
                    elif key in {"spreads", "spread", "handicap"}:
                        if name == home: row["home_spread"], row["home_spread_odds"] = point, price
                        elif name == away: row["away_spread"], row["away_spread_odds"] = point, price
                    elif key in {"totals", "total", "over_under", "overunder"}:
                        if "over" in lname: row["total"], row["over_odds"] = point, price
                        elif "under" in lname: row["total"], row["under_odds"] = point, price
            if any(k in row for k in ("home_moneyline", "home_spread", "total")):
                normalized.append(row)
    return normalized


def evaluate_market(projection: dict[str, Any], market: dict[str, Any], margin_sigma: float, total_sigma: float) -> list[dict[str, Any]]:
    margin = float(projection["projected_margin_home"])
    total = float(projection["projected_total"])
    out: list[dict[str, Any]] = []
    home_ml, away_ml = _num(market.get("home_moneyline")), _num(market.get("away_moneyline"))
    if home_ml is not None and away_ml is not None:
        hp, ap = no_vig_two_way(american_to_probability(home_ml), american_to_probability(away_ml))
        model_home = float(projection["home_win_probability"])
        side, probability, fair, odds = ("Home", model_home, hp, home_ml) if model_home - hp >= (1-model_home)-ap else ("Away", 1-model_home, ap, away_ml)
        out.append({"market": "Moneyline", "side": side, "line": None, "odds": odds, "model_probability": probability, "market_probability": fair, "edge": probability-fair})
    spread = _num(market.get("home_spread"))
    if spread is not None:
        home_cover = normal_probability_above(margin, -spread, margin_sigma)
        side = "Home" if home_cover >= .5 else "Away"
        out.append({"market": "Spread", "side": side, "line": spread if side == "Home" else -spread, "odds": market.get("home_spread_odds") if side == "Home" else market.get("away_spread_odds"), "model_probability": max(home_cover,1-home_cover), "market_probability": .5, "edge": abs(home_cover-.5), "raw_point_edge": abs(margin+spread)})
    line = _num(market.get("total"))
    if line is not None:
        over = normal_probability_above(total, line, total_sigma); side = "Over" if over >= .5 else "Under"
        out.append({"market": "Total", "side": side, "line": line, "odds": market.get("over_odds") if side == "Over" else market.get("under_odds"), "model_probability": max(over,1-over), "market_probability": .5, "edge": abs(over-.5), "raw_point_edge": abs(total-line)})
    return out

