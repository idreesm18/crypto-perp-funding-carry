# Delta-Neutral Crypto Carry: Regime Dependence, Cost Sensitivity, and the Absence of On-Chain Predictive Power

## Motivation and Research Question

Perpetual futures on crypto exchanges settle funding payments every eight hours. When rates are positive, longs pay shorts, and a delta-neutral carry trade exists: long spot, short the perpetual, collect the differential. The structural argument for rate persistence is that leveraged speculative demand systematically exceeds hedging supply, producing a positive funding premium. The question to answer is how stable that premium is across macro regimes, how sensitive it is to execution costs, and whether on-chain exchange inflow data can improve entry timing.

The on-chain hypothesis: large inflows onto exchange addresses signal impending sell pressure, which compresses funding rates, and a timing overlay suppressing carry entry during inflow spikes would improve risk-adjusted returns. That turned out to be wrong, but there were substantive regime and cost findings anyway.

## Data and Methodology

BTCUSDT and ETHUSDT perpetuals on Binance, January 2020 through March 2026, 6,846 eight-hour funding periods per asset. Funding rates, spot klines, and perp klines from Binance public bulk downloads (data.binance.vision). VIX daily closes from FRED. On-chain exchange inflows at hourly resolution from Dune Analytics curated tables.

The carry signal enters when the 8-hour funding rate exceeds 0.01%. The position is designed to be delta-neutral (long spot and short equal notional of the perpetual) so price exposure is intended to net to zero and funding income is the sole intended P&L source. The backtest models this via funding income and basis mark-to-market components rather than explicitly simulating two-leg margin accounts. Position sizing is inverse 30-day realized volatility, normalized across assets. The cost model applies a fixed half-spread to both legs per unit of turnover, defaulting to 5 bps per side. P&L decomposes into funding income, cost drag, and basis mark-to-market each period.

Regime analysis is done along two lines: a structural break at January 1, 2021, following Kroner, Mohammed, and Vega's identification of a shift in crypto-macro sensitivity coinciding with institutional entry, and a VIX threshold at 25.

## Results

Full-sample Sharpe is 0.370, 286 cumulative bps over 6.2 years. The attribution: +6,112 bps gross funding income, -5,955 bps cost drag, +129 bps basis mark-to-market. Costs absorb 97% of gross income.

VIX cuts the sample pretty cleanly. Low-VIX periods (VIX ≤ 25, 78% of the sample): Sharpe 1.017, 128 bps/yr. High-VIX: Sharpe -2.174, -253 bps/yr. High-VIX periods coincide with lower funding rates and continued turnover costs near the entry threshold. Win rate drops from 63% to 50%.

|  | VIX ≤ 25 | VIX > 25 |
|---|---|---|
| Pre-2021 | 4.687 | -4.140 |
| Post-2021 | 0.429 | -0.427 |

Pre-2021 low-VIX is the standout regime: Sharpe 4.69, 1,105 bps/yr, coinciding with elevated funding rates and limited institutional competition. Pre-2021 is a small sample and strongly influenced by the 2021 bull market. Post-2021 low-VIX is still positive (Sharpe 0.43) but the premium is lower. Every high-VIX cell is negative, in both eras.

Spread sensitivity: breakeven is approximately 5.2 bps per side. At 3 bps, Sharpe is 4.25. At 7 bps, -2.19.

## On-Chain Signal Test

BTC, ETH, and USDT hourly exchange inflows as leading indicators of funding rate changes with the regression:

> Δfunding(T+lag) = α + β₁·inflow_z(T) + β₂·funding_rate(T) + β₃·realized_vol(T) + ε

Newey-West HAC errors, pooled and per-asset and pre/post-2021 scopes, lags 1 to 24 periods (8 to 192 hours), over 75 specifications total. Every inflow Z-score p-value is above 0.20. Overlay ΔSharpe = 0.000. USDT produces p = 0.085 at lag 24, an implausible 8-day horizon across 75+ tests.

Chi, Chu, and Hao (2024) find the same null for BTC and ETH inflows as predictors of spot returns. At 8-hour resolution, there is no detectable lead-lag relationship between inflows and funding rate changes. If a transmission mechanism exists, it operates at frequencies this sample cannot detect.

## Conclusion

In this sample, the carry trade was profitable when VIX was low and execution costs were institutional. Both conditions needed to hold simultaneously. Post-2021, even within low-VIX periods, the premium is lower, consistent with more capital competing for the same trade. On-chain inflows add nothing at 8-hour resolution.

Natural next steps: sub-hourly inflow data where the information transmission may still be observable; open interest as a crowding indicator (high OI plus positive funding is a fragile position); replacing realized vol with a directional persistence measure; extending to additional perpetual markets where the premium may be less competed away.
