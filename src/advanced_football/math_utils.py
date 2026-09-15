from __future__ import annotations

import hashlib
import math
from statistics import NormalDist


def stable_seed(*parts: object) -> int:
    raw = "|".join(str(x) for x in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big") % (2**32 - 1)


def american_to_probability(odds: float) -> float:
    odds = float(odds)
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 100.0 / (odds + 100.0) if odds > 0 else -odds / (-odds + 100.0)


def normalize_american_odds(odds: float) -> float:
    """Convert provider decimal odds to American while preserving American prices."""
    value=float(odds)
    if 1.0 < value < 100.0:
        return round((value-1.0)*100.0,1) if value>=2.0 else round(-100.0/(value-1.0),1)
    return value


def no_vig_two_way(p1: float, p2: float) -> tuple[float, float]:
    total = p1 + p2
    return (p1 / total, p2 / total) if total > 0 else (math.nan, math.nan)


def normal_probability_above(mean: float, threshold: float, sigma: float) -> float:
    if not math.isfinite(sigma) or sigma <= 0:
        return float(mean > threshold)
    return 1.0 - NormalDist(mu=mean, sigma=sigma).cdf(threshold)


def confidence_from_probability(probability: float, reliability: float = 1.0) -> float:
    """Shrink confidence toward 50% when inputs or validation are weak."""
    p = min(max(float(probability), 0.0), 1.0)
    r = min(max(float(reliability), 0.0), 1.0)
    return 0.5 + (abs(p - 0.5) * r)
