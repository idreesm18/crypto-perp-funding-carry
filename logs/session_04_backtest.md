# Session 4: Backtest Engine (2026-04-03)

## What was done

### 1. Implemented `src/4_backtest.py`
P&L engine that runs the carry strategy through history and produces performance metrics.

Key implementation details:
- Imports `build_portfolio` and `load_signals` from `3_portfolio.py` via `importlib` (numeric filename)
- Loads spot and perp prices at 8h settlement times (candle open = price at timestamp)
- P&L decomposition per period per asset:
  1. **Funding income**: `weight × funding_rate` (collected at settlement)
  2. **Cost drag**: `-cost` (spread on both legs per unit of turnover)
  3. **Basis P&L**: `weight_{t-1} × (spot_return - perp_return)` — MtM from holding carry position between settlements; near zero for delta-neutral
- `run_backtest(signals, prices, threshold, spread_bps)` is importable — downstream steps (on-chain overlay, regime splitting) can call with different parameters
- Sweep functions for threshold and spread robustness checks
- Pre/post 2021 regime split built into main output

### 2. Generated output files

**`data/backtest.parquet`** — 13,602 rows (6,801 per asset)

| Column | Type | Description |
|---|---|---|
| `timestamp` | datetime64[ns, UTC] | 8h funding settlement time |
| `symbol` | str | `BTC` or `ETH` |
| `weight` | float64 | Inverse-vol normalized weight |
| `funding_rate` | float64 | Raw funding rate |
| `turnover` | float64 | |delta weight| from prior period |
| `funding_pnl` | float64 | weight × funding_rate |
| `cost_drag` | float64 | -cost (negative) |
| `basis_pnl` | float64 | MtM from spot-perp return differential |
| `total_pnl` | float64 | Sum of all three components |

**`output/threshold_sweep.csv`** — 7 threshold levels × full metrics
**`output/spread_sweep.csv`** — 6 spread levels × full metrics

### 3. Created `notebooks/backtest.ipynb`
Exploration notebook with 18 sections:
- Schema, head/tail, coverage, nulls
- P&L decomposition summary table
- Cumulative P&L curve with full decomposition (funding, cost, basis, total)
- Per-period P&L distribution (total + component histograms)
- Drawdown analysis (curve with shading, duration, top 5 troughs)
- 90-day rolling Sharpe time series
- Per-asset P&L breakdown (BTC vs ETH side-by-side)
- Pre/post 2021 regime comparison table
- Yearly P&L summary (per-asset table + portfolio bar chart)
- Threshold sweep (Sharpe, return, drawdown vs threshold)
- Spread sweep (Sharpe, return vs spread + breakeven interpolation)
- Basis P&L deep-dive (cumulative curve, distribution, % of funding)
- Performance metrics summary table (full, pre-2021, post-2021, 2021-only, 2023-2024)
- Monthly P&L heatmap (year × month grid)
- Threshold × spread joint sensitivity grid (7×5 Sharpe heatmap)

### 4. Key findings

**Baseline carry (0.01% threshold, 5 bps/side):**
| Metric | Full | Pre-2021 | Post-2021 |
|---|---|---|---|
| Sharpe (ann) | 0.370 | 0.611 | 0.309 |
| Total return (bps) | 285.6 | 104.0 | 181.6 |
| Annual return (bps/yr) | 46.0 | 108.2 | 34.6 |
| Max drawdown (bps) | -1448.6 | -343.7 | -1448.6 |
| Max DD duration (days) | 1808 | 309 | 1808 |
| Win rate (active) | 61.2% | 61.1% | 61.2% |

**P&L decomposition:**
- Funding income: +6,112 bps (gross)
- Cost drag: -5,955 bps (97% of gross — costs eat almost everything)
- Basis MtM: +129 bps (2.1% of funding — confirms delta-neutrality)
- Net: +286 bps over 6.2 years

**Cost is the swing factor:**
- Breakeven spread: ~5.2 bps/side
- At 3 bps/side (market maker): Sharpe 4.3, +2,668 bps — viable
- At 5 bps/side (default): Sharpe 0.4, +286 bps — marginal
- At 7 bps/side (retail taker): Sharpe -2.2 — unprofitable

**Threshold sweep:**
- 0.05% gives best Sharpe (0.98) by only entering on truly elevated funding
- 0.005% is catastrophic (Sharpe -10.2) — churn from constant flickers above/below threshold
- Lower thresholds increase activity but destroy risk-adjusted returns via cost drag

**Strategy is a spread capture trade in disguise:** the edge isn't the signal, it's the execution. Anyone paying retail spreads cannot make this work. Only viable for participants with sub-3-bps execution.

**Implication for on-chain overlay (step 5):** The biggest value-add would be suppressing money-losing entries in 2023-2024, not finding new entries. A filter that avoids entering when carry is about to compress could flip the post-2021 Sharpe.

## What's next
**Step 5 per `project_brief.md` build order: `src/5_onchain.py`**
- On-chain exchange inflow data ingestion
- Predictive regression: does inflow Z-score predict funding rate compression?
- If significant lead-lag exists: build timing overlay signal
- If not: document as null result

## Current directory structure
```
carry_project/
  data/              9 raw parquet files + signals.parquet + portfolio.parquet + backtest.parquet (12 total)
  logs/              session_01, session_02, session_03, session_04 (this file)
  notebooks/         7 exploration notebooks (added backtest.ipynb)
  output/            threshold_sweep.csv, spread_sweep.csv
  src/
    1_data_pull.py   ✅ implemented and tested
    2_signal.py      ✅ implemented and tested
    3_portfolio.py   ✅ implemented and tested
    4_backtest.py    ✅ implemented and tested
    5_onchain.py     stub (next)
    6_regime.py      stub
  ideas.md           running ideas doc
  project_brief.md   full project spec
  README.md          project overview
  .gitignore         excludes data/, .parquet, .csv, .env, __pycache__
```
