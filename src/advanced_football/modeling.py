from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, log_loss, mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .math_utils import confidence_from_probability, stable_seed


EXCLUDE={"game_id","gameday","home_team","away_team","home_score","away_score","actual_margin","actual_total"}


@dataclass
class ModelBundle:
    margin_models:list[Any];total_models:list[Any];margin_weights:np.ndarray;total_weights:np.ndarray
    calibrator:Any;features:list[str];medians:pd.Series;margin_sigma:float;total_sigma:float
    validation:dict[str,Any]


def _models(seed:int) -> list[Any]:
    return [
        Pipeline([("impute",SimpleImputer(strategy="median")),("model",HistGradientBoostingRegressor(max_iter=260,max_leaf_nodes=24,l2_regularization=2.0,learning_rate=.045,random_state=seed))]),
        Pipeline([("impute",SimpleImputer(strategy="median")),("model",ExtraTreesRegressor(n_estimators=350,min_samples_leaf=5,max_features=.72,n_jobs=-1,random_state=seed))]),
        Pipeline([("impute",SimpleImputer(strategy="median")),("scale",StandardScaler()),("model",Ridge(alpha=18.0))]),
    ]


def _weights(errors:list[float]) -> np.ndarray:
    inv=1/np.maximum(np.asarray(errors,float),.01);return inv/inv.sum()


def season_weights(seasons:pd.Series,current:int) -> np.ndarray:
    age=current-seasons.astype(int)
    return np.select([age<=0,age==1,age==2],[4.0,1.6,.9],default=.55).astype(float)


def add_rolling_features(team_games:pd.DataFrame,current_season:int) -> pd.DataFrame:
    x=team_games.sort_values(["team","gameday","game_id"]).copy()
    metrics=[c for c in x.select_dtypes(include="number") if c not in {"season","week","home_score","away_score","neutral"}]
    for metric in metrics:
        x[f"hist_{metric}"]=x.groupby("team")[metric].transform(lambda s:s.shift().ewm(span=7,min_periods=1,adjust=False).mean())
        x[f"season_{metric}"]=x.groupby(["team","season"])[metric].transform(lambda s:s.shift().ewm(span=3,min_periods=1,adjust=False).mean())
    x["games_prior"]=x.groupby("team").cumcount();x["season_games"]=x.groupby(["team","season"]).cumcount()
    # Current-year evidence becomes the majority after two games while history remains a stabilizing prior.
    share=1-np.exp(-x.season_games/1.7)
    for metric in metrics:
        x[f"pre_{metric}"]=(1-share)*x[f"hist_{metric}"]+share*x[f"season_{metric}"].fillna(x[f"hist_{metric}"])
    x["margin_volatility"]=x.groupby("team")["margin"].transform(lambda s:s.shift().rolling(8,min_periods=2).std(ddof=0)) if "margin" in x else np.nan
    return x


def matchup_dataset(schedule:pd.DataFrame,rolling:pd.DataFrame) -> tuple[pd.DataFrame,list[str]]:
    feature_cols=[c for c in rolling if c.startswith("pre_") or c in {"games_prior","season_games","margin_volatility","pre_elo"}]
    home=rolling[["game_id","team",*feature_cols]].rename(columns={"team":"home_team",**{c:f"home_{c}" for c in feature_cols}})
    away=rolling[["game_id","team",*feature_cols]].rename(columns={"team":"away_team",**{c:f"away_{c}" for c in feature_cols}})
    data=schedule.copy();data["game_id"]=data.game_id.astype(str)
    data=data.merge(home,on=["game_id","home_team"],how="left").merge(away,on=["game_id","away_team"],how="left")
    # Upcoming games have no same-game team row. Construct their state strictly from games
    # before kickoff, including the most recently completed game.
    upcoming=data.home_score.isna()|data.away_score.isna()
    raw_metrics=[c[4:] for c in feature_cols if c.startswith("pre_") and c[4:] in rolling.columns]
    for idx in data.index[upcoming]:
        when=pd.Timestamp(data.at[idx,"gameday"]);season=int(data.at[idx,"season"])
        for side in ("home","away"):
            team=data.at[idx,f"{side}_team"];q=rolling[(rolling.team==team)&(rolling.gameday<when)].sort_values("gameday")
            if q.empty:continue
            current=q[q.season==season];share=1-np.exp(-len(current)/1.7)
            for metric in raw_metrics:
                hist=q[metric].ewm(span=7,min_periods=1,adjust=False).mean().iloc[-1]
                cur=current[metric].ewm(span=3,min_periods=1,adjust=False).mean().iloc[-1] if not current.empty else hist
                data.at[idx,f"{side}_pre_{metric}"]=(1-share)*hist+share*cur
            data.at[idx,f"{side}_games_prior"]=len(q);data.at[idx,f"{side}_season_games"]=len(current)
            data.at[idx,f"{side}_margin_volatility"]=q.margin.tail(8).std(ddof=0) if "margin" in q and len(q)>1 else np.nan
            if "pre_elo" in q:data.at[idx,f"{side}_pre_elo"]=q.pre_elo.iloc[-1]
    features=[]
    for col in feature_cols:
        h,a=f"home_{col}",f"away_{col}";features.extend([h,a]);data[f"diff_{col}"]=data[h]-data[a];features.append(f"diff_{col}")
    neutral=data["neutral"] if "neutral" in data else pd.Series(0,index=data.index)
    data["home_field"]=1-pd.to_numeric(neutral,errors="coerce").fillna(0);features.append("home_field")
    data["season_progress"]=pd.to_numeric(data.get("week",1),errors="coerce").fillna(1).clip(1,20)/20;features.append("season_progress")
    data["actual_margin"]=pd.to_numeric(data.home_score,errors="coerce")-pd.to_numeric(data.away_score,errors="coerce")
    data["actual_total"]=pd.to_numeric(data.home_score,errors="coerce")+pd.to_numeric(data.away_score,errors="coerce")
    return data,list(dict.fromkeys(features))


def train(data:pd.DataFrame,features:list[str],league:str,current_season:int) -> ModelBundle:
    z=data[data.actual_margin.notna()&data.actual_total.notna()].sort_values(["gameday","game_id"]).copy()
    if len(z)<80:raise RuntimeError(f"Only {len(z)} completed {league} games available")
    cut=max(60,int(len(z)*.8));train_set,val=z.iloc[:cut],z.iloc[cut:]
    xtr=train_set[features].replace([np.inf,-np.inf],np.nan);xv=val[features].replace([np.inf,-np.inf],np.nan)
    sample=season_weights(train_set.season,current_season)
    margins=_models(stable_seed(league,"margin"));totals=_models(stable_seed(league,"total"))
    for model in margins:model.fit(xtr,train_set.actual_margin,model__sample_weight=sample)
    for model in totals:model.fit(xtr,train_set.actual_total,model__sample_weight=sample)
    mp=np.vstack([m.predict(xv) for m in margins]);tp=np.vstack([m.predict(xv) for m in totals])
    mw=_weights([mean_absolute_error(val.actual_margin,p) for p in mp]);tw=_weights([mean_absolute_error(val.actual_total,p) for p in tp])
    pred_margin=np.average(mp,axis=0,weights=mw);pred_total=np.average(tp,axis=0,weights=tw)
    y=(val.actual_margin>0).astype(int);cal=None
    if y.nunique()>1:
        # A zero projected margin must map to 50%. Removing the intercept keeps the
        # calibrated probability direction consistent with the projected score winner.
        cal=LogisticRegression(C=.7,fit_intercept=False).fit(pred_margin.reshape(-1,1),y);prob=cal.predict_proba(pred_margin.reshape(-1,1))[:,1]
    else:prob=1/(1+np.exp(-pred_margin/10))
    validation={"games":len(val),"margin_mae":float(mean_absolute_error(val.actual_margin,pred_margin)),"total_mae":float(mean_absolute_error(val.actual_total,pred_total)),"winner_accuracy":float(((pred_margin>0)==(val.actual_margin>0)).mean()),"brier_score":float(brier_score_loss(y,prob)),"log_loss":float(log_loss(y,np.clip(prob,.001,.999),labels=[0,1])),"method":"chronological holdout; recency-weighted training; market-free features"}
    # Refit every component on all completed games after honest validation.
    fullx=z[features].replace([np.inf,-np.inf],np.nan);fullw=season_weights(z.season,current_season)
    margins=_models(stable_seed(league,"margin","full"));totals=_models(stable_seed(league,"total","full"))
    for model in margins:model.fit(fullx,z.actual_margin,model__sample_weight=fullw)
    for model in totals:model.fit(fullx,z.actual_total,model__sample_weight=fullw)
    return ModelBundle(margins,totals,mw,tw,cal,features,fullx.median(),float(np.std(val.actual_margin-pred_margin,ddof=1)),float(np.std(val.actual_total-pred_total,ddof=1)),validation)


def predict(bundle:ModelBundle,row:pd.Series,league:str) -> dict[str,Any]:
    values={f:bundle.medians.get(f,0.) if pd.isna(row.get(f,np.nan)) else float(row[f]) for f in bundle.features}
    x=pd.DataFrame([values]);margin=float(np.average([m.predict(x)[0] for m in bundle.margin_models],weights=bundle.margin_weights));total=float(np.average([m.predict(x)[0] for m in bundle.total_models],weights=bundle.total_weights))
    home=max(0.,(total+margin)/2);away=max(0.,(total-margin)/2)
    raw=float(bundle.calibrator.predict_proba([[margin]])[0,1]) if bundle.calibrator is not None else 1/(1+np.exp(-margin/10))
    current_games=min(float(row.get("home_season_games",0) or 0),float(row.get("away_season_games",0) or 0));completeness=float(np.mean([not pd.isna(row.get(f,np.nan)) for f in bundle.features]));reliability=min(1.,.58+.08*current_games)*completeness
    conf=confidence_from_probability(raw if raw>=.5 else 1-raw,reliability)
    return {"projected_home":round(home,1),"projected_away":round(away,1),"projected_margin_home":round(margin,1),"projected_total":round(total,1),"home_win_probability":raw,"predicted_winner":row.home_team if margin>=0 else row.away_team,"winner_confidence":conf,"data_reliability":reliability,"margin_uncertainty":bundle.margin_sigma,"total_uncertainty":bundle.total_sigma,"current_season_games_min":int(current_games)}
