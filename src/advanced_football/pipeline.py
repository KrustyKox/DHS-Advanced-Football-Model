from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import numpy as np

from .config import LOCKS, OUTPUT, RAW, SETTINGS, ensure_dirs
from .data_sources import cfb_team_games, load_cfb_schedules, load_nfl_pbp, load_nfl_schedules, nfl_team_games
from .evaluation import grade_locked, selection_gate, summarize_performance
from .locks import update_locks
from .markets import evaluate_market, fetch_market_board, normalize_events
from .modeling import add_rolling_features, matchup_dataset, predict, train


def _write(path:Path,value:Any)->None:path.write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding="utf-8")


def _finite(value:Any)->Any:
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and (pd.isna(value) or value in (float("inf"),float("-inf"))):return None
    if isinstance(value,dict):return {k:_finite(v) for k,v in value.items()}
    if isinstance(value,list):return [_finite(v) for v in value]
    return value


def _market_match(game:dict[str,Any],markets:list[dict[str,Any]])->list[dict[str,Any]]:
    def clean(x):return "".join(c for c in str(x).lower() if c.isalnum())
    home,away=clean(game["home"]),clean(game["away"])
    exact=[m for m in markets if clean(m.get("home"))==home and clean(m.get("away"))==away]
    if exact:return exact
    return [m for m in markets if (home in clean(m.get("home")) or clean(m.get("home")) in home) and (away in clean(m.get("away")) or clean(m.get("away")) in away)]


def build_league(league:str,schedule:pd.DataFrame,team_games:pd.DataFrame,market_payload:dict[str,Any],now:datetime)->tuple[dict,list[dict]]:
    rolling=add_rolling_features(team_games,SETTINGS.current_season);dataset,features=matchup_dataset(schedule,rolling);bundle=train(dataset,features,league,SETTINGS.current_season)
    future=dataset[dataset.gameday.notna() & (dataset.gameday>=pd.Timestamp(now))].sort_values("gameday").head(500)
    markets=normalize_events(market_payload);games=[];qualified=[]
    for _,row in future.iterrows():
        p=predict(bundle,row,league);game={"game_id":str(row.game_id),"league":league,"season":int(row.season),"week":int(row.week) if pd.notna(row.week) else None,"kickoff":pd.Timestamp(row.gameday).isoformat(),"home":row.home_team,"away":row.away_team,**p,"sportsbooks":[]}
        for market in _market_match(game,markets):
            plays=evaluate_market(game,market,bundle.margin_sigma,bundle.total_sigma)
            evaluated=[]
            for play in plays:
                ok,reasons=selection_gate(play,game,bundle.validation);item={**play,"qualified":ok,"gate_reasons":reasons}
                evaluated.append(item)
                if ok:qualified.append({"game_id":game["game_id"],"league":league,"kickoff":game["kickoff"],"home":game["home"],"away":game["away"],"sportsbook":market.get("sportsbook"),**item})
            game["sportsbooks"].append({"sportsbook":market.get("sportsbook"),"home_spread":market.get("home_spread"),"home_moneyline":market.get("home_moneyline"),"away_moneyline":market.get("away_moneyline"),"total":market.get("total"),"evaluations":evaluated})
        games.append(game)
    locked=update_locks(LOCKS/f"{league}.json",games,now)
    finals={str(r.game_id):(float(r.home_score),float(r.away_score)) for _,r in schedule[schedule.home_score.notna()&schedule.away_score.notna()].iterrows()}
    graded=grade_locked(locked,finals);performance=summarize_performance(graded)
    output={"generated_at":now.isoformat(),"league":league,"season":SETTINGS.current_season,"validation":bundle.validation,"targets":{"overall_margin_mae":5.0,"confidence_70_margin_mae":2.5},"feature_count":len(features),"current_season_weight":4.0,"games":games,"warnings":([market_payload["warning"]] if market_payload.get("warning") else [])}
    _write(LOCKS/f"{league}.json",_finite({"updated_at":now.isoformat(),"games":graded}))
    return _finite(output),qualified,performance


def run()->dict[str,Any]:
    ensure_dirs();now=datetime.now(timezone.utc);years=list(range(SETTINGS.current_season-SETTINGS.history_seasons+1,SETTINGS.current_season+1))
    nfl_schedule=load_nfl_schedules();nfl_schedule=nfl_schedule[nfl_schedule.season.isin(years)].copy();nfl_pbp=load_nfl_pbp(years);nfl_teams=nfl_team_games(nfl_schedule,nfl_pbp)
    cfb_schedule=load_cfb_schedules(SETTINGS.current_season,SETTINGS.history_seasons);cfb_teams=cfb_team_games(cfb_schedule)
    results={};all_plays=[];performance={"generated_at":now.isoformat()}
    for league,schedule,teams in (("nfl",nfl_schedule,nfl_teams),("cfb",cfb_schedule,cfb_teams)):
        try:market=fetch_market_board(league)
        except Exception as exc:market={"events":[],"warning":f"Market fetch failed: {type(exc).__name__}: {exc}","generated_at":now.isoformat()}
        _write(RAW/f"{league}_markets_schema.json",{"generated_at":now.isoformat(),"records":len(market.get("events",[])),"sample_keys":sorted({str(k) for r in market.get("events",[])[:25] if isinstance(r,dict) for k in r})})
        results[league],plays,performance[league]=build_league(league,schedule,teams,market,now);all_plays.extend(plays);_write(OUTPUT/f"{league}.json",results[league])
    all_plays.sort(key=lambda x:(x["kickoff"],-float(x.get("edge",0))))
    _write(OUTPUT/"qualified_plays.json",_finite({"generated_at":now.isoformat(),"plays":all_plays,"gate_policy":{"min_probability":SETTINGS.min_selection_confidence,"min_market_edge":SETTINGS.min_market_edge,"research_only":True}}));_write(OUTPUT/"performance.json",_finite(performance))
    return {"nfl_games":len(results["nfl"]["games"]),"cfb_games":len(results["cfb"]["games"]),"qualified_plays":len(all_plays)}
