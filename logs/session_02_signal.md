# Session 2: Baseline Carry Signal (2026-04-03)

## What was done

### 1. Implemented `src/2_signal.py`
Builds the baseline carry signal (Layer 1) from funding rates and computes realized vol for downstream position sizing.

Key implementation details:
- Loads funding rates (8h frequency) and spot klines (1h) per asset
- Computes 30-day annualized realized vol from hourly spot log returns: `rolling(720h).std() * sqrt(8760)`
- Uses `min_periods=360` (15 days) — produces 45 null vol values per asset at the start of the series (Jan 1–15, 2020)
- Asof-joins vol onto funding timestamps (backward direction: uses most recent hourly vol at or before each settlement)
- Signal: `1 if funding_rate > 0.0001 (0.01% per 8h) else 0`
- 0.01% is Binance's default funding rate — threshold means "only enter when funding is above baseline"
- Concurrent funding rate is used (not lagged) — Binance publishes indicative rate before settlement, so this is observable pre-trade
- Prints threshold sensitivity table and per-asset stats on run
- Bug fixed during implementation: timezone mismatch on `merge_asof` — funding timestamps are UTC-aware, vol DataFrame lost tz info via `.values`. Fixed by passing the Series directly.

### 2. Generated `data/signals.parquet`

| Column | Type | Description |
|---|---|---|
| `timestamp` | datetime64[ns, UTC] | 8h funding settlement time |
| `symbol` | str | `BTC` or `ETH` |
| `funding_rate` | float64 | Raw funding rate at this settlement |
| `realized_vol_30d` | float64 | Annualized 30d vol from hourly spot returns |
| `signal` | int64 | 1 = in carry, 0 = out (at 0.01% threshold) |

- 13,692 total rows (6,846 per asset)
- 90 null vol values total (45 per asset, first 15 days of warm-up)
- Date range: 2020-01-01 → 2026-03-31
- Downstream steps can re-threshold `funding_rate` directly without re-running this script

### 3. Created `notebooks/signals.ipynb`
Exploration notebook covering:
- Schema, head/tail, coverage, null check
- Funding rate distribution histograms with threshold line
- Signal summary (% time in carry, mean funding when on)
- Threshold sensitivity curve (0% to 0.05%)
- Realized vol distribution (BTC vs ETH overlay)
- Rolling 30d signal activity over time with 2021 regime split line
- Pre-2021 vs post-2021 regime comparison table
- BTC vs ETH signal agreement/disagreement
- Funding rate autocorrelation (ACF bar charts, up to 30 lags)
- Yearly signal summary table

### 4. Key findings

**Signal activity by year:**
| Year | BTC pct_on | ETH pct_on | Mean funding (%) |
|------|-----------|-----------|-----------------|
| 2020 | 26.8% | 37.4% | 0.02–0.03 |
| 2021 | 42.9% | 45.4% | 0.03 |
| 2022 | 0.0% | 0.0% | 0.00 |
| 2023 | 6.3% | 6.9% | 0.01 |
| 2024 | 19.4% | 22.0% | 0.01 |
| 2025 | 0.0% | 0.0% | 0.00 |
| 2026 | 0.0% | 0.0% | 0.00 |

- **Carry opportunity has largely disappeared post-2021.** 2022, 2025, 2026 have 0% signal activity. Funding compressed to or below the 0.01% default rate.
- **2021 bull run was the sweet spot** — sustained speculative long positioning kept funding elevated.
- **ETH consistently has higher signal activity than BTC** — more retail speculation drives more persistent premiums.
- **Threshold sensitivity cliff at 0.01%**: dropping to 0.005% jumps from ~16% to ~67% time-in-carry. The backtest (step 4) will determine if the lower threshold is profitable after costs or just adds churn.
- **Funding is autocorrelated** — high funding persists across multiple 8h periods, validating the threshold-based signal approach. If funding were random, the signal would be useless.
- **This is exactly the regime split the project brief anticipated.** The pre/post-2021 structural break is the central finding. The on-chain overlay (step 5) becomes more interesting as a way to identify rare post-2021 windows where carry is still viable.

## What's next
**Step 3 per `project_brief.md` build order: `src/3_portfolio.py`**
- Position sizing: inverse of 30-day realized vol, normalized to 1 total across assets
- Rebalancing at each 8h funding settlement
- Transaction cost model: spread-based (fixed bps per side or derived from kline data)
- Output: position sizes per asset per period, cost estimates

## Current directory structure
```
carry_project/
  data/              9 raw parquet files + signals.parquet (10 total)
  logs/              session_01_data_pull.md, session_02_signal.md (this file)
  notebooks/         5 exploration notebooks (added signals.ipynb)
  output/            empty (for future charts/tables)
  src/
    1_data_pull.py   ✅ implemented and tested
    2_signal.py      ✅ implemented and tested
    3_portfolio.py   stub (next)
    4_backtest.py    stub
    5_onchain.py     stub
    6_regime.py      stub
  ideas.md           running ideas doc
  project_brief.md   full project spec
  README.md          project overview
  .gitignore         excludes data/, .parquet, .csv, .env, __pycache__
```
