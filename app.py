from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent;OUT=ROOT/"data"/"output"
st.set_page_config(page_title="DHS Football",page_icon="🏈",layout="wide",initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--dhs-bg:#080d14;--dhs-panel:#111923;--dhs-panel-2:#16212d;--dhs-line:#263546;--dhs-text:#f6f8fb;--dhs-muted:#91a0b2;--dhs-gold:#f5b700;--dhs-green:#31d07c}
html,body,[data-testid="stAppViewContainer"]{background:var(--dhs-bg);color:var(--dhs-text)}
[data-testid="stHeader"]{background:rgba(8,13,20,.78);backdrop-filter:blur(16px)}
#MainMenu,footer{visibility:hidden}.block-container{padding:1rem 1.35rem calc(5rem + env(safe-area-inset-bottom));max-width:1320px}
.dhs-app-header{display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:.25rem 0 1rem;padding:.8rem .95rem;background:linear-gradient(145deg,#172433,#0f1721);border:1px solid var(--dhs-line);border-radius:22px;box-shadow:0 14px 34px rgba(0,0,0,.24)}
.dhs-brand{display:flex;align-items:center;gap:.8rem;min-width:0}.dhs-logo{display:grid;place-items:center;width:48px;height:48px;flex:0 0 48px;border-radius:15px;background:linear-gradient(145deg,#ffc928,#e5a700);box-shadow:0 7px 18px rgba(245,183,0,.22);font-size:1.55rem}
.dhs-title{font-size:1.08rem;font-weight:850;line-height:1.1;letter-spacing:-.02em}.dhs-subtitle{color:var(--dhs-muted);font-size:.76rem;margin-top:.22rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.dhs-live{display:flex;align-items:center;gap:.42rem;color:#b8c4d1;font-size:.7rem;font-weight:800;letter-spacing:.08em}.dhs-dot{width:8px;height:8px;border-radius:50%;background:var(--dhs-green);box-shadow:0 0 0 4px rgba(49,208,124,.12)}
.dhs-hero{padding:1.05rem 1.1rem;margin:.15rem 0 1rem;border-radius:20px;background:radial-gradient(circle at 90% 0%,rgba(245,183,0,.18),transparent 38%),linear-gradient(145deg,#172332,#101720);border:1px solid var(--dhs-line)}.dhs-hero-kicker{color:var(--dhs-gold);font-size:.72rem;font-weight:800;letter-spacing:.11em;text-transform:uppercase}.dhs-hero-title{font-size:1.65rem;font-weight:850;letter-spacing:-.035em;margin:.28rem 0}.dhs-hero-copy{color:#a8b4c2;font-size:.88rem;max-width:700px}
.dhs-card{background:linear-gradient(145deg,var(--dhs-panel-2),var(--dhs-panel));border:1px solid var(--dhs-line);border-radius:18px;padding:15px 16px;height:100%;box-shadow:0 8px 22px rgba(0,0,0,.13)}.dhs-label{color:var(--dhs-muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.09em;font-weight:700}.dhs-value{font-size:1.52rem;font-weight:820;color:var(--dhs-text);margin:.14rem 0}.good{color:var(--dhs-green)}.bad{color:#ff6675}.warn{color:var(--dhs-gold)}.small{font-size:.78rem;color:#9eabb9}
.dhs-scorecard{background:linear-gradient(145deg,#172332,#101821);border:1px solid var(--dhs-line);border-radius:18px;padding:1rem;margin:.2rem 0 .85rem}.dhs-score-row{display:grid;grid-template-columns:1fr auto;align-items:center;gap:1rem;padding:.48rem 0}.dhs-score-row+.dhs-score-row{border-top:1px solid rgba(145,160,178,.14)}.dhs-team{font-size:1rem;font-weight:760}.dhs-site{display:inline-block;width:1.15rem;color:var(--dhs-muted);font-size:.68rem;font-weight:700}.dhs-score{font-size:1.45rem;font-weight:850}.dhs-score-meta{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:.7rem}.dhs-chip{padding:.36rem .58rem;border-radius:999px;background:#202d3b;color:#c8d2dc;font-size:.72rem;font-weight:700}.dhs-chip.gold{background:rgba(245,183,0,.13);color:#ffd65a}
[data-baseweb="tab-list"]{gap:.35rem;overflow-x:auto;scrollbar-width:none;padding:.28rem 0 .62rem;position:sticky;top:2.8rem;z-index:99;background:linear-gradient(var(--dhs-bg) 75%,transparent)}[data-baseweb="tab-list"]::-webkit-scrollbar{display:none}[data-baseweb="tab"]{height:44px;white-space:nowrap;border-radius:999px;padding:0 .9rem;background:#121b25;border:1px solid #202d3b}[data-baseweb="tab"][aria-selected="true"]{background:#f5b700;color:#111820;border-color:#f5b700}[data-baseweb="tab-highlight"]{display:none}
[data-testid="stExpander"]{border:1px solid var(--dhs-line);border-radius:17px!important;background:#0f161f;overflow:hidden;margin-bottom:.65rem}[data-testid="stDataFrame"]{border:1px solid var(--dhs-line);border-radius:15px;overflow:hidden}.stButton button,.stDownloadButton button{min-height:44px;border-radius:13px}.stSelectbox div[data-baseweb="select"]>div,.stMultiSelect div[data-baseweb="select"]>div{min-height:44px;border-radius:13px}.stAlert{border-radius:15px}
@media(max-width:768px){.block-container{padding:.65rem .72rem calc(5.5rem + env(safe-area-inset-bottom))}.dhs-app-header{position:relative;margin:0 0 .65rem;border-radius:19px;padding:.72rem .78rem}.dhs-logo{width:43px;height:43px;flex-basis:43px;border-radius:13px}.dhs-title{font-size:1rem}.dhs-live{font-size:.62rem}.dhs-hero{padding:.9rem;border-radius:18px}.dhs-hero-title{font-size:1.36rem}.dhs-value{font-size:1.35rem}[data-baseweb="tab-list"]{top:2.55rem;margin-left:-.72rem;margin-right:-.72rem;padding-left:.72rem;padding-right:.72rem}[data-baseweb="tab"]{height:42px;padding:0 .78rem;font-size:.8rem}.dhs-scorecard{padding:.82rem}.dhs-score{font-size:1.3rem}h1{font-size:1.7rem!important}h2{font-size:1.35rem!important}h3{font-size:1.15rem!important}}
</style>""",unsafe_allow_html=True)


@st.cache_data(ttl=60)
def load(name):
    path=OUT/name
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return {}


def metric_card(label,value,sub="",state=""):
    st.markdown(f'<div class="dhs-card"><div class="dhs-label">{label}</div><div class="dhs-value {state}">{value}</div><div class="small">{sub}</div></div>',unsafe_allow_html=True)


def pct(v):return "—" if v is None else f"{100*float(v):.1f}%"
def num(v,d=2):return "—" if v is None else f"{float(v):.{d}f}"
def central_time(value):
    stamp=pd.to_datetime(value,utc=True,errors="coerce")
    return stamp.tz_convert("America/Chicago") if pd.notna(stamp) else stamp


def scorecard(game):
    winner=game.get("predicted_winner") or "TBD"
    confidence=pct(game.get("winner_confidence"))
    reliability=pct(game.get("data_reliability"))
    margin=game.get("projected_margin_home")
    margin_text="—" if margin is None else f"{float(margin):+.1f} home"
    return f'''<div class="dhs-scorecard">
      <div class="dhs-score-row"><div class="dhs-team"><span class="dhs-site">AWAY</span> {game.get("away","—")}</div><div class="dhs-score">{game.get("projected_away","—")}</div></div>
      <div class="dhs-score-row"><div class="dhs-team"><span class="dhs-site">HOME</span> {game.get("home","—")}</div><div class="dhs-score">{game.get("projected_home","—")}</div></div>
      <div class="dhs-score-meta"><span class="dhs-chip gold">Pick: {winner}</span><span class="dhs-chip">Confidence {confidence}</span><span class="dhs-chip">Margin {margin_text}</span><span class="dhs-chip">Total {game.get("projected_total","—")}</span><span class="dhs-chip">Reliability {reliability}</span></div>
    </div>'''


nfl,cfb,perf,qualified,underdogs=load("nfl.json"),load("cfb.json"),load("performance.json"),load("qualified_plays.json"),load("underdog_ml_picks.json")
st.markdown('''<div class="dhs-app-header"><div class="dhs-brand"><div class="dhs-logo">🏈</div><div><div class="dhs-title">DHS Football</div><div class="dhs-subtitle">Advanced game markets • Central Time</div></div></div><div class="dhs-live"><span class="dhs-dot"></span>RESEARCH</div></div>''',unsafe_allow_html=True)
tab_overview,tab_board,tab_plays,tab_underdogs,tab_lab,tab_perf,tab_validation,tab_method=st.tabs(["🏠 Home","🏈 Games","✅ Picks","🐶 Underdogs","🔬 Matchup","📊 Results","🎯 Goals","ℹ️ About"])

with tab_overview:
    st.markdown('''<div class="dhs-hero"><div class="dhs-hero-kicker">Decision dashboard</div><div class="dhs-hero-title">This week’s football board</div><div class="dhs-hero-copy">Independent projections, current market comparisons, and kickoff-locked results in one mobile-first view.</div></div>''',unsafe_allow_html=True)
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
        kickoff=central_time(g.get("kickoff"));label=f"{kickoff.strftime('%a %b %d • %I:%M %p %Z') if pd.notna(kickoff) else 'TBD'} — {g.get('away')} at {g.get('home')}"
        with st.expander(label):
            st.markdown(scorecard(g),unsafe_allow_html=True)
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
        frame["Game time (CT)"]=pd.to_datetime(frame.kickoff,utc=True,errors="coerce").dt.tz_convert("America/Chicago").dt.strftime("%a %b %d • %I:%M %p %Z")
        frame["Probability"]=frame.model_probability.map(pct);frame["Edge"]=frame.edge.map(pct)
        st.dataframe(frame[["Game time (CT)","league","away","home","sportsbook","market","side","line","odds","Probability","Edge"]],hide_index=True,use_container_width=True)
    st.caption("Qualification means the statistical gates passed. It does not guarantee profit or eliminate variance.")

with tab_underdogs:
    st.subheader("Underdogs projected to win outright")
    st.caption("A team appears here only when it has the longer sportsbook moneyline and the model independently predicts it to win.")
    picks=underdogs.get("picks",[])
    if not picks:
        st.warning("No current sportsbook underdogs are projected to win, or market moneylines have not been loaded yet.")
    else:
        frame=pd.DataFrame(picks)
        c1,c2,c3=st.columns(3)
        leagues=c1.multiselect("League",sorted(frame.league.unique()),default=sorted(frame.league.unique()),key="dog_league")
        books=c2.multiselect("Sportsbook",sorted(frame.sportsbook.dropna().unique()),default=sorted(frame.sportsbook.dropna().unique()),key="dog_book")
        status=c3.selectbox("Status",["All picks","Qualified only","Watchlist only"])
        frame=frame[frame.league.isin(leagues)&frame.sportsbook.isin(books)]
        if status=="Qualified only":frame=frame[frame.qualified]
        elif status=="Watchlist only":frame=frame[~frame.qualified]
        frame=frame.sort_values(["kickoff","probability_edge"],ascending=[True,False])
        frame["Game time (CT)"]=pd.to_datetime(frame.kickoff,utc=True,errors="coerce").dt.tz_convert("America/Chicago").dt.strftime("%a %b %d • %I:%M %p %Z")
        frame["Model win %"]=frame.model_probability.map(pct);frame["Market fair %"]=frame.market_probability.map(pct);frame["Probability edge"]=frame.probability_edge.map(pct);frame["Confidence"]=frame.winner_confidence.map(pct);frame["Reliability"]=frame.data_reliability.map(pct)
        frame["Status"]=frame.qualified.map({True:"QUALIFIED",False:"WATCHLIST"})
        st.dataframe(frame[["Game time (CT)","league","away","home","sportsbook","underdog","moneyline","Model win %","Market fair %","Probability edge","Confidence","Reliability","Status"]],hide_index=True,use_container_width=True)
        with st.expander("Why watchlist picks did not qualify"):
            review=frame[~frame.qualified][["underdog","sportsbook","gate_reasons"]]
            st.dataframe(review,hide_index=True,use_container_width=True)
    st.info("An underdog prediction is not automatically a wager. Only rows marked QUALIFIED have passed the probability, edge, reliability, validation-sample and plausibility gates.")

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
