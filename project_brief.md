# Project Brief: Crypto Carry Backtest with On-Chain Timing Signal

## Research Question
Does on-chain exchange inflow predict short-term funding rate direction, and does using it
to time carry entry/exit improve risk-adjusted P&L relative to a naive carry baseline?

## Background
Perpetual futures funding rates create a delta-neutral carry opportunity: go long spot,
short the perpetual, collect funding payments when rates are positive. This is a known
strategy. The novel contribution is testing whether on-chain exchange inflow data -- large
movements of crypto onto exchange addresses -- can predict upcoming funding rate compression
before it occurs, improving entry/exit timing.

This project extends published research (Kroner, Mohammed, Vega -- Federal Reserve working
paper on crypto price discovery) by asking a tradeable follow-on question using a fully
independent dataset and methodology with a split on the post-2021 break identified in the paper. 

## Structure: Two Layers

### Layer 1: Baseline Carry Strategy (benchmark)
- Universe: BTCUSDT, ETHUSDT (Binance perpetuals)
- Signal: enter carry when funding_rate > threshold; exit when below threshold or negative
- Position sizing: volatility-scaled (inverse of 30-day realized vol), normalized to 1 total
- Hold: rebalance at each 8-hour funding settlement
- Transaction costs: bid-ask spread on entry and exit legs (modeled from OHLCV or fixed bps)
- Output: cumulative P&L curve, Sharpe, max drawdown, turnover, funding income vs. cost drag

### Layer 2: On-Chain Timing Overlay
- Signal: rolling Z-score of exchange inflow. Suppress carry entry when Z > threshold.
- Hypothesis: inflow spike at T predicts funding rate compression at T+1 or T+2
- Required first step: run predictive regression (OLS, HAC errors) to confirm lead-lag exists
- If no significant lead-lag: document as null result and report why
- Output: Sharpe(Layer 2) vs. Sharpe(Layer 1), P&L attribution of timing overlay contribution

## Regime Analysis
- Primary split: pre-2021 vs. post-2021 (structural break from published paper)
- Secondary split: high vs. low macro uncertainty (VIX > 25 vs. <= 25, from FRED)
- Report all metrics separately per regime

## Data Sources (all free, no API key required unless noted)

### Binance (primary, no key required)
- Funding rates:    GET https://fapi.binance.com/fapi/v1/fundingRate
                   params: symbol, startTime, endTime, limit=1000
                   history: back to 2019 for BTC/ETH
- Spot klines:     GET https://api.binance.com/api/v3/klines
                   params: symbol, interval, startTime, endTime, limit=1000
- Perp klines:     GET https://fapi.binance.com/fapi/v1/klines
- Open interest:   GET https://fapi.binance.com/futures/data/openInterestHist
                   note: API only returns 30 days; cache as you go for longer history
- Bulk data dump:  https://data.binance.vision (pre-packaged CSVs, faster for multi-year pulls)

### VIX (regime labels, no key required)
- FRED API:        https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS

### On-Chain Inflows (Layer 2 -- confirm access before building)
- Glassnode (paid, preferred): 
    GET https://api.glassnode.com/v1/metrics/transactions/transfers_volume_to_exchanges_sum
    requires Advanced subscription (~$39/month) for hourly resolution
- CryptoQuant (free tier available):
    https://cryptoquant.com/docs
    free tier: daily resolution only

## File Structure
```
carry_project/
  data/           raw parquet files, not committed to git
  src/
    data_pull.py  API ingestion (build this first)
    signal.py     funding rate signal + on-chain signal construction
    portfolio.py  position sizing, rebalancing, cost model
    backtest.py   P&L engine, performance metrics
    onchain.py    on-chain data ingestion and predictive regression
    regime.py     regime splitting and conditional reporting
  notebooks/      exploratory analysis
  output/         charts, performance tables, results
  README.md
  project_brief.md (this file)
```

## Build Order
1. data_pull.py -- get funding rates and klines working, verify data quality
2. signal.py -- baseline funding rate signal only
3. portfolio.py -- position sizing and cost model
4. backtest.py -- P&L engine, confirm baseline carry results look reasonable
5. onchain.py -- only after baseline is confirmed and data access is confirmed
6. regime.py -- split all results once both layers are working
7. README.md -- write up as mini working paper once results are in

## Key Design Decisions
- Null result framing: if on-chain signal does not predict funding direction, that is the
  finding. Document it clearly. Do not search for a positive result by overfitting.
- No fabrication: every claim in the README must be supported by code output.
- Reproducibility: baseline carry results must be fully reproducible with Binance public data.
  On-chain layer should document data source and access requirements clearly.
- Robustness: sweep entry threshold and inflow spike threshold. Report sensitivity tables.
- Simplicitly: Code should be as simple, concise, and readable as possible

## Resume Framing (do not include in README, for reference only)
"Built a cross-asset crypto carry backtest using perpetual futures funding rates with
volatility-scaled position sizing and spread-based transaction cost modeling; tested
on-chain exchange inflow as a leading indicator of funding regime changes and attributed
P&L to carry baseline versus timing overlay across pre/post-2021 regimes."
