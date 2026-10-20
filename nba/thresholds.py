"""Conditional player-stat distributions after team minutes/scoring adjustment.

These are provisional normal-approximation thresholds, NOT calibrated hit rates.
Historical dispersion is adjusted for changed minutes and scoring opportunity.
"""
import math
from statistics import NormalDist

LEVELS = (50, 60, 70, 80, 90, 95)
STATS = ("PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV", "PRA", "PR", "PA", "RA")
COMBOS = {"PRA": ("PTS", "REB", "AST"), "PR": ("PTS", "REB"),
          "PA": ("PTS", "AST"), "RA": ("REB", "AST")}


def adjusted_thresholds(games, original, adjusted, minimum=5):
    """Estimate per-stat P(X >= integer) from recent observed variability.

    Variance uses historical game-to-game spread and scales by the ratio
    of adjusted to baseline mean. This preserves within-game covariance
    for combo stats via historical summed observations.
    """
    output = {}
    for stat in STATS:
        parts = COMBOS.get(stat, (stat,))
        sample = []
        for game in games[:20]:
            vals = [game.get(key) for key in parts]
            if all(isinstance(x, (int, float)) and math.isfinite(x) and x >= 0 for x in vals):
                sample.append(sum(vals))
        if len(sample) < minimum:
            continue
        if not isinstance(original.get(stat), (int, float)) or not isinstance(adjusted.get(stat), (int, float)):
            continue
        baseline, target = float(original[stat]), float(adjusted[stat])
        if baseline <= 0 or target < 0:
            continue
        mean = sum(sample) / len(sample)
        spread = math.sqrt(sum((x-mean)**2 for x in sample) / max(len(sample)-1, 1))
        # Adjust variability to new role; retain a conservative floor.
        sigma = max(spread * math.sqrt(max(target, 0.01) / baseline),
                    0.2 * math.sqrt(max(target, 1)), 0.75)
        # X >= k uses a continuity correction for integer-valued counting stats.
        dist = NormalDist(mu=target, sigma=sigma)
        output[stat] = {}
        for level in LEVELS:
            quantile = dist.inv_cdf(1-level/100)
            output[stat][str(level)] = max(0, int(math.floor(quantile + 0.5)))
    return output
