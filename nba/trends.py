"""NBA historical threshold scanner. Descriptive trends, not calibrated probabilities."""
import math
from statistics import mean

STATS = ("PTS", "REB", "AST", "3PM", "STL", "BLK", "PRA", "PR", "PA", "RA")
COMBOS = {"PRA": ("PTS", "REB", "AST"), "PR": ("PTS", "REB"),
          "PA": ("PTS", "AST"), "RA": ("REB", "AST")}
# Avoid automatic trivial 1+ thresholds for high-volume counting categories.
MINIMUM = {"PTS": 10, "REB": 3, "AST": 3, "3PM": 1, "STL": 1, "BLK": 1,
           "PRA": 15, "PR": 12, "PA": 12, "RA": 5}
STEP = {"PTS": 5, "REB": 1, "AST": 1, "3PM": 1, "STL": 1, "BLK": 1,
        "PRA": 5, "PR": 5, "PA": 5, "RA": 2}


def stat_value(game, stat):
    keys = COMBOS.get(stat, (stat,))
    values = [game.get(k) for k in keys]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0
               for v in values):
        return None
    return sum(values)


def eligible_games(games, before_date):
    """Sort and deduplicate completed dated logs, excluding future/current games."""
    unique = {}
    for g in games:
        date = str(g.get("date", ""))[:10]
        event_id = str(g.get("event_id") or date)
        if len(date) != 10 or not date[:4].isdigit() or date >= str(before_date):
            continue
        if not isinstance(g.get("MIN"), (int, float)) or g["MIN"] <= 0:
            continue
        unique[event_id] = g
    return sorted(unique.values(), key=lambda g: str(g["date"]), reverse=True)


def scan_player(player, team, availability, games, min_games=15, all_thresholds=False):
    """Return one strongest threshold per stat for a player."""
    if len(games) < min_games:
        return []
    output = []
    for stat in STATS:
        observed = [(g, stat_value(g, stat)) for g in games[:40]]
        observed = [(g, v) for g, v in observed if v is not None]
        if len(observed) < min_games:
            continue
        values = [v for _, v in observed]
        last20 = values[:20]
        last10 = values[:10]
        last5 = values[:5]
        if len(last20) < min_games:
            continue
        upper = int(max(last20))
        candidates = range(MINIMUM[stat], upper + 1, STEP[stat])
        best = None
        for threshold in candidates:
            n20 = sum(v >= threshold for v in last20)
            n10 = sum(v >= threshold for v in last10)
            n5 = sum(v >= threshold for v in last5)
            streak = next((i for i, v in enumerate(values) if v < threshold), len(values))
            if n20 / len(last20) < .75 or n10 / len(last10) < .7:
                continue
            # Descriptive score; deliberately NOT a probability.
            rate20 = n20 / len(last20)
            rate10 = n10 / len(last10)
            rate5 = n5 / len(last5)
            season_rate = sum(v >= threshold for v in values) / len(values)
            minutes = [g["MIN"] for g, _ in observed[:10]]
            stable = 1 - min(1, (max(minutes) - min(minutes)) / 35)
            sample_factor = min(1, len(last20) / 20)
            streak_strength = min(streak, 20) / 20
            score = 100 * (0.30 * rate20 + 0.20 * rate10 +
                           0.15 * rate5 + 0.15 * season_rate +
                           0.10 * streak_strength + 0.10 * stable) * sample_factor
            # Prioritize reliability, then nontrivial threshold relative to recent average.
            utility = score + 5 * min(1, threshold / max(mean(last20), 1))
            candidate = {"Player": player, "Team": team, "Stat": stat,
                         "Prop": f"{threshold}+ {stat}", "Threshold": threshold,
                         "Last 5": f"{n5}/{len(last5)}",
                         "Last 10": f"{n10}/{len(last10)}",
                         "Last 20": f"{n20}/{len(last20)}",
                         "Streak": streak, "Trend Score": round(score, 1),
                         "Season Sample": len(values),
                         "Sample Hit Rate": round(season_rate * 100, 1),
                         "Avg MIN (10)": round(mean(minutes), 1),
                         "Availability": availability,
                         "_utility": utility,
                         "Evidence": [{"Date": g["date"], "Opponent": g.get("opponent", ""),
                                       "MIN": g["MIN"], stat: v,
                                       "Hit": v >= threshold}
                                      for g, v in observed[:20]]}
            if all_thresholds:
                output.append(candidate)
            if best is None or candidate["_utility"] > best["_utility"]:
                best = candidate
        if best and not all_thresholds:
            output.append(best)
    return output


def rank_trends(rows, top_n=25, max_per_player=2):
    """Diversify player exposure while preserving top trend scores."""
    ranked = sorted(rows, key=lambda x: (x["Trend Score"], x["_utility"],
                                          x["Streak"]), reverse=True)
    result, counts = [], {}
    for item in ranked:
        name = item["Player"]
        if counts.get(name, 0) >= max_per_player:
            continue
        result.append(item)
        counts[name] = counts.get(name, 0) + 1
        if len(result) >= top_n:
            break
    return result
