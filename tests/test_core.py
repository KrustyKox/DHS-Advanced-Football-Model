from datetime import datetime,timezone

from src.advanced_football.evaluation import selection_gate,summarize_performance
from src.advanced_football.math_utils import american_to_probability,no_vig_two_way,normalize_american_odds,stable_seed
from src.advanced_football.markets import normalize_events
from src.advanced_football.pipeline import build_underdog_ml_board
from src.advanced_football.cannot_miss import build_cannot_miss,grade_history


def test_stable_seed():assert stable_seed("NFL",1)==stable_seed("NFL",1)!=stable_seed("NFL",2)


def test_odds_math():
    assert round(american_to_probability(-110),4)==.5238
    a,b=no_vig_two_way(.5238,.5238);assert round(a,3)==round(b,3)==.5
    assert normalize_american_odds(2.8)==180.0
    assert normalize_american_odds(1.5)==-200.0
    assert normalize_american_odds(-110)==-110


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


def test_nfl_uses_temporary_64_percent_reliability_gate():
    play={"market":"Spread","edge":.10,"model_probability":.76,"raw_point_edge":4}
    nfl_projection={"league":"nfl","data_reliability":.65}
    cfb_projection={"league":"cfb","data_reliability":.65}
    nfl_ok,_=selection_gate(play,nfl_projection,{"games":300})
    cfb_ok,cfb_reasons=selection_gate(play,cfb_projection,{"games":300})
    assert nfl_ok
    assert not cfb_ok and "input reliability below threshold" in cfb_reasons


def test_underdog_board_requires_model_to_pick_the_longer_price():
    results={"nfl":{"games":[{"game_id":"1","week":2,"kickoff":"2026-09-20T17:00:00Z","home":"Home","away":"Away","predicted_winner":"Away","home_win_probability":.42,"winner_confidence":.58,"data_reliability":.9,"sportsbooks":[{"sportsbook":"draftkings","home_moneyline":-150,"away_moneyline":130,"evaluations":[{"market":"Moneyline","side":"Away","qualified":True,"gate_reasons":[]}]}]}]}}
    picks=build_underdog_ml_board(results)
    assert len(picks)==1 and picks[0]["underdog"]=="Away" and picks[0]["qualified"]


def _parlay_game(number,probability,odds=-250):
    return {"game_id":str(number),"week":4,"kickoff":f"2026-10-0{number}T17:00:00+00:00","home":f"H{number}","away":f"A{number}","predicted_winner":f"H{number}","home_win_probability":probability,"data_reliability":.80,"sportsbooks":[{"sportsbook":"draftkings","home_moneyline":odds,"away_moneyline":200}]}


def test_cannot_miss_builds_smallest_high_confidence_parlay_over_250():
    data={"league":"nfl","season":2026,"games":[_parlay_game(i,.78-i/1000) for i in range(1,6)]}
    result=build_cannot_miss(data,datetime(2026,9,20,tzinfo=timezone.utc))
    assert result["status"]=="QUALIFIED"
    assert result["parlay_odds"]>=250
    assert 3<=result["leg_count"]<=6
    assert result["sportsbook"]=="draftkings"


def test_cannot_miss_passes_instead_of_lowering_standards():
    data={"league":"nfl","season":2026,"games":[_parlay_game(i,.68) for i in range(1,6)]}
    result=build_cannot_miss(data,datetime(2026,9,20,tzinfo=timezone.utc))
    assert result["status"]=="PASS"


def test_cannot_miss_history_grades_ticket_and_units():
    ticket={"status":"QUALIFIED","parlay_odds":275,"legs":[{"game_id":"1","home":"H1","away":"A1","team":"H1"},{"game_id":"2","home":"H2","away":"A2","team":"A2"}]}
    result=grade_history([ticket],{"1":(24,10),"2":(14,21)})[0]
    assert result["result"]=="WIN" and result["units_profit"]==2.75
