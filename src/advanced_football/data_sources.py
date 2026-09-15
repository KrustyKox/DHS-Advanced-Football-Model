from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import numpy as np
import pandas as pd
import requests

NFL_SCHEDULES=(
    "https://github.com/nflverse/nfldata/raw/master/data/games.csv",
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv",
)
NFL_PBP="https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
CFB_SCOREBOARD="https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
CFB_SCHEDULE_CSV="https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main/schedules/csv/cfb_schedules_{season}.csv"


def _get(url: str, **kwargs) -> requests.Response:
    response=requests.get(url,timeout=kwargs.pop("timeout",60),headers={"User-Agent":"DHS-Advanced-Football/0.1"},**kwargs)
    response.raise_for_status();return response


def load_nfl_schedules() -> pd.DataFrame:
    errors=[]
    for url in NFL_SCHEDULES:
        try:
            frame=pd.read_csv(io.BytesIO(_get(url).content),low_memory=False)
            frame["gameday"]=pd.to_datetime(frame["gameday"],errors="coerce",utc=True)
            return frame
        except Exception as exc: errors.append(f"{url}: {exc}")
    raise RuntimeError("Unable to load NFL schedules: "+" | ".join(errors))


def _pbp_year(season: int) -> pd.DataFrame | None:
    try:
        raw=_get(NFL_PBP.format(season=season),timeout=90).content
        wanted={"game_id","season","week","season_type","posteam","defteam","epa","success","yards_gained","pass","rush","sack","interception","fumble_lost","yardline_100","touchdown","third_down_converted","third_down_failed","qb_hit","down","play_type"}
        frame=pd.read_parquet(io.BytesIO(raw));return frame[[c for c in frame if c in wanted]].copy()
    except Exception:return None


def load_nfl_pbp(seasons: list[int]) -> pd.DataFrame:
    frames=[]
    with ThreadPoolExecutor(max_workers=min(5,len(seasons))) as pool:
        futures=[pool.submit(_pbp_year,season) for season in seasons]
        for future in as_completed(futures):
            frame=future.result()
            if frame is not None and not frame.empty:frames.append(frame)
    if not frames:raise RuntimeError("Unable to load NFL play-by-play")
    return pd.concat(frames,ignore_index=True)


def nfl_team_games(schedule: pd.DataFrame,pbp: pd.DataFrame) -> pd.DataFrame:
    p=pbp[pbp.posteam.notna()&pbp.defteam.notna()].copy()
    for c in ["epa","success","yards_gained","pass","rush","sack","interception","fumble_lost","yardline_100","touchdown","third_down_converted","third_down_failed","qb_hit","down"]:
        if c not in p:p[c]=np.nan
        p[c]=pd.to_numeric(p[c],errors="coerce")
    p["is_play"]=(p["pass"].fillna(0).gt(0)|p["rush"].fillna(0).gt(0))
    p["turnover"]=(p.interception.fillna(0)+p.fumble_lost.fillna(0)).clip(upper=1)
    p["explosive"]=(p.yards_gained>=20).astype(float)
    p["redzone"]=(p.yardline_100<=20)
    p["third"]=(p.third_down_converted.fillna(0)+p.third_down_failed.fillna(0)).gt(0)
    rows=[]
    for (gid,team,opp),g in p.groupby(["game_id","posteam","defteam"],sort=False):
        q=g[g.is_play];pa=q[q["pass"].fillna(0)>0];ru=q[q["rush"].fillna(0)>0];early=q[q.down.isin([1,2])];rz=q[q.redzone];third=q[q.third]
        rows.append({"game_id":str(gid),"team":team,"opponent":opp,"epa":q.epa.mean(),"success":q.success.mean(),"pass_epa":pa.epa.mean(),"rush_epa":ru.epa.mean(),"pass_rate":len(pa)/len(q) if len(q) else np.nan,"early_down_epa":early.epa.mean(),"early_down_success":early.success.mean(),"explosive_rate":q.explosive.mean(),"turnover_rate":q.turnover.mean(),"sack_rate":pa.sack.mean(),"pressure_rate":pa.qb_hit.mean(),"redzone_td_rate":rz.touchdown.mean() if len(rz) else np.nan,"third_down_rate":third.third_down_converted.mean() if len(third) else np.nan,"plays":len(q)})
    x=pd.DataFrame(rows)
    sched=schedule.copy();sched["game_id"]=sched.game_id.astype(str)
    # Sportsbook spread/total fields in nflverse schedules are deliberately excluded.
    keep=[c for c in ["game_id","season","week","gameday","gametime","home_team","away_team","home_score","away_score","roof","surface","temp","wind","rest_home","rest_away"] if c in sched]
    x=x.merge(sched[keep],on="game_id",how="left")
    x["pf"]=np.where(x.team.eq(x.home_team),x.home_score,x.away_score);x["pa"]=np.where(x.team.eq(x.home_team),x.away_score,x.home_score);x["margin"]=x.pf-x.pa;x["win"]=(x.margin>0).astype(float)
    opponent=x[["game_id","team","epa","success","pass_epa","rush_epa","explosive_rate","turnover_rate","sack_rate","pressure_rate"]].rename(columns={"team":"opponent","epa":"def_epa_allowed","success":"def_success_allowed","pass_epa":"def_pass_epa_allowed","rush_epa":"def_rush_epa_allowed","explosive_rate":"def_explosive_allowed","turnover_rate":"def_takeaway_rate","sack_rate":"def_sack_rate","pressure_rate":"def_pressure_rate"})
    return x.merge(opponent,on=["game_id","opponent"],how="left")


def _cfb_week(args: tuple[int,int,int]) -> tuple[int,int,list[dict]]:
    season,seasontype,week=args
    try:return season,week,(_get(CFB_SCOREBOARD,params={"dates":str(season),"seasontype":seasontype,"week":week,"limit":500,"groups":80},timeout=30).json().get("events") or [])
    except Exception:return season,week,[]


def load_cfb_schedules(current_season: int,history_seasons: int) -> pd.DataFrame:
    # SportsDataverse publishes a stable season file and is the primary source. ESPN
    # remains a fallback because its scoreboard endpoint occasionally rejects CI traffic.
    frames=[]
    for season in range(current_season-history_seasons+1,current_season+1):
        try:
            raw=_get(CFB_SCHEDULE_CSV.format(season=season),timeout=60).content;frame=pd.read_csv(io.BytesIO(raw),low_memory=False)
            frame=frame.rename(columns={"start_date":"gameday","home_points":"home_score","away_points":"away_score","neutral_site":"neutral"})
            needed=["game_id","season","week","gameday","home_team","away_team","home_score","away_score","neutral"]
            if all(c in frame for c in needed):frames.append(frame[needed])
        except Exception:continue
    if frames:
        out=pd.concat(frames,ignore_index=True).drop_duplicates("game_id");out["game_id"]=out.game_id.astype(str);out["gameday"]=pd.to_datetime(out.gameday,errors="coerce",utc=True);out["neutral"]=out.neutral.fillna(False).astype(int)
        return out.sort_values(["season","gameday","week","game_id"]).reset_index(drop=True)
    tasks=[]
    for season in range(current_season-history_seasons+1,current_season+1):
        tasks.extend((season,2,week) for week in range(1,16));tasks.extend((season,3,week) for week in range(1,6))
    parsed={}
    fetched=[]
    with ThreadPoolExecutor(max_workers=18) as pool:
        for future in as_completed([pool.submit(_cfb_week,task) for task in tasks]):fetched.append(future.result())
    for task_season,task_week,events in fetched:
      for event in events:
        comps=event.get("competitions") or []
        if not comps:continue
        c=comps[0];teams=c.get("competitors") or [];home=next((x for x in teams if x.get("homeAway")=="home"),None);away=next((x for x in teams if x.get("homeAway")=="away"),None)
        if not home or not away:continue
        def name(x):
            t=x.get("team") or {};return t.get("displayName") or t.get("shortDisplayName") or t.get("name")
        def score(x):
            try:return float(x.get("score"))
            except Exception:return np.nan
        status=((event.get("status") or {}).get("type") or {})
        gid=str(event.get("id") or "")
        if gid and gid not in parsed:parsed[gid]={"game_id":gid,"season":int(task_season),"week":int(task_week),"gameday":pd.to_datetime(event.get("date") or c.get("date"),errors="coerce",utc=True),"home_team":name(home),"away_team":name(away),"home_score":score(home) if status.get("completed") else np.nan,"away_score":score(away) if status.get("completed") else np.nan,"neutral":int(bool(c.get("neutralSite",False)))}
    if not parsed:raise RuntimeError("Unable to download college football schedule/history from ESPN public data")
    return pd.DataFrame(parsed.values()).sort_values(["season","gameday","week","game_id"]).reset_index(drop=True)


def cfb_team_games(schedule: pd.DataFrame) -> pd.DataFrame:
    ratings:dict[str,float]={};rows=[]
    for _,g in schedule.sort_values(["gameday","game_id"]).iterrows():
        he=ratings.get(g.home_team,1500.);ae=ratings.get(g.away_team,1500.)
        if pd.notna(g.home_score) and pd.notna(g.away_score):
            margin=float(g.home_score-g.away_score);expected=1/(1+10**((ae-he-55*(1-int(g.neutral)))/400));actual=1. if margin>0 else .5 if margin==0 else 0.
            change=24*(actual-expected);ratings[g.home_team]=he+change;ratings[g.away_team]=ae-change
            rows.extend([{"game_id":g.game_id,"team":g.home_team,"opponent":g.away_team,"season":g.season,"week":g.week,"gameday":g.gameday,"pf":g.home_score,"pa":g.away_score,"opp_elo":ae,"pre_elo":he,"neutral":g.neutral},{"game_id":g.game_id,"team":g.away_team,"opponent":g.home_team,"season":g.season,"week":g.week,"gameday":g.gameday,"pf":g.away_score,"pa":g.home_score,"opp_elo":he,"pre_elo":ae,"neutral":g.neutral}])
    x=pd.DataFrame(rows)
    if not x.empty:
        x["margin"]=x.pf-x.pa;x["win"]=(x.margin>0).astype(float);x["adj_margin"]=x.margin.clip(-42,42)+.045*(x.opp_elo-1500);x["adj_pf"]=x.pf.clip(upper=56)+.03*(x.opp_elo-1500);x["adj_pa"]=x.pa.clip(upper=56)-.03*(x.opp_elo-1500)
    return x
