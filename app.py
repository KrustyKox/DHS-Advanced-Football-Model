from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent;OUT=ROOT/"data"/"output"
st.set_page_config(page_title="DHS Advanced Football Model",page_icon="🏈",layout="wide")
st.markdown("""<style>
.block-container{padding-top:1.4rem;max-width:1600px}.dhs-card{background:#111821;border:1px solid #253243;border-radius:12px;padding:14px 16px;height:100%}.dhs-label{color:#91a0b2;font-size:.76rem;text-transform:uppercase;letter-spacing:.08em}.dhs-value{font-size:1.65rem;font-weight:750;color:#f4f7fb}.good{color:#31d07c}.bad{color:#ff6675}.warn{color:#f5b700}.small{font-size:.82rem;color:#9eabb9}</style>""",unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load(name):
    path=OUT/name
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return {}


def metric_card(label,value,sub="",state=""):
    st.markdown(f'<div class="dhs-card"><div class="dhs-label">{label}</div><div class="dhs-value {state}">{value}</div><div class="small">{sub}</div></div>',unsafe_allow_html=True)


def pct(v):return "—" if v is None else f"{100*float(v):.1f}%"
def num(v,d=2):return "—" if v is None else f"{float(v):.{d}f}"


nfl,cfb,perf,qualified=load("nfl.json"),load("cfb.json"),load("performance.json"),load("qualified_plays.json")
st.title("DHS Advanced Football Model")
st.caption("Independent projections • market comparison • kickoff-locked evaluation • research mode")
tab_overview,tab_board,tab_plays,tab_lab,tab_perf,tab_validation,tab_method=st.tabs(["Overview","Game Board","Qualified Plays","Matchup Lab","Performance","Validation & Goals","Methodology"])

with tab_overview:
    st.subheader("Decision dashboard")
    cols=st.columns(4)
    with cols[0]:metric_card("NFL games",len(nfl.get("games",[])),"Upcoming modeled games")
    with cols[1]:metric_card("CFB games",len(cfb.get("games",[])),"Upcoming modeled games")
    with cols[2]:metric_card("Qualified plays",len(qualified.get("plays",[])),"All reliability and edge gates passed")
    with cols[3]:metric_card("Operating status","RESEARCH", "No wager is guaranteed", "warn")
    st.info("The targets—margin MAE below 5.0 overall and below 2.5 for 70%+ confidence—are measured goals, not assumed performance.")
    for league,data in (("NFL",nfl),("CFB",cfb)):
        st.markdown(f"#### {league} model health")
        v=data.get("validation",{});p=perf.get(league.lower(),{})
        cols=st.columns(5)
        values=[("Validation games",v.get("games"),"Chronological holdout"),("Winner accuracy",pct(v.get("winner_accuracy")),"Validation"),("Margin MAE",num(v.get("margin_mae")),"Target <5.0"),("Total MAE",num(v.get("total_mae")),"Validation"),("Brier score",num(v.get("brier_score"),3),"Lower is better")]
        for col,(label,value,sub) in zip(cols,values):
            with col:metric_card(label,value,sub,"good" if label=="Margin MAE" and v.get("margin_mae",99)<5 else "")
        for warning in data.get("warnings",[]):st.warning(f"{league}: {warning}")

with tab_board:
    league=st.radio("League",["NFL","CFB"],horizontal=True,key="board_league");data=nfl if league=="NFL" else cfb;games=data.get("games",[])
    weeks=sorted({g.get("week") for g in games if g.get("week") is not None});selected=st.multiselect("Week",weeks,default=weeks)
    shown=[g for g in games if not selected or g.get("week") in selected]
    for g in shown:
        kickoff=pd.to_datetime(g.get("kickoff"),utc=True,errors="coerce");label=f"{kickoff.strftime('%a %b %d • %I:%M %p UTC') if pd.notna(kickoff) else 'TBD'} — {g.get('away')} at {g.get('home')}"
        with st.expander(label):
            c=st.columns([1.4,1,1,1,1]);c[0].markdown(f"### {g.get('away')} {g.get('projected_away')}  \n### {g.get('home')} {g.get('projected_home')}");c[1].metric("Winner",g.get("predicted_winner"));c[2].metric("Confidence",pct(g.get("winner_confidence")));c[3].metric("Projected margin",f"{g.get('projected_margin_home'):+.1f} home");c[4].metric("Projected total",g.get("projected_total"))
            st.caption(f"Reliability {pct(g.get('data_reliability'))} • Margin uncertainty ±{num(g.get('margin_uncertainty'),1)} • Current-season games: {g.get('current_season_games_min',0)}")
            books=g.get("sportsbooks",[])
            if books:
                rows=[]
                for b in books:rows.append({"Sportsbook":b.get("sportsbook"),"Home spread":b.get("home_spread"),"Home ML":b.get("home_moneyline"),"Away ML":b.get("away_moneyline"),"Total":b.get("total")})
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
            else:st.caption("No matched market lines available.")

with tab_plays:
    plays=qualified.get("plays",[])
    if not plays:st.warning("No plays currently pass every qualification gate. This is valid behavior—not a pipeline failure.")
    else:
        frame=pd.DataFrame(plays);c1,c2,c3=st.columns(3);league_filter=c1.multiselect("League",sorted(frame.league.unique()),default=sorted(frame.league.unique()));market_filter=c2.multiselect("Market",sorted(frame.market.unique()),default=sorted(frame.market.unique()));book_filter=c3.multiselect("Sportsbook",sorted(frame.sportsbook.dropna().unique()),default=sorted(frame.sportsbook.dropna().unique()))
        frame=frame[frame.league.isin(league_filter)&frame.market.isin(market_filter)&frame.sportsbook.isin(book_filter)].sort_values(["kickoff","model_probability"],ascending=[True,False])
        frame["Probability"]=frame.model_probability.map(pct);frame["Edge"]=frame.edge.map(pct)
        st.dataframe(frame[["kickoff","league","away","home","sportsbook","market","side","line","odds","Probability","Edge"]],hide_index=True,use_container_width=True)
    st.caption("Qualification means the statistical gates passed. It does not guarantee profit or eliminate variance.")

with tab_lab:
    league=st.selectbox("League",["NFL","CFB"],key="lab_league");games=(nfl if league=="NFL" else cfb).get("games",[])
    options={f"{g.get('away')} at {g.get('home')} — Week {g.get('week')}":g for g in games}
    if options:
        g=options[st.selectbox("Game",list(options))];st.subheader(f"{g['away']} at {g['home']}")
        c=st.columns(4);c[0].metric("Projected score",f"{g['away']} {g['projected_away']} – {g['home']} {g['projected_home']}");c[1].metric("Home margin",f"{g['projected_margin_home']:+.1f}");c[2].metric("Total",g["projected_total"]);c[3].metric("Reliability",pct(g["data_reliability"]))
        for book in g.get("sportsbooks",[]):
            st.markdown(f"#### {str(book.get('sportsbook','Market')).title()}")
            if book.get("evaluations"):st.dataframe(pd.DataFrame(book["evaluations"]),hide_index=True,use_container_width=True)
    else:st.info("Run the model pipeline to populate games.")

with tab_perf:
    for league in ("nfl","cfb"):
        p=perf.get(league,{}) ;st.markdown(f"### {league.upper()} locked performance")
        c=st.columns(5);vals=[("Games",p.get("games",0)),("Winner accuracy",pct(p.get("winner_accuracy"))),("Margin MAE",num(p.get("margin_mae"))),("Total MAE",num(p.get("total_mae"))),("70%+ margin MAE",num(p.get("high_confidence_margin_mae")))]
        for col,(label,value) in zip(c,vals):
            with col:metric_card(label,value)
        if p.get("confidence_buckets"):st.dataframe(pd.DataFrame(p["confidence_buckets"]).T,use_container_width=True)

with tab_validation:
    st.subheader("Promotion scorecard")
    rows=[]
    for league,data in (("NFL",nfl),("CFB",cfb)):
        v=data.get("validation",{});p=perf.get(league.lower(),{})
        rows.extend([{"League":league,"Metric":"Walk-forward margin MAE","Current":v.get("margin_mae"),"Goal":5.0,"Passed":v.get("margin_mae",99)<5},{"League":league,"Metric":"Locked live margin MAE","Current":p.get("margin_mae"),"Goal":5.0,"Passed":p.get("margin_mae") is not None and p["margin_mae"]<5},{"League":league,"Metric":"70%+ locked margin MAE","Current":p.get("high_confidence_margin_mae"),"Goal":2.5,"Passed":p.get("high_confidence_margin_mae") is not None and p["high_confidence_margin_mae"]<2.5}])
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.markdown("A model is not promoted based on one weekend. Gates require adequate sample size, calibration, stable subgroup performance, and independently locked pregame predictions.")

with tab_method:
    st.markdown("""### How the system works
1. Collect schedules, results, NFL play-by-play efficiency, and sportsbook markets.
2. Build leakage-safe pregame states using only information available before kickoff.
3. Blend current-season form with a shrinking historical prior. Current season receives 4× training weight.
4. Train independent margin and total ensembles with chronological validation.
5. Calibrate winner probabilities and estimate residual uncertainty.
6. Compare—not train against—DraftKings and Bovada spreads, moneylines, and totals.
7. Apply reliability, probability, plausible-edge, and sample-size gates.
8. Lock the latest snapshot at kickoff and grade it permanently.

### Known next-stage inputs
NFL roster/QB continuity, position-weighted injuries, offensive-line continuity, weather, travel, and coaching changes; CFB returning production, transfer portal, recruiting talent, quarterback continuity, coaching changes, FBS/FCS classification, and pace. These inputs must have timestamped historical availability before they can enter honest backtests.""")

st.caption(f"NFL generated {nfl.get('generated_at') or 'not yet'} • CFB generated {cfb.get('generated_at') or 'not yet'}")
