"""Independent NBA mobile-first dashboard prototype. Synthetic data only."""
import pandas as pd
import streamlit as st

st.set_page_config(page_title="DHS NBA", page_icon="🏀", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 1.2rem; padding-left: 1rem; padding-right: 1rem}
h1 {font-size: 1.8rem !important; letter-spacing: -.035em}
[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.18); border-radius: 14px; padding: .7rem}
[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden}
</style>
""", unsafe_allow_html=True)

st.title("🏀 DHS NBA")
st.caption("Player projections • Mobile-first research dashboard")
st.warning("DEMO ONLY — synthetic players and invented values. No live odds or validated NBA predictions.", icon="⚠️")

from schedule import load_schedule, games_for_date, eastern_today

@st.cache_data(ttl=1800, show_spinner=False)
def cached_schedule(day):
    return load_schedule(day)

st.subheader("NBA Schedule — Live data")
selected_date = st.date_input("Game date (Eastern)", value=eastern_today())
try:
    real_games = games_for_date(cached_schedule(selected_date), selected_date)
    if real_games:
        labels = [f'{g["away"]} @ {g["home"]} · {g["status"]}' for g in real_games]
        selected_game = st.selectbox("Today's games", labels)
        st.caption("Source: ESPN public scoreboard · refreshed every 30 minutes")
    else:
        st.info("No NBA games listed for this date.")
except Exception as exc:
    st.error(f"NBA schedule unavailable: {exc}")
    st.caption("No games will be invented if the live feed fails.")

st.divider()
st.subheader("Step 2 — Current team rosters & injury watch")
st.caption("Live roster source: ESPN (unofficial). Injury listings are incomplete and do not confirm game-day availability.")
from availability import get_team_availability

@st.cache_data(ttl=900, show_spinner=False)
def cached_availability(team_code):
    return get_team_availability(team_code)

if "real_games" in locals() and real_games:
    selected = real_games[labels.index(selected_game)]
    selected_teams = [selected["away"], selected["home"]]
    roster_team = st.selectbox("Roster team", selected_teams)
    if st.button("Refresh roster / injuries"):
        cached_availability.clear()
        st.rerun()
    try:
        roster_result = cached_availability(roster_team)
        st.caption(f'Checked (UTC): {roster_result["checked_utc"]} · Injury feed: {roster_result["injury_feed"]}')
        st.caption(f'Injury records returned: {roster_result.get("injury_records", 0)} · Matched to roster: {roster_result.get("matched_injuries", 0)}')
        st.markdown("[Cross-check official NBA injury reports](https://official.nba.com/nba-injury-report-2026-27-season/)")
        roster_frame = pd.DataFrame(roster_result["players"])
        st.dataframe(roster_frame[["player", "position", "jersey", "availability", "injury_detail"]],
                     hide_index=True, use_container_width=True)
        st.warning("Player availability is NOT verified. Players missing from injury listings are not confirmed active. Do not use these statuses for betting yet.")
    except Exception as exc:
        st.error(f"Roster feed unavailable: {exc}")
        st.caption("No roster is fabricated when a feed fails.")
else:
    st.info("Choose a date with an NBA matchup to inspect the teams' rosters.")

st.divider()
st.subheader("Step 3 — Real player game logs")
st.caption("Historical game statistics from ESPN's unofficial player feed. These are past results, not projections.")
from stats import game_log

@st.cache_data(ttl=3600, show_spinner=False)
def cached_game_log(player_id, season):
    return game_log(player_id, season)

if "roster_result" in locals() and roster_result.get("players"):
    roster_players = roster_result["players"]
    player_names = [p["player"] for p in roster_players]
    player_choice = st.selectbox("Player for historical stats", player_names)
    selected_player = roster_players[player_names.index(player_choice)]
    season_choice = st.number_input("Season ending year", min_value=2020, max_value=2030,
                                    value=2026, step=1)
    if st.button("Load player game log"):
        try:
            log = cached_game_log(selected_player["player_id"], int(season_choice))
            log_df = pd.DataFrame(log["games"])
            st.success(f'Loaded {len(log_df)} recorded games · retrieved {log["checked_utc"]}')
            st.dataframe(log_df, hide_index=True, use_container_width=True)
            summary_cols = [c for c in ["MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV"] if c in log_df]
            if summary_cols:
                st.caption("Observed per-game averages (not injury-adjusted)")
                st.dataframe(log_df[summary_cols].mean(numeric_only=True).round(1).to_frame("Average").T,
                             hide_index=True, use_container_width=True)
        except Exception as exc:
            st.error(f"Player statistics unavailable: {exc}")
            st.caption("No historical results are fabricated when the provider blocks requests or changes its format.")
else:
    st.info("Load a roster from a scheduled game above to inspect real player game logs.")

st.divider()
st.subheader("Player projection prototype")
st.caption("Player data below remains synthetic until roster, injury, and statistics ingestion is validated.")
game = "Synthetic demonstration matchup"
view = st.segmented_control("View", ["Box Score", "Probability Tables", "Game Outlook"], default="Probability Tables")
players = [
    ("Player A", "HOME", "Starter", 35, 26.4, 8.1, 5.8, 2.9, 1.1, .6, 2.7),
    ("Player B", "HOME", "Starter", 32, 19.1, 6.9, 4.3, 2.1, .8, .4, 1.8),
    ("Player C", "HOME", "Bench", 23, 11.6, 5.4, 2.8, 1.3, .7, .5, 1.2),
    ("Player D", "AWAY", "Starter", 36, 28.2, 6.3, 8.2, 3.2, 1.4, .3, 3.1),
    ("Player E", "AWAY", "Starter", 33, 21.7, 9.5, 3.6, 1.8, .9, .8, 2.4),
    ("Player F", "AWAY", "Bench", 25, 12.3, 4.6, 5.2, 1.6, .7, .2, 1.5),
]
cols = ["Player", "Team", "Role", "MIN", "PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV"]
df = pd.DataFrame(players, columns=cols)
df["PRA"] = df["PTS"] + df["REB"] + df["AST"]
df["PR"] = df["PTS"] + df["REB"]
df["PA"] = df["PTS"] + df["AST"]
df["RA"] = df["REB"] + df["AST"]
team = st.segmented_control("Lineup", ["Both", "HOME", "AWAY"], default="Both")
role = st.selectbox("Players", ["All rotation players", "Starters", "Bench"], index=0)
shown = df.copy()
if team != "Both":
    shown = shown[shown["Team"] == team]
if role != "All rotation players":
    shown = shown[shown["Role"] == ("Starter" if role == "Starters" else "Bench")]

if view == "Box Score":
    st.subheader("Projected box score")
    st.dataframe(shown[cols + ["PRA"]], hide_index=True, use_container_width=True)
elif view == "Probability Tables":
    stat = st.selectbox("Statistic", ["PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV", "PRA", "PR", "PA", "RA"])
    focus = st.select_slider("Highlight confidence", options=[50, 60, 70, 80, 90, 95], value=80)
    st.caption("Threshold = estimated minimum whole-number result reached with at least the stated probability. Placeholder distributions only.")
    # Illustrative monotonically decreasing thresholds; replace with calibrated empirical predictive CDFs.
    spreads = {"PTS": 7, "REB": 3, "AST": 3, "3PM": 1.5, "STL": 1, "BLK": 1, "TOV": 1.5, "PRA": 10, "PR": 8, "PA": 8, "RA": 5}
    offsets = {50: 0, 60: .25, 70: .5, 80: .85, 90: 1.3, 95: 1.65}
    rows = []
    for _, p in shown.iterrows():
        item = {"Player": p["Player"], "Team": p["Team"], "Mean": round(float(p[stat]), 1)}
        for pct in [50, 60, 70, 80, 90, 95]:
            item[f"{pct}%"] = f"{max(0, int(p[stat] - spreads[stat] * offsets[pct]))}+"
        rows.append(item)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                 column_config={f"{focus}%": st.column_config.TextColumn(f"★ {focus}%")})
    st.info("For real predictions, thresholds must come from simulated distributions, not the demonstration calculation.")
else:
    a, b = st.columns(2)
    a.metric("Home score", "118.4")
    b.metric("Away score", "111.7")
    c, d = st.columns(2)
    c.metric("Projected spread", "HOME -6.7")
    d.metric("Projected total", "230.1")
    st.caption("Illustrative game figures; not derived from the sample player data.")

st.divider()
st.caption("NBA development module • No football model files or live production workflows modified.")
