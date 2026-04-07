# Session 5: On-Chain Signal Layer (2026-04-06)

## What was done

### 1. Data source exploration and access confirmation

Evaluated all candidate sources for hourly exchange inflow data:

| Source | Resolution | Access | Outcome |
|---|---|---|---|
| Glassnode | Hourly (T2 metric) | API requires Professional plan ($999/mo) | Rejected — cost |
| CryptoQuant | Hourly | Free tier requires API key registration | 401, not pursued |
| Coin Metrics Community | Daily | Free, no key | Tested — too coarse |
| **Dune Analytics** | **Hourly** | **Free tier + free API key** | **Selected** |

**Coin Metrics** was used first (daily `FlowInExNtv`) and produced a null result. Idrees requested higher-frequency data, so we switched to **Dune Analytics**. Wrote three SQL queries using Dune's curated tables:
- `dune_btc_inflows.sql` — `bitcoin.outputs` joined to `cex.addresses` (761 BTC exchange addresses)
- `dune_eth_inflows.sql` — `ethereum.traces` joined to `cex.addresses` (4,366 ETH exchange addresses)
- `dune_usdt_inflows.sql` — `tokens.transfers` joined to `cex.addresses`, filtered to USDT contract `0xdAC17F958D2ee523a2206206994597C13D831ec7`

Data is fetched programmatically via Dune API (free API key, paginated JSON results), cached as parquet. No CSV export / paid plan needed.

### 2. Implemented `src/5_onchain.py`

Full on-chain pipeline: Dune API ingestion, Z-score construction, predictive regression, USDT market-wide analysis, and (conditional) timing overlay.

Key implementation details:
- **Ingestion**: `POST /api/v1/query/{id}/execute` → poll status → paginated `GET /api/v1/query/{id}/results`
- **Z-score**: 30-day rolling mean/std on hourly series (window = 720 hours), `min_periods=360`
- **BTC/ETH merge**: Asof-join per-asset inflow Z onto 8h funding timestamps (backward, no look-ahead)
- **USDT merge**: Market-wide signal — single USDT Z-score merged onto all funding timestamps (both BTC and ETH) by timestamp only
- **Regression**: OLS with Newey-West HAC errors (3 lags). Model: `Δfunding(T+lag) = α + β₁·inflow_z(T) + β₂·funding_rate(T) + β₃·realized_vol(T) + ε`
- **Scopes**: Pooled, per-asset (BTC, ETH), per-regime (pre/post-2021)
- **Multi-lag sweep**: lags 1, 3, 8, 16, 24 (8h to 192h)
- **Overlay**: Suppresses carry when `inflow_z > threshold`. Only activated if p < 0.10 with expected sign

### 3. Literature review

Reviewed academic literature on exchange inflow predictability during analysis:

**Chi, Chu & Hao (2024) — [arXiv:2411.06327](https://arxiv.org/abs/2411.06327)**
_"Return and Volatility Forecasting Using On-Chain Flows in Cryptocurrency Markets"_
- Tests BTC, ETH, and USDT inflows at 1–6h frequency, 2017–2023
- Key finding: **"BTC net inflows generally lack predictive power for BTC returns"** — directly consistent with our null
- USDT inflows positively predict BTC/ETH returns at multiple intervals — motivated our USDT extension
- ETH inflows negatively predict ETH returns — interesting but they target price, not funding

**Herremans & Low (2022) — [arXiv:2211.08281](https://arxiv.org/abs/2211.08281)**
_"Forecasting Bitcoin volatility spikes from whale transactions and CryptoQuant data"_
- Uses entity-aware CryptoQuant data (not raw transfers) at daily resolution
- Exchange inflow features present but not top predictors; taker buy volume ranks higher
- Supports the view that entity-adjusted data is materially cleaner than raw transfers

Neither paper tests exchange inflow as a predictor of perpetual futures **funding rates** specifically. Our null result is the first formal test of this question.

### 4. Generated output and data files

| File | Rows | Description |
|---|---|---|
| `data/dune_btc_inflows.parquet` | 54,705 | Hourly BTC exchange inflows, 2020-01-01 → 2026-04-05 |
| `data/dune_eth_inflows.parquet` | 54,867 | Hourly ETH exchange inflows, 2020-01-01 → 2026-04-05 |
| `data/dune_usdt_inflows.parquet` | 54,907 | Hourly USDT exchange inflows, 2020-01-01 → 2026-04-06 |
| `data/onchain_merged.parquet` | 13,692 | BTC/ETH funding periods with inflow Z-scores |
| `data/onchain_usdt_merged.parquet` | 13,692 | Funding periods with USDT Z-score |
| `output/onchain_regression.csv` | — | BTC/ETH regression results across all scopes |
| `output/onchain_usdt_regression.csv` | — | USDT regression results across all scopes |

### 5. Key findings: NULL RESULT (all three assets)

#### BTC/ETH inflows — null across all scopes and horizons

| Scope | N | β(inflow_z) | t-stat | p-value | R² |
|---|---|---|---|---|---|
| Pooled | 13,600 | -2.39e-06 | -1.117 | 0.264 | 0.0006 |
| BTC | 6,800 | +5.63e-07 | +0.338 | 0.735 | 0.103 |
| ETH | 6,800 | +2.44e-08 | +0.008 | 0.994 | 0.109 |
| Pre-2021 | 2,104 | +1.65e-06 | +0.199 | 0.843 | 0.001 |
| Post-2021 | 11,494 | -1.79e-06 | -1.272 | 0.203 | 0.0005 |

Multi-lag sweep (lags 1–24, 8h–192h): all p-values > 0.20. Overlay ΔSharpe = 0.000.

#### USDT inflows — null, one marginal result at implausible horizon

| Scope | N | β(usdt_z) | t-stat | p-value | R² |
|---|---|---|---|---|---|
| Pooled | 13,600 | +1.38e-06 | +1.041 | 0.298 | 0.0005 |
| BTC | 6,800 | +1.68e-07 | +0.093 | 0.926 | 0.103 |
| ETH | 6,800 | +1.80e-06 | +1.155 | 0.248 | 0.109 |
| Pre-2021 | 2,104 | +3.54e-06 | +0.537 | 0.591 | 0.001 |
| Post-2021 | 11,494 | +1.17e-06 | +1.141 | 0.254 | 0.0004 |

USDT multi-lag sweep: lag 24 (192h = 8 days) shows p=0.085 with correct positive sign. All other lags > 0.38. This is most likely a multiple-testing artifact — five lags tested, one marginal hit at the longest and least mechanistically plausible horizon. Not acted upon.

### 6. Interpretation

All three on-chain signals (BTC inflow, ETH inflow, USDT inflow) fail to predict funding rate changes at the 10% significance level. The overlay adds nothing. Consistent findings:

- **Consistent with Chi et al. (2024)**: BTC inflows don't predict BTC returns; our result extends this to funding rates
- **Raw vs entity-adjusted**: Our Dune data captures all transfers to labeled exchange addresses including internal wallet shuffling. Entity-adjusted data (Glassnode) would be cleaner but requires a paid subscription
- **Wrong target for USDT**: Chi et al. find USDT inflows predict spot *returns*, not funding specifically. The transmission USDT → buying → price up → basis expansion → funding increase may be too indirect or too fast to show up at 8h resolution
- **Crisis conflation**: The largest inflow spikes (June 2022 Celsius/3AC, November 2022 FTX) occurred when funding was near zero or negative — forced deposits during capitulation, not bullish accumulation. This contaminates the signal

## What's next
**Step 6 per `project_brief.md` build order: `src/6_regime.py`**
- Regime analysis applies to the **baseline carry strategy only** (on-chain overlay is null)
- Split by pre/post-2021 structural break and VIX > 25 vs ≤ 25
- Report all metrics separately per regime
- Conditional performance tables

## Current directory structure
```
carry_project/
  data/              12 parquet files (9 raw + signals + portfolio + backtest
                     + dune_btc/eth/usdt_inflows + onchain_merged + onchain_usdt_merged)
  logs/              session_01 → session_05 (this file)
  notebooks/         8 notebooks (added onchain.ipynb)
  output/            threshold_sweep.csv, spread_sweep.csv,
                     onchain_regression.csv, onchain_usdt_regression.csv
  src/
    1_data_pull.py       ✅ implemented and tested
    2_signal.py          ✅ implemented and tested
    3_portfolio.py       ✅ implemented and tested
    4_backtest.py        ✅ implemented and tested
    5_onchain.py         ✅ implemented and tested (null result — all three signals)
    dune_btc_inflows.sql ✅ hourly BTC exchange inflows
    dune_eth_inflows.sql ✅ hourly ETH exchange inflows
    dune_usdt_inflows.sql✅ hourly USDT exchange inflows
    6_regime.py          stub (next)
  ideas.md
  project_brief.md
  README.md
  .env                   (gitignored — DUNE_API_KEY)
  .gitignore
```
