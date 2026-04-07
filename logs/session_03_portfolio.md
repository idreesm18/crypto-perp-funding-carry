# Session 3: Portfolio Construction (2026-04-03)

## What was done

### 1. Implemented `src/3_portfolio.py`
Builds position weights (inverse-vol sizing), computes turnover, and models transaction costs.

Key implementation details:
- Loads `data/signals.parquet`, drops 90 null-vol warm-up rows
- Position sizing: `weight = (1/realized_vol_30d) * signal`, normalized so weights sum to 1 across assets per timestamp
- When only one asset is active it gets weight=1.0; when both are active, BTC gets ~56% (lower vol)
- Turnover: `|weight_now - weight_previous|` per asset per period
- Cost model: `turnover × 2 × spread_bps / 10,000` — both legs (spot + perp) per unit of turnover
- Default spread: 5 bps per instrument per trade direction (conservative)
- `build_portfolio(signals, threshold, spread_bps)` is importable — backtest can call with different parameters without re-running the script
- Threshold re-applied from `funding_rate` directly, so sweeps don't require re-running `2_signal.py`

### 2. Generated `data/portfolio.parquet`

| Column | Type | Description |
|---|---|---|
| `timestamp` | datetime64[ns, UTC] | 8h funding settlement time |
| `symbol` | str | `BTC` or `ETH` |
| `funding_rate` | float64 | Raw funding rate at this settlement |
| `realized_vol_30d` | float64 | Annualized 30d vol from hourly spot returns |
| `signal` | int64 | 1 = in carry, 0 = out (at 0.01% threshold) |
| `weight` | float64 | Inverse-vol normalized weight (0 when signal off) |
| `turnover` | float64 | |delta weight| from prior period |
| `cost` | float64 | Turnover × 2 × spread_bps / 10,000 |

- 13,602 rows (6,801 per asset)
- Date range: 2020-01-16 → 2026-03-31

### 3. Created `notebooks/portfolio.ipynb`
Exploration notebook covering:
- Schema, head/tail, coverage, null check
- Weight distribution per asset (BTC vs ETH)
- Weight allocation time series with 2021 regime split
- BTC weight share when both active (mean=0.558, driven by ETH/BTC vol ratio of 1.25)
- Turnover analysis: time series and distribution (19.2% of periods have trades)
- Trade event breakdown: entries, exits, rebalances, holds
- Cost analysis: cumulative cost curve and per-period distribution
- Funding income vs cost drag: cumulative comparison chart
- Spread sensitivity: net P&L at 1-10 bps/side
- Pre-2021 vs post-2021 regime comparison table
- Yearly portfolio summary (funding, cost, net by year)
- Holding period duration histograms

### 4. Key findings

**Yearly net P&L (at 5 bps/side):**
| Year | BTC net (bps) | ETH net (bps) |
|------|--------------|---------------|
| 2020 | +115.5 | -46.4 |
| 2021 | +419.7 | +491.4 |
| 2022 | 0.0 | 0.0 |
| 2023 | -176.2 | -135.7 |
| 2024 | -236.9 | -274.3 |
| 2025–26 | 0.0 | 0.0 |

- **Total: +6,112 bps funding income vs 5,955 bps cost = +157 bps net over 6 years.** At 5 bps/side the strategy barely breaks even (~25 bps/year).
- **2021 carries the entire strategy.** Without 2021, cumulative P&L is negative. 2023 and 2024 actively lose money — funding isn't high enough to cover entry/exit costs.
- **Cost assumption is the swing factor.** At 3 bps/side: +2,539 bps net (~400 bps/year, viable). At 5 bps/side: +157 bps (marginal). At 7 bps/side: -2,225 bps (unprofitable).
- **Short holding periods kill profitability.** Median hold is 2-3 periods (16-24h). Most trades are quick flickers above threshold — you pay full round-trip cost for 1-2 funding payments.
- **Post-2021 is essentially dead.** BTC post-2021 nets +6.7 bps over 5+ years. ETH post-2021 is +81.3 bps — marginally positive only because of a few 2024 episodes.
- **Implication for the on-chain overlay (step 5):** the biggest value-add would be suppressing the money-losing entries in 2023-2024, not finding new entries. A filter that avoids short-duration false signals could materially improve the post-2021 results.

## What's next
**Step 4 per `project_brief.md` build order: `src/4_backtest.py`**
- P&L engine: cumulative P&L curve, Sharpe, max drawdown
- Decompose returns into funding income, cost drag, mark-to-market residual
- Threshold sweep and cost sensitivity as robustness checks
- Confirm baseline carry results look reasonable before adding on-chain overlay

## Current directory structure
```
carry_project/
  data/              9 raw parquet files + signals.parquet + portfolio.parquet (11 total)
  logs/              session_01, session_02, session_03 (this file)
  notebooks/         6 exploration notebooks (added portfolio.ipynb)
  output/            empty (for future charts/tables)
  src/
    1_data_pull.py   ✅ implemented and tested
    2_signal.py      ✅ implemented and tested
    3_portfolio.py   ✅ implemented and tested
    4_backtest.py    stub (next)
    5_onchain.py     stub
    6_regime.py      stub
  ideas.md           running ideas doc
  project_brief.md   full project spec
  README.md          project overview
  .gitignore         excludes data/, .parquet, .csv, .env, __pycache__
```
