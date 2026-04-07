# Crypto Carry Backtest with On-Chain Timing Signal

A systematic delta-neutral carry strategy on BTC and ETH perpetual futures (Binance, January 2020 through March 2026), with a test of on-chain exchange inflows as a timing signal. The strategy goes long spot, short the perpetual, and collects funding at each 8-hour settlement, with inverse-volatility position sizing and spread-based transaction costs modeled explicitly. On-chain overlay: hourly BTC, ETH, and USDT inflows tested via OLS with Newey-West HAC errors across 75+ specifications. All p-values exceed 0.20. In this sample, the strategy was profitable at institutional execution costs during low-VIX environments. Outside those conditions, it was not.

## Key Findings

**VIX regime is the dominant performance variable.** Low-VIX periods (VIX ≤ 25, 78% of the sample) produce a Sharpe of 1.017 and 128 bps/yr. High-VIX periods flip to Sharpe -2.174 and -253 bps/yr. High-VIX periods in this sample coincide with lower funding rates and continued turnover costs near the entry threshold. Win rate drops from 63% to 50%.

**Gross funding income is real; friction is what kills it.** Full-sample P&L attribution: +6,112 bps funding income, -5,955 bps cost drag, +129 bps basis mark-to-market, 286 bps net. Costs absorb 97% of gross income. At 3 bps/side, Sharpe is 4.25. At 5 bps (default), 0.37. At 7 bps (retail taker), -2.19. Breakeven is approximately 5.2 bps/side. Premium is persistent, but execution quality determines whether it's capturable.

**On-chain inflows at 8-hour resolution did not improve results.** BTC, ETH, and USDT hourly exchange inflows tested across pooled, per-asset, and pre/post-2021 scopes with lags from 8 to 192 hours. All p-values exceed 0.20. Overlay ΔSharpe = 0.000. No detectable lead-lag relationship was found at 8-hour resolution. See Chi, Chu, and Hao (2024) for consistent findings on spot returns.

## Methodology

### Data Sources

| Source | Data | Resolution | Period |
|---|---|---|---|
| Binance bulk downloads (data.binance.vision) | Funding rates, spot klines, perp klines | 8h / 1h | 2020-01 to 2026-03 |
| FRED (VIXCLS) | VIX daily close | Daily | 1990-01 to 2026-04 |
| Dune Analytics | BTC, ETH, USDT exchange inflows | Hourly | 2020-01 to 2026-04 |

### Strategy Design

- **Universe:** BTCUSDT, ETHUSDT perpetual futures on Binance
- **Entry signal:** Funding rate > 0.01% per 8-hour settlement period
- **Position sizing:** Inverse 30-day realized volatility, normalized so active weights sum to 1. Scales down in high-vol, up in low-vol
- **Delta-neutrality:** The strategy holds equal notional in spot (long) and the perpetual (short), so spot price moves cancel across legs. The backtest models this by computing funding income and basis mark-to-market rather than tracking two separate accounts. Margin requirements and liquidation risk on the short perp leg are not modeled -- a known simplification standard in strategy research.
- **Rebalance frequency:** Every 8 hours at funding settlement
- **Cost model:** Fixed half-spread on both legs per unit of turnover. Cost = turnover x 2 x spread / 10,000. Default: 5 bps/side

### P&L Decomposition

Each period decomposes into three components:

1. **Funding income:** weight x funding_rate (collected at settlement)
2. **Cost drag:** -turnover x 2 x spread_bps / 10,000 (paid on entry/exit)
3. **Basis mark-to-market:** prior weight x (spot return - perp return)

Full-sample attribution: +6,112 bps funding, -5,955 bps cost, +129 bps basis = +286 bps net.

### Regime Framework

Two dimensions:

- **Structural break:** Pre-2021 vs post-2021 (January 1, 2021). Based on Kroner, Mohammed, and Vega's identification of a shift in crypto-macro sensitivity coinciding with institutional entry.
- **Macro uncertainty:** VIX ≤ 25 (low) vs VIX > 25 (high). VIX forward-filled from daily closes onto 8-hour timestamps.

## Results

### Baseline Performance

| Metric | Full Sample | Pre-2021 | Post-2021 |
|---|---|---|---|
| Sharpe (ann.) | 0.370 | 0.611 | 0.309 |
| Total return (bps) | 285.6 | 104.0 | 181.6 |
| Annual return (bps/yr) | 46.0 | 108.2 | 34.6 |
| Max drawdown (bps) | -1,448.6 | -343.7 | -1,448.6 |
| Win rate (active periods) | 61.2% | 61.1% | 61.2% |

### Regime Performance -- 2x2 Sharpe Grid

| | VIX ≤ 25 | VIX > 25 |
|---|---|---|
| **Pre-2021** | 4.687 | -4.140 |
| **Post-2021** | 0.429 | -0.427 |

Every high-VIX cell is negative. Pre-2021 low-VIX was the standout regime (Sharpe 4.69, 1,105 bps/yr). Post-2021 low-VIX remains positive (Sharpe 0.43, 48 bps/yr) but the premium is lower.

### Spread Sensitivity (at 0.01% threshold)

| Spread (bps/side) | 1 | 2 | 3 | 5 | 7 | 10 |
|---|---|---|---|---|---|---|
| **Sharpe** | 9.03 | 6.64 | 4.25 | 0.37 | -2.19 | -4.44 |

Viable at ≤ 3 bps (institutional). Unprofitable at ≥ 7 bps (retail). Breakeven: ~5.2 bps/side.

### Threshold Sensitivity (at 5 bps/side spread)

| Threshold | 0.00% | 0.01% | 0.03% | 0.05% |
|---|---|---|---|---|
| **Sharpe** | -5.68 | 0.370 | 0.481 | 0.983 |

Sharpe improves monotonically with threshold: tighter entry criteria cut turnover costs but reduce time invested. At 0.05%, the strategy is in carry roughly 5% of periods. Full sweep across 7 levels in `output/threshold_sweep.csv`.

### On-Chain Overlay

| Signal | Scope | Best p-value | ΔSharpe |
|---|---|---|---|
| BTC inflow Z-score | Pooled, per-asset, per-regime, lags 1-24 | 0.264 | 0.000 |
| ETH inflow Z-score | Pooled, per-asset, per-regime, lags 1-24 | > 0.20 | 0.000 |
| USDT inflow Z-score | Pooled, per-asset, per-regime, lags 1-24 | 0.085 (lag 24) | 0.000 |

USDT marginal signal at lag 24 (p = 0.085) is at an implausible 8-day horizon across 75+ specifications and is not acted upon.

## Repository Structure

```
carry_project/
├── src/
│   ├── 1_data_pull.py        Data ingestion (Binance bulk downloads, FRED VIX)
│   ├── 2_signal.py           Funding rate signal + realized vol computation
│   ├── 3_portfolio.py        Inverse-vol position sizing + cost model
│   ├── 4_backtest.py         P&L engine, performance metrics, sensitivity sweeps
│   ├── 5_onchain.py          Dune API inflow ingestion, predictive regression
│   ├── 6_regime.py           Regime splitting (era x VIX) and conditional metrics
│   ├── dune_btc_inflows.sql  Dune query: hourly BTC exchange inflows
│   ├── dune_eth_inflows.sql  Dune query: hourly ETH exchange inflows
│   └── dune_usdt_inflows.sql Dune query: hourly USDT exchange inflows
├── notebooks/                Exploration notebooks (8 total)
├── data/                     Parquet files (not committed)
├── output/
│   ├── threshold_sweep.csv   7 thresholds x full metrics
│   ├── spread_sweep.csv      6 spread levels x full metrics
│   ├── regime_analysis.csv   9 regime slices x full metrics
│   ├── onchain_regression.csv        BTC/ETH inflow regression results
│   └── onchain_usdt_regression.csv   USDT inflow regression results
├── logs/                     Session logs (sessions 1-6)
├── project_brief.md          Research design document
├── WRITEUP.md                Research write-up
└── ideas.md                  Future extensions
```

## Setup and Run

```bash
# Install dependencies
pip install -r requirements.txt

# For on-chain data (optional): set Dune API key
echo "DUNE_API_KEY=your_key_here" > .env

# Run pipeline sequentially
python3 src/1_data_pull.py      # ~20 min (downloads from Binance + FRED)
python3 src/2_signal.py
python3 src/3_portfolio.py
python3 src/4_backtest.py       # P&L engine + sweeps
python3 src/5_onchain.py        # Requires DUNE_API_KEY
python3 src/6_regime.py
```

Steps 1-4 require no API keys. Step 5 requires a free Dune Analytics API key.

## Dependencies

```
pandas>=2.0
numpy>=2.0
scipy>=1.13
statsmodels>=0.14
requests>=2.32
pyarrow>=21.0
matplotlib>=3.9
```
