from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np

from .config import SETTINGS


def selection_gate(play: dict[str, Any], projection: dict[str, Any], validation: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if int(validation.get("games", 0)) < SETTINGS.min_validation_games:
        reasons.append("insufficient validation sample")
    if float(play.get("edge", 0)) < SETTINGS.min_market_edge:
        reasons.append("market edge below threshold")
    if float(play.get("model_probability", 0)) < SETTINGS.min_selection_confidence:
        reasons.append("probability below threshold")
    league = str(projection.get("league", "")).lower()
    min_reliability = SETTINGS.nfl_min_reliability if league == "nfl" else SETTINGS.cfb_min_reliability
    if float(projection.get("data_reliability", 0)) < min_reliability:
        reasons.append("input reliability below threshold")
    raw = float(play.get("raw_point_edge", 0) or 0)
    if play.get("market") == "Spread" and raw > SETTINGS.max_plausible_spread_edge:
        reasons.append("spread edge requires review")
    if play.get("market") == "Total" and raw > SETTINGS.max_plausible_total_edge:
        reasons.append("total edge requires review")
    return not reasons, reasons


def summarize_performance(records: list[dict[str, Any]]) -> dict[str, Any]:
    graded = [r for r in records if r.get("actual_home") is not None and r.get("actual_away") is not None]
    if not graded:
        return {"games": 0, "status": "Awaiting completed locked games"}
    margin_errors, total_errors, winners = [], [], []
    confident_errors = []
    buckets: dict[str, list[float]] = defaultdict(list)
    for r in graded:
        actual_margin = float(r["actual_home"])-float(r["actual_away"])
        actual_total = float(r["actual_home"])+float(r["actual_away"])
        err = abs(float(r["projected_margin_home"])-actual_margin)
        margin_errors.append(err); total_errors.append(abs(float(r["projected_total"])-actual_total))
        winners.append((actual_margin > 0) == (float(r["projected_margin_home"]) > 0))
        conf = float(r.get("winner_confidence", .5))
        if conf >= .70: confident_errors.append(err)
        buckets["70%+" if conf >= .70 else "Under 70%"].append(err)
    overall = float(np.mean(margin_errors)); high = float(np.mean(confident_errors)) if confident_errors else None
    return {
        "games": len(graded), "winner_accuracy": float(np.mean(winners)), "margin_mae": overall,
        "total_mae": float(np.mean(total_errors)), "high_confidence_games": len(confident_errors),
        "high_confidence_margin_mae": high, "overall_target": {"target": 5.0, "passed": overall < 5.0},
        "high_confidence_target": {"target": 2.5, "passed": high is not None and high < 2.5},
        "confidence_buckets": {k: {"games": len(v), "margin_mae": float(np.mean(v))} for k,v in buckets.items()},
    }


def grade_locked(locked: list[dict[str, Any]], finals: dict[str, tuple[float,float]]) -> list[dict[str, Any]]:
    out=[]
    for row in locked:
        item=dict(row); score=finals.get(str(row.get("game_id")))
        if score is not None:
            item["actual_home"],item["actual_away"] = score
        out.append(item)
    return out
