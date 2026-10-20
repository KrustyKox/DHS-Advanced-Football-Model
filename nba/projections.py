"""Transparent NBA statistical baseline, NOT calibrated betting probabilities.

Uses observed completed game logs, recent-game weighting and empirical quantiles.
Missing/insufficient data is explicitly excluded. No synthetic projections.
"""
import math
from statistics import NormalDist

STATS = ("MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV")
LEVELS = (50, 60, 70, 80, 90, 95)


def _valid_games(games):
    clean = []
    for row in games:
        if all(isinstance(row.get(k), (float, int)) and
               math.isfinite(row[k]) and row[k] >= 0 for k in ("PTS", "REB", "AST")):
            clean.append(row)
    return clean


def project_player(games, minimum_games=5):
    """Returns estimates and illustrative empirical thresholds, or raises.

    Feed ordering is assumed most-recent-first, as returned by ESPN gamelog.
    Percentile thresholds are in-sample descriptive estimates, not validated
    out-of-sample probabilities. Weights decay toward older games.
    """
    clean = _valid_games(games)[:20]
    if len(clean) < minimum_games:
        raise ValueError(f"Only {len(clean)} usable games; need {minimum_games}")
    weights = [0.90 ** i for i in range(len(clean))]
    result = {"games_used": len(clean), "projections": {}, "thresholds": {}}
    for stat in STATS:
        observations = [(float(g[stat]), w) for g, w in zip(clean, weights)
                        if isinstance(g.get(stat), (int, float)) and math.isfinite(g[stat])
                        and g[stat] >= 0]
        if len(observations) < minimum_games:
            continue
        total_w = sum(w for _, w in observations)
        mean = sum(v*w for v, w in observations)/total_w
        variance = sum(w*(v-mean)**2 for v,w in observations)/total_w
        # Finite-sample uncertainty floor avoids spurious near-certainty.
        sigma = max(math.sqrt(variance), 0.20*math.sqrt(max(mean, 1)), 0.75)
        result["projections"][stat] = round(mean, 1)
        result["thresholds"][stat] = {}
        for level in LEVELS:
            z = NormalDist().inv_cdf(1-level/100)
            threshold = max(0, math.floor(mean + z*sigma))
            result["thresholds"][stat][str(level)] = threshold
    for combo, parts in {"PRA": ("PTS","REB","AST"), "PR": ("PTS","REB"),
                         "PA": ("PTS","AST"), "RA": ("REB","AST")}.items():
        if all(k in result["projections"] for k in parts):
            result["projections"][combo] = round(sum(result["projections"][k] for k in parts),1)
            observations = [sum(g[k] for k in parts) for g in clean
                            if all(isinstance(g.get(k),(int,float)) for k in parts)]
            if len(observations) >= minimum_games:
                w = weights[:len(observations)]
                tw = sum(w)
                mean = sum(x*y for x,y in zip(observations,w))/tw
                sigma = max(math.sqrt(sum(y*(x-mean)**2 for x,y in zip(observations,w))/tw),
                            0.20*math.sqrt(max(mean,1)), 0.75)
                result["thresholds"][combo] = {
                    str(p): max(0,math.floor(mean+NormalDist().inv_cdf(1-p/100)*sigma))
                    for p in LEVELS}
    return result
