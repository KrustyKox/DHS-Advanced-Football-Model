from __future__ import annotations

import itertools
import math
from datetime import datetime, timezone
from typing import Any

from .config import SETTINGS
from .math_utils import american_to_decimal, american_to_probability, decimal_to_american, no_vig_two_way


POLICY = {
    "nfl": {"min_probability": SETTINGS.cannot_miss_nfl_min_probability, "min_reliability": SETTINGS.nfl_min_reliability, "min_legs": 3, "max_legs": 6, "preferred_odds": [-500, -150]},
    "cfb": {"min_probability": SETTINGS.cannot_miss_cfb_min_probability, "min_reliability": SETTINGS.cfb_min_reliability, "min_legs": 3, "max_legs": 7, "preferred_odds": [-700, -175]},
}


def _candidates(data: dict[str, Any], week: int, sportsbook: str) -> list[dict[str, Any]]:
    league = str(data.get("league", "")).lower()
    policy = POLICY[league]
    candidates: list[dict[str, Any]] = []
    for game in data.get("games", []):
        if game.get("week") != week or float(game.get("data_reliability", 0)) < policy["min_reliability"]:
            continue
        home_p = float(game.get("home_win_probability", .5))
        side = "Home" if home_p >= .5 else "Away"
        team = game.get("home") if side == "Home" else game.get("away")
        model_p = home_p if side == "Home" else 1.0 - home_p
        if model_p < policy["min_probability"] or team != game.get("predicted_winner"):
            continue
        book = next((b for b in game.get("sportsbooks", []) if b.get("sportsbook") == sportsbook), None)
        if not book:
            continue
        try:
            home_odds, away_odds = float(book["home_moneyline"]), float(book["away_moneyline"])
            odds = home_odds if side == "Home" else away_odds
            market = no_vig_two_way(american_to_probability(home_odds), american_to_probability(away_odds))[0 if side == "Home" else 1]
        except (KeyError, TypeError, ValueError):
            continue
        low, high = policy["preferred_odds"]
        if odds < low or odds > high:
            continue
        reliability = float(game.get("data_reliability", 0))
        candidates.append({
            "game_id": str(game.get("game_id")), "kickoff": game.get("kickoff"), "away": game.get("away"), "home": game.get("home"),
            "team": team, "side": side, "moneyline": odds, "model_probability": model_p, "market_probability": market,
            "probability_edge": model_p - market, "reliability": reliability,
            "safety_score": .5 * model_p + .25 * market + .25 * reliability,
        })
    return sorted(candidates, key=lambda x: (-x["safety_score"], x["kickoff"], x["game_id"]))


def _combined_american(legs: tuple[dict[str, Any], ...]) -> float:
    return decimal_to_american(math.prod(american_to_decimal(leg["moneyline"]) for leg in legs))


def build_cannot_miss(data: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    league = str(data.get("league", "")).lower()
    policy = POLICY[league]
    upcoming = [g for g in data.get("games", []) if g.get("week") is not None and str(g.get("kickoff", "")) > now.isoformat()]
    base = {"league": league, "season": data.get("season"), "generated_at": now.isoformat(), "status": "PASS", "policy": {**policy, "minimum_parlay_odds": SETTINGS.cannot_miss_min_odds, "preferred_max_odds": SETTINGS.cannot_miss_preferred_max_odds}}
    if not upcoming:
        return {**base, "reason": "No upcoming games are available."}
    week = min(int(g["week"]) for g in upcoming)
    books = sorted({str(b.get("sportsbook")) for g in upcoming if g.get("week") == week for b in g.get("sportsbooks", []) if b.get("sportsbook")})
    combinations: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    candidate_counts: dict[str, int] = {}
    for book in books:
        eligible = _candidates(data, week, book)
        candidate_counts[book] = len(eligible)
        # The highest-safety pool keeps the exhaustive search bounded on large CFB slates.
        candidates = eligible[:18]
        for size in range(policy["min_legs"], min(policy["max_legs"], len(candidates)) + 1):
            for legs in itertools.combinations(candidates, size):
                odds = _combined_american(legs)
                if odds < SETTINGS.cannot_miss_min_odds:
                    continue
                combined_p = math.prod(leg["model_probability"] for leg in legs)
                implied_p = american_to_probability(odds)
                in_preferred = odds <= SETTINGS.cannot_miss_preferred_max_odds
                # Prefer the +250–+350 band, then maximum modeled hit rate, fewer legs, and a price nearest +250.
                rank = (not in_preferred, -combined_p, size, abs(odds - SETTINGS.cannot_miss_min_odds))
                combinations.append((rank, {**base, "status": "QUALIFIED", "week": week, "sportsbook": book, "legs": list(legs), "leg_count": size, "parlay_odds": odds, "model_combined_probability": combined_p, "sportsbook_implied_probability": implied_p, "probability_edge": combined_p - implied_p}))
    if not combinations:
        return {**base, "week": week, "candidate_counts": candidate_counts, "reason": "No combination met every confidence, reliability, individual-price, and +250 parlay requirement."}
    return min(combinations, key=lambda item: item[0])[1]


def grade_history(history: list[dict[str, Any]], finals: dict[str, tuple[float, float]]) -> list[dict[str, Any]]:
    graded = []
    for record in history:
        item = dict(record)
        if item.get("status") != "QUALIFIED":
            graded.append(item); continue
        results = []
        for leg in item.get("legs", []):
            score = finals.get(str(leg.get("game_id")))
            if score is None:
                results.append("PENDING")
            else:
                home_score, away_score = score
                winner = leg.get("home") if home_score > away_score else leg.get("away") if away_score > home_score else "TIE"
                results.append("WIN" if winner == leg.get("team") else "LOSS")
        item["leg_results"] = results
        item["result"] = "LOSS" if "LOSS" in results else "WIN" if results and all(r == "WIN" for r in results) else "PENDING"
        item["units_profit"] = round(float(item["parlay_odds"]) / 100.0, 3) if item["result"] == "WIN" else -1.0 if item["result"] == "LOSS" else None
        graded.append(item)
    return graded


def update_history(history: list[dict[str, Any]], selections: list[dict[str, Any]], finals: dict[str, tuple[float, float]], now: datetime) -> list[dict[str, Any]]:
    by_key = {(r.get("league"), r.get("season"), r.get("week")): r for r in history}
    for selection in selections:
        key = (selection.get("league"), selection.get("season"), selection.get("week"))
        existing = by_key.get(key)
        if existing and existing.get("status") == "QUALIFIED":
            first_kickoff = min((str(x.get("kickoff")) for x in existing.get("legs", [])), default="")
            if first_kickoff and first_kickoff <= now.isoformat():
                continue
        by_key[key] = selection
    return grade_history(sorted(by_key.values(), key=lambda r: (str(r.get("season")), str(r.get("week")), str(r.get("league")))), finals)
