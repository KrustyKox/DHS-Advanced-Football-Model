# DHS Advanced Football Model

An isolated research and market-evaluation system for NFL and college football moneylines, spreads, and totals. It does not import, modify, or publish into the original DHS Football Model repository.

## Design principles

- GitHub Actions performs data collection, training, prediction, market evaluation, locking, and grading.
- Streamlit reads committed JSON and provides an evaluation dashboard.
- Sportsbook prices are evaluation targets, never model features.
- Predictions lock at kickoff and cannot be rewritten by later model runs.
- Current-season evidence receives the largest weight; history remains a shrinking prior when the current sample is small.
- A pick is not labeled qualified merely because its raw edge is large. Calibration, uncertainty, data completeness, plausible-edge, and validation gates must also pass.

## Accuracy targets

The research goals are an overall margin MAE below 5.0 points and a margin MAE below 2.5 points for predictions rated above 70% confidence. These are difficult targets, not claims. The dashboard reports sample size and pass/fail status and will not hide misses.

## Setup

1. Add `PARLAY_API_KEY` in **GitHub → Settings → Secrets and variables → Actions**.
2. If ParlayAPI uses different event-odds paths, add repository variables `PARLAY_NFL_ODDS_PATH` and `PARLAY_CFB_ODDS_PATH`.
3. Run the `Update Advanced Football Model` workflow.
4. Deploy `app.py` on Streamlit Community Cloud.

The default configurable paths are:

- NFL: `/v1/sports/americanfootball_nfl/odds`
- CFB: `/v1/sports/americanfootball_ncaaf/odds`

Only DraftKings and Bovada are requested by default. The API key is used only by GitHub Actions; the Streamlit app does not call ParlayAPI.

## Dashboard

- Executive overview and target tracking
- Date-ordered NFL and CFB boards
- Qualified ATS, moneyline, and total plays
- Matchup lab with model/market differences and uncertainty
- Locked performance and edge-bucket diagnostics
- Walk-forward validation, calibration, and methodology

## Development

```bash
pip install -r requirements.txt
pytest -q
python scripts/run_pipeline.py
streamlit run app.py
```

If market credentials are absent, the model still builds projections and records a market-data warning. It will not invent sportsbook prices.

