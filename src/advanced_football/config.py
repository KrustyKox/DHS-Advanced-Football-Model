from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUTPUT = DATA / "output"
LOCKS = DATA / "locks"
RAW = DATA / "raw"


@dataclass(frozen=True)
class Settings:
    current_season: int = int(os.getenv("MODEL_SEASON", "2026"))
    history_seasons: int = int(os.getenv("HISTORY_SEASONS", "5"))
    simulations: int = int(os.getenv("SIMULATIONS", "20000"))
    sportsbooks: tuple[str, ...] = ("draftkings", "bovada")
    min_market_edge: float = float(os.getenv("MIN_MARKET_EDGE", "0.035"))
    min_selection_confidence: float = float(os.getenv("MIN_SELECTION_CONFIDENCE", "0.70"))
    nfl_min_reliability: float = float(os.getenv("NFL_MIN_RELIABILITY", "0.64"))
    cfb_min_reliability: float = float(os.getenv("CFB_MIN_RELIABILITY", "0.72"))
    cannot_miss_min_odds: float = float(os.getenv("CANNOT_MISS_MIN_ODDS", "250"))
    cannot_miss_preferred_max_odds: float = float(os.getenv("CANNOT_MISS_PREFERRED_MAX_ODDS", "350"))
    cannot_miss_nfl_min_probability: float = float(os.getenv("CANNOT_MISS_NFL_MIN_PROBABILITY", "0.70"))
    cannot_miss_cfb_min_probability: float = float(os.getenv("CANNOT_MISS_CFB_MIN_PROBABILITY", "0.75"))
    max_plausible_spread_edge: float = float(os.getenv("MAX_SPREAD_EDGE", "12"))
    max_plausible_total_edge: float = float(os.getenv("MAX_TOTAL_EDGE", "14"))
    min_validation_games: int = int(os.getenv("MIN_VALIDATION_GAMES", "150"))
    nfl_odds_path: str = os.getenv("PARLAY_NFL_ODDS_PATH") or "/v1/sports/americanfootball_nfl/odds"
    cfb_odds_path: str = os.getenv("PARLAY_CFB_ODDS_PATH") or "/v1/sports/americanfootball_ncaaf/odds"


SETTINGS = Settings()


def ensure_dirs() -> None:
    for path in (OUTPUT, LOCKS, RAW):
        path.mkdir(parents=True, exist_ok=True)
