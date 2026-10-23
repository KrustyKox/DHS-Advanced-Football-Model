"""Deterministic tests for NBA prop-market matching (no network needed)."""
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from market_filter import qualify_market_trends


def test_price_floor_and_exact_threshold():
    row = {"Player": "Example Player", "Team": "DAL", "Stat": "REB",
           "Threshold": 10, "Trend Score": 91}
    offers = [{"player": "Example Player", "stat": "REB", "threshold": 10,
               "american_odds": -500, "sportsbook": "draftkings"},
              {"player": "Example Player", "stat": "REB", "threshold": 10,
               "american_odds": -600, "sportsbook": "bovada"},
              {"player": "Example Player", "stat": "REB", "threshold": 4,
               "american_odds": -110, "sportsbook": "fanduel"}]
    payload = {"date": "2026-10-23", "fetched_utc": datetime.now(timezone.utc).isoformat(),
               "offers": offers}
    selected = qualify_market_trends([row], payload, "2026-10-23")
    assert len(selected) == 1
    assert selected[0]["American Odds"] == -500


if __name__ == "__main__":
    test_price_floor_and_exact_threshold()
    print("NBA odds filter smoke test passed")
