# Crypto Carry Backtest with On-Chain Timing Signal

This project builds and evaluates a systematic delta-neutral carry strategy on BTC and ETH perpetual futures (Binance, January 2020–March 2026), then tests whether on-chain exchange inflow data can improve entry timing. The strategy goes long spot and short the perpetual to collect funding rate payments, with inverse-volatility position sizing, explicit spread-based transaction costs, and regime-conditional performance measurement. The on-chain overlay — hourly exchange inflows of BTC, ETH, and USDT tested via OLS regression with Newey-West HAC errors — produces a null result: inflow Z-scores do not predict funding rate changes at any tested horizon (p > 0.20 across all specifications). The dominant performance driver is not the signal but the interaction of execution cost and macro regime: carry is profitable at institutional spreads during low-VIX environments and unprofitable otherwise.

## Key Findings

**VIX regime is the dominant performance variable.** Low-VIX periods (VIX ≤ 25, 78% of the sample) deliver a Sharpe of 1.017. High-VIX periods (VIX > 25) flip the strategy to a Sharpe of -2.174 with -253 bps/yr. The mechanism: macro stress compresses crypto funding rates while the strategy still incurs turnover costs, producing a negative net P&L. Win rate drops from 63% to 50% — indistinguishable from random.

**Execution cost is the binding constraint.** At 3 bps/side (institutional with smart order routing), Sharpe is 4.25. At 5 bps/side (default), Sharpe is 0.37. At 7 bps/side (retail taker), Sharpe is -2.19. The breakeven spread is approximately 5.2 bps/side. This is a spread capture trade — the edge is in execution, not the signal.

**On-chain inflows contain no exploitable information at 8-hour resolution.** BTC, ETH, and USDT hourly exchange inflows were tested as leading indicators of funding rate changes across pooled, per-asset, and pre/post-2021 scopes with lags from 8 to 192 hours. All p-values exceed 0.20. Overlay ΔSharpe = 0.000. This is consistent with Chi, Chu, and Hao (2024) and implies that on-chain flow information is incorporated into perpetual futures pricing faster than the 8-hour settlement cycle.

## Methodology

### Data Sources

| Source | Data | Resolution | Period |
|---|---|---|---|
| Binance bulk downloads (data.binance.vision) | Funding rates, spot klines, perp klines | 8h / 1h | 2020-01 – 2026-03 |
| FRED (VIXCLS) | VIX daily close | Daily | 1990-01 – 2026-04 |
| Dune Analytics | BTC, ETH, USDT exchange inflows | Hourly | 2020-01 – 2026-04 |

### Strategy Design

- **Universe:** BTCUSDT, ETHUSDT perpetual futures on Binance
- **Entry signal:** Funding rate > 0.01% per 8-hour settlement period
- **Position sizing:** Inverse of 30-day realized volatility, normalized so active weights sum to 1. Scales down in high-vol (when carry is less attractive) and up in low-vol (when margin is cheaper)
- **Rebalance frequency:** Every 8 hours at funding settlement
- **Cost model:** Fixed half-spread applied to both legs (spot + perp) per unit of turnover. Default: 5 bps/side. Cost = turnover × 2 × spread / 10,000

### P&L Decomposition

Each period's P&L decomposes into three components:

1. **Funding income:** weight × funding_rate (collected at settlement)
2. **Cost drag:** -turnover × 2 × spread_bps / 10,000 (paid on entry/exit)
3. **Basis mark-to-market:** prior weight × (spot return - perp return)

Full-sample attribution: +6,112 bps funding, -5,955 bps cost, +129 bps basis = +286 bps net. Costs consume 97% of gross funding income.

### Regime Framework

Two regime dimensions, producing a 2×2 grid:

- **Structural break:** Pre-2021 vs post-2021 (January 1, 2021). Based on Kroner, Mohammed, and Vega's identification of a structural shift in crypto-macro sensitivity coinciding with institutional entry.
- **Macro uncertainty:** VIX ≤ 25 (low) vs VIX > 25 (high). VIX is forward-filled from daily closes onto 8-hour backtest timestamps.

## Results

### Baseline Performance

| Metric | Full Sample | Pre-2021 | Post-2021 |
|---|---|---|---|
| Sharpe (ann.) | 0.370 | 0.611 | 0.309 |
| Total return (bps) | 285.6 | 104.0 | 181.6 |
| Annual return (bps/yr) | 46.0 | 108.2 | 34.6 |
| Max drawdown (bps) | -1,448.6 | -343.7 | -1,448.6 |
| Win rate (active periods) | 61.2% | 61.1% | 61.2% |

### Regime Performance — 2×2 Sharpe Grid

| | VIX ≤ 25 | VIX > 25 |
|---|---|---|
| **Pre-2021** | 4.687 | -4.140 |
| **Post-2021** | 0.429 | -0.427 |

Every high-VIX cell is negative regardless of era. Pre-2021 low-VIX was the golden regime (Sharpe 4.69, 1,105 bps/yr). Post-2021 low-VIX remains marginally positive (Sharpe 0.43, 48 bps/yr).

### Spread Sensitivity (at 0.01% threshold)

| Spread (bps/side) | 1 | 2 | 3 | 5 | 7 | 10 |
|---|---|---|---|---|---|---|
| **Sharpe** | 9.03 | 6.64 | 4.25 | 0.37 | -2.19 | -4.44 |

Viable at ≤ 3 bps (institutional). Unprofitable at ≥ 7 bps (retail). Breakeven: ~5.2 bps/side.

### Threshold Sensitivity (at 5 bps/side spread)

| Threshold | 0.00% | 0.01% | 0.03% | 0.05% |
|---|---|---|---|---|
| **Sharpe** | -5.68 | 0.370 | 0.481 | 0.983 |

Higher thresholds improve Sharpe by restricting entry to periods with strongly positive funding, reducing churn and cost drag. Full sweep with 7 threshold levels in `output/threshold_sweep.csv`.

### On-Chain Overlay

| Signal | Scope | Best p-value | ΔSharpe |
|---|---|---|---|
| BTC inflow Z-score | Pooled, per-asset, per-regime, lags 1–24 | 0.264 | 0.000 |
| ETH inflow Z-score | Pooled, per-asset, per-regime, lags 1–24 | > 0.20 | 0.000 |
| USDT inflow Z-score | Pooled, per-asset, per-regime, lags 1–24 | 0.085 (lag 24) | 0.000 |

USDT marginal signal at lag 24 (p = 0.085) is at an implausible 8-day horizon across 75+ specifications — not acted upon.

## Repository Structure

```
carry_project/
├── src/
│   ├── 1_data_pull.py      Data ingestion (Binance bulk downloads, FRED VIX)
│   ├── 2_signal.py          Funding rate signal + realized vol computation
│   ├── 3_portfolio.py       Inverse-vol position sizing + cost model
│   ├── 4_backtest.py        P&L engine, performance metrics, sensitivity sweeps
│   ├── 5_onchain.py         Dune API inflow ingestion, predictive regression
│   ├── 6_regime.py          Regime splitting (era × VIX) and conditional metrics
│   ├── dune_btc_inflows.sql Dune query: hourly BTC exchange inflows
│   ├── dune_eth_inflows.sql Dune query: hourly ETH exchange inflows
│   └── dune_usdt_inflows.sql Dune query: hourly USDT exchange inflows
├── notebooks/               Exploration notebooks (8 total)
├── data/                    Parquet files (not committed)
├── output/
│   ├── threshold_sweep.csv  7 thresholds × full metrics
│   ├── spread_sweep.csv     6 spread levels × full metrics
│   ├── regime_analysis.csv  9 regime slices × full metrics
│   ├── onchain_regression.csv       BTC/ETH inflow regression results
│   └── onchain_usdt_regression.csv  USDT inflow regression results
├── logs/                    Session logs (sessions 1–6)
├── project_brief.md         Research design document
├── WRITEUP.md               Research write-up
└── ideas.md                 Future extensions
```

## Setup and Run

```bash
# Install dependencies
pip install pandas numpy scipy statsmodels requests pyarrow matplotlib

# For on-chain data (optional): set Dune API key
echo "DUNE_API_KEY=your_key_here" > .env

# Run pipeline sequentially
python3 src/1_data_pull.py      # ~20 min (downloads from Binance + FRED)
python3 src/2_signal.py          # Baseline carry signal
python3 src/3_portfolio.py       # Position sizing + costs
python3 src/4_backtest.py        # P&L engine + sweeps
python3 src/5_onchain.py         # On-chain signal test (requires DUNE_API_KEY)
python3 src/6_regime.py          # Regime analysis
```

Steps 1–4 require no API keys — all Binance data is from public bulk downloads. Step 5 requires a free Dune Analytics API key.

## Dependencies

```
pandas
numpy
scipy
statsmodels
requests
pyarrow
matplotlib
```
