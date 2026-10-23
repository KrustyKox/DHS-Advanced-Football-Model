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
st.caption("Scans every scheduled team's roster and uses completed historical games only. Current season first, then prior season.")
c1, c2, c3 = st.columns(3)
with c1:
    minimum_games = st.selectbox("Minimum game sample", [10, 15, 20], index=1)
with c2:
    minimum_score = st.slider("Minimum trend score", 0, 100, 75)
with c3:
    max_player = st.selectbox("Maximum trends per player", [1, 2, 3], index=1)

if st.button("Scan today's NBA prop trends", type="primary", disabled=not bool(matchups)):
    teams = list(dict.fromkeys(code for g in matchups for code in (g["away"], g["home"])))
    season = date.year + (1 if date.month >= 7 else 0)
    candidates, errors, processed = [], [], 0
    progress = st.progress(0, text="Loading player histories...")
    total = len(teams)
    for i, team in enumerate(teams):
        try:
            athletes = roster(team)["players"]
            for athlete in athletes:
                status = str(athlete.get("availability") or "Unverified")
                if any(term in status.lower() for term in
                       ("out", "inactive", "suspended", "doubtful", "injured reserve")):
                    continue
                games = []
                for year in (season, season - 1):
                    try:
                        games.extend(history(athlete["player_id"], year))
                    except Exception:
                        pass
                clean = eligible_games(games, date)
                if len(clean) < minimum_games:
                    continue
                processed += 1
                candidates.extend(scan_player(athlete["player"], team, status,
                                              clean, min_games=minimum_games))
        except Exception as exc:
            errors.append(f"{team}: {str(exc)[:110]}")
        progress.progress((i + 1) / total, text=f"Scanned {i + 1} of {total} teams")
    qualified = [row for row in candidates if row["Trend Score"] >= minimum_score]
    st.session_state["nba_trends"] = rank_trends(qualified, max_per_player=max_player)
    st.session_state["nba_trend_diagnostics"] = {
        "players": processed, "candidates": len(candidates),
        "qualified": len(qualified), "errors": errors, "date": str(date)}
    progress.empty()

diag = st.session_state.get("nba_trend_diagnostics", {})
if diag and diag.get("date") == str(date):
    a, b, c = st.columns(3)
    a.metric("Players analyzed", diag["players"])
    b.metric("Trends qualified", diag["qualified"])
    c.metric("Top trends", len(st.session_state.get("nba_trends", [])))
    results = st.session_state.get("nba_trends", [])
    if results:
        cols = ["Player", "Team", "Prop", "Last 5", "Last 10", "Last 20",
                "Streak", "Trend Score", "Sample Hit Rate", "Avg MIN (10)", "Availability"]
        st.dataframe(pd.DataFrame(results)[cols], hide_index=True,
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
        st.info("No trends met the selected criteria. Try lowering the minimum score.")
    if diag["errors"]:
        with st.expander("Data-source errors"):
            st.write(diag["errors"])

st.divider()
st.markdown("[Official NBA injury reports](https://official.nba.com/nba-injury-report-2026-27-season/)")
st.caption("No verified lineups, live sportsbook markets, implied odds, or out-of-sample backtest. A historical streak does not guarantee the next game.")
