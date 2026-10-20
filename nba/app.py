"""Independent NBA research dashboard. Real data; unvalidated estimates."""
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
st.warning("RESEARCH ONLY — estimates are not calibrated or validated. Injury availability may be incomplete; no live odds.", icon="⚠️")

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
st.subheader("Step 4 — Real-data player projection baseline")
st.caption("Weighted recent-game estimates. Probability thresholds are preliminary and NOT backtested or betting-ready.")
from projections import project_player
from team_model import allocate, recent_team_scores
from thresholds import adjusted_thresholds

if "roster_result" in locals() and roster_result.get("players"):
    if st.button("Generate baseline projections for selected team", type="primary"):
        st.session_state.pop("nba_baseline_rows", None)
        st.session_state.pop("nba_baseline_thresholds", None)
        st.session_state.pop("nba_team_diagnostics", None)
        results, skipped, threshold_rows = [], [], []
        player_histories = {}
        with st.spinner("Retrieving historical games and building player estimates..."):
            for athlete in roster_result["players"]:
                status = str(athlete.get("availability") or "Unverified").strip().lower()
                # Explicitly excluded statuses must never produce active-player projections.
                if any(term in status for term in ("out", "inactive", "suspended", "doubtful", "injured reserve")):
                    skipped.append(f'{athlete["player"]}: excluded due to availability status ({athlete.get("availability")})')
                    continue
                try:
                    history = cached_game_log(athlete["player_id"], 2026)
                    estimate = project_player(history["games"])
                    player_histories[athlete["player_id"]] = history["games"]
                    row = {"Player": athlete["player"], "Team": athlete["team"],
                           "Availability": athlete["availability"], "Games": estimate["games_used"]}
                    row.update(estimate["projections"])
                    results.append(row)
                    threshold_rows.append({"Player": athlete["player"], "Team": athlete["team"],
                                           "player_id": athlete["player_id"],
                                           "thresholds": estimate["thresholds"],
                                           "projections": estimate["projections"]})
                except Exception as exc:
                    skipped.append(f'{athlete["player"]}: {str(exc)[:90]}')
        if results:
            try:
                scores = recent_team_scores(roster_team, selected_date.year, selected_date)
                if len(scores) < 5:
                    raise ValueError(f"Only {len(scores)} completed team games; need 5")
                target = sum(scores) / len(scores)
                results, diagnostics = allocate(results, target)
                by_name = {r["Player"]: r for r in results}
                for item in threshold_rows:
                    adjusted = by_name.get(item["Player"])
                    if adjusted:
                        item["thresholds"] = adjusted_thresholds(
                            player_histories[item["player_id"]],
                            item["projections"], adjusted)
                        item["projections"] = {k: adjusted[k] for k in item["projections"] if k in adjusted}
                diagnostics["target"] = round(target, 1)
                diagnostics["games"] = len(scores)
                st.session_state["nba_team_diagnostics"] = diagnostics
            except Exception as exc:
                st.error(f"Team allocation unavailable: {exc}")
                st.warning("Unconstrained projections withheld rather than displayed.")
                results = []
        if results:
            st.session_state["nba_baseline_rows"] = results
            st.session_state["nba_baseline_thresholds"] = threshold_rows
            st.session_state["nba_baseline_skipped"] = skipped
            st.session_state["nba_baseline_team"] = roster_team
            st.session_state["nba_baseline_game"] = (str(selected_date), selected_game)
        else:
            st.error("No verified player game logs could be projected. No placeholder results were substituted.")
            st.caption("First error: " + (skipped[0] if skipped else "Unknown"))
    if st.session_state.get("nba_baseline_rows") and st.session_state.get("nba_baseline_team") == roster_team and st.session_state.get("nba_baseline_game") == (str(selected_date), selected_game):
        diag = st.session_state.get("nba_team_diagnostics", {})
        if diag:
            c1, c2, c3 = st.columns(3)
            c1.metric("Projected team PTS", diag["team_points"])
            c2.metric("Allocated team MIN", diag["team_minutes"])
            c3.metric("Historical team PTS", diag["target"])
            st.caption(f'Original independent totals: {diag["raw_points"]} PTS, {diag["raw_minutes"]} MIN. Historical sample: {diag["games"]} games.')
        frame = pd.DataFrame(st.session_state["nba_baseline_rows"])
        st.dataframe(frame, hide_index=True, use_container_width=True)
        st.caption(f'{len(frame)} players estimated; {len(st.session_state.get("nba_baseline_skipped", []))} skipped for missing/insufficient data.')
        with st.expander("Skipped players and data issues"):
            st.write(st.session_state.get("nba_baseline_skipped", []))
        st.warning("Players explicitly marked OUT, inactive, doubtful, or suspended are excluded. Unverified/questionable players may remain visible for research only; NO projections are qualified betting plays until availability is confirmed.")
else:
    st.info("Choose a scheduled game and load a team roster before generating baseline projections.")

st.divider()
st.subheader("Step 5 — Adjusted player probability thresholds")
st.caption("Preliminary modeled thresholds from team-adjusted means and historical game variability. NOT backtested or betting-ready.")
threshold_data = st.session_state.get("nba_baseline_thresholds", [])
same_matchup = ("real_games" in locals() and real_games and
                st.session_state.get("nba_baseline_team") == roster_team and
                st.session_state.get("nba_baseline_game") == (str(selected_date), selected_game))
if same_matchup and threshold_data:
    stat = st.selectbox("Statistic", ["PTS", "REB", "AST", "3PM", "STL", "BLK", "TOV", "PRA", "PR", "PA", "RA"])
    confidence = st.select_slider("Modeled confidence", options=[50, 60, 70, 80, 90, 95], value=80)
    rows = []
    for athlete in threshold_data:
        levels = athlete["thresholds"].get(stat)
        if not levels:
            continue
        item = {"Player": athlete["Player"], "Team": athlete["Team"],
                "Projected": athlete["projections"].get(stat)}
        for pct in (50, 60, 70, 80, 90, 95):
            item[f"{pct}%"] = f'{levels[str(pct)]}+'
        rows.append(item)
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     column_config={f"{confidence}%": st.column_config.TextColumn(f"★ {confidence}%")})
        st.warning("These are statistical estimates, not verified 50–95% success probabilities. Injury status may be unverified; do not treat thresholds as betting edges.")
    else:
        st.info("No usable historical distribution for this statistic.")
else:
    st.info("Generate team-constrained projections above to populate adjusted probability thresholds.")
st.divider()
st.caption("NBA development branch only • Football production files unchanged.")
