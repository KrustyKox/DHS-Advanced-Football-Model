"""DHS NBA historical player-prop trend finder. Descriptive research only."""
import pandas as pd
import streamlit as st
from schedule import load_schedule, games_for_date, eastern_today
from availability import get_team_availability
from stats import game_log
from trends import eligible_games, scan_player, rank_trends

st.set_page_config(page_title="DHS NBA Trends", page_icon="🏀", layout="wide",
                   initial_sidebar_state="collapsed")
st.title("🏀 DHS NBA Trend Finder")
st.caption("Historical player-prop consistency across today's NBA matchups")
st.warning("RESEARCH ONLY — trend scores are NOT win probabilities. No sportsbook odds or verified game-day availability.")

@st.cache_data(ttl=1800, show_spinner=False)
def schedule(day):
    return games_for_date(load_schedule(day), day)

@st.cache_data(ttl=1800, show_spinner=False)
def roster(team):
    return get_team_availability(team)

@st.cache_data(ttl=3600, show_spinner=False)
def history(player_id, season):
    return game_log(player_id, season)["games"]

date = st.date_input("NBA game date (Eastern)", value=eastern_today())
try:
    matchups = schedule(date)
except Exception as exc:
    matchups = []
    st.error(f"Schedule unavailable: {exc}")
if matchups:
    st.write("Matchups: " + " · ".join(g["away"] + " @ " + g["home"] for g in matchups))
else:
    st.info("No NBA games available for this date.")

st.subheader("Top 25 Historical Prop Trends")
st.caption("Precomputed daily on GitHub. Only exact sportsbook-quoted thresholds priced -500 or better qualify.")
import requests

@st.cache_data(ttl=600, show_spinner=False)
def load_snapshot(day):
    url = ("https://raw.githubusercontent.com/KrustyKox/"
           "DHS-Advanced-Football-Model/feature/nba-player-projections/nba/data/"
           + str(day) + ".json")
    response = requests.get(url, timeout=12, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    payload = response.json()
    if payload.get("date") != str(day):
        raise ValueError("Snapshot date mismatch")
    return payload

try:
    snapshot = load_snapshot(date)
    st.success(f'Precomputed {snapshot["generated_utc"]} UTC · {snapshot["teams"]} teams scanned')
    st.caption(snapshot.get("market_status", "Market verification unavailable for this snapshot"))
    st.session_state["nba_trends"] = snapshot["trends"]
    st.session_state["nba_trend_diagnostics"] = {
        "players": snapshot["players_analyzed"], "qualified": snapshot["qualified"],
        "errors": snapshot.get("errors", []), "date": str(date)}
except Exception as exc:
    st.info("No precomputed snapshot is available for this date yet. The scheduled GitHub scan must run and commit a snapshot first.")
    st.caption(f"Snapshot retrieval: {str(exc)[:140]}")
    st.session_state.pop("nba_trends", None)
    st.session_state.pop("nba_trend_diagnostics", None)

diag = st.session_state.get("nba_trend_diagnostics", {})
if diag and diag.get("date") == str(date):
    a, b, c = st.columns(3)
    a.metric("Players analyzed", diag["players"])
    b.metric("Trends qualified", diag["qualified"])
    c.metric("Top trends", len(st.session_state.get("nba_trends", [])))
    results = st.session_state.get("nba_trends", [])
    if results:
        cols = ["Player", "Team", "Prop", "American Odds", "Sportsbook", "Last 5", "Last 10", "Last 20",
                "Streak", "Trend Score", "Sample Hit Rate", "Avg MIN (10)", "Availability"]
        st.dataframe(pd.DataFrame(results)[[c for c in cols if c in pd.DataFrame(results).columns]], hide_index=True,
                     use_container_width=True)
        st.caption("Trend Score (0–100) combines historical hit rates, streak recency, sample size and minutes stability. It is NOT a calibrated hit probability.")
        labels = [f'{i+1}. {r["Player"]} — {r["Prop"]}' for i, r in enumerate(results)]
        chosen = st.selectbox("Inspect game-by-game evidence", range(len(results)),
                              format_func=lambda i: labels[i])
        selected = results[chosen]
        st.write(f'**{selected["Player"]}: {selected["Prop"]}** — {selected["Last 20"]} in last 20 available games; current streak {selected["Streak"]}')
        st.dataframe(pd.DataFrame(selected["Evidence"]), hide_index=True,
                     use_container_width=True)
        st.caption("The evidence table shows only completed games prior to the selected date.")
    else:
        st.info("No sportsbook-verified trends qualified. No odds feed may be configured, exact offers may be missing, or prices may be worse than -500.")
    if diag["errors"]:
        with st.expander("Data-source errors"):
            st.write(diag["errors"])

st.divider()
st.markdown("[Official NBA injury reports](https://official.nba.com/nba-injury-report-2026-27-season/)")
st.caption("No verified lineups, live sportsbook markets, implied odds, or out-of-sample backtest. A historical streak does not guarantee the next game.")
