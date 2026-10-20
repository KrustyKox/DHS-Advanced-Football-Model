# DHS NBA Player Projections (isolated prototype)

This folder is intentionally independent of the NFL/CFB application. Run with:

```bash
pip install -r nba/requirements.txt
streamlit run nba/app.py
```

The initial dashboard is a mobile-first UI prototype using clearly labeled synthetic demo data. **It does not produce validated predictions or betting recommendations yet.** No existing production files, jobs, or dependencies are changed.

Next milestones:
1. Acquire and validate NBA player game logs, schedules, roster status, and injury reports.
2. Fit a minutes model and per-minute stat distributions using chronological out-of-sample testing.
3. Jointly simulate game pace, team points, and player box scores with internally consistent totals.
4. Produce calibrated 50/60/70/80/90/95% integer thresholds for every stat.
5. Add sportsbook odds comparisons and correlation-aware parlay research.
6. Add immutable pre-tipoff prediction snapshots and grading.
