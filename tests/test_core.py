from datetime import datetime,timezone

from src.advanced_football.evaluation import selection_gate,summarize_performance
from src.advanced_football.math_utils import american_to_probability,no_vig_two_way,stable_seed
from src.advanced_football.markets import normalize_events


def test_stable_seed():assert stable_seed("NFL",1)==stable_seed("NFL",1)!=stable_seed("NFL",2)


def test_odds_math():
    assert round(american_to_probability(-110),4)==.5238
    a,b=no_vig_two_way(.5238,.5238);assert round(a,3)==round(b,3)==.5


def test_market_normalization():
    payload={"events":[{"id":"1","home_team":"A","away_team":"B","bookmakers":[{"key":"draftkings","markets":[{"key":"h2h","outcomes":[{"name":"A","price":-120},{"name":"B","price":105}]},{"key":"spreads","outcomes":[{"name":"A","point":-2.5,"price":-110},{"name":"B","point":2.5,"price":-110}]},{"key":"totals","outcomes":[{"name":"Over","point":47.5,"price":-110},{"name":"Under","point":47.5,"price":-110}]}]}]}]}
    rows=normalize_events(payload);assert rows[0]["home_spread"]==-2.5;assert rows[0]["total"]==47.5


def test_performance_targets():
    records=[{"actual_home":24,"actual_away":20,"projected_margin_home":5,"projected_total":45,"winner_confidence":.75}]
    result=summarize_performance(records);assert result["margin_mae"]==1;assert result["overall_target"]["passed"]


def test_gate_rejects_implausible_edge():
    play={"market":"Spread","edge":.10,"model_probability":.76,"raw_point_edge":15}
    projection={"data_reliability":.9};ok,reasons=selection_gate(play,projection,{"games":300})
    assert not ok and "spread edge requires review" in reasons

