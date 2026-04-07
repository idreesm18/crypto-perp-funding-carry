# Delta-Neutral Crypto Carry: Regime Dependence, Cost Sensitivity, and the Absence of On-Chain Predictive Power

## Motivation and Research Question

Perpetual futures on crypto exchanges settle funding payments every eight hours. When funding rates are positive — when leveraged longs pay shorts — a delta-neutral carry trade exists: go long spot, short the perpetual, collect the funding differential. The structural argument for funding rate persistence is that leveraged speculative demand in crypto markets systematically exceeds hedging supply, producing a positive funding premium analogous to the equity variance risk premium. The open question is how this premium varies across macro regimes, how sensitive it is to execution costs, and whether publicly observable on-chain data can improve entry timing.

This project builds a complete systematic backtest of this carry strategy across BTC and ETH perpetuals on Binance (January 2020 through March 2026), with volatility-scaled position sizing, explicit transaction cost modeling, and regime-conditional performance measurement. It then tests whether hourly exchange inflow data — the movement of BTC, ETH, and USDT onto exchange deposit addresses — contains exploitable information for predicting funding rate changes. The hypothesis is that large inflows represent impending sell pressure that compresses funding rates, and that a timing overlay suppressing carry entry during inflow spikes would improve risk-adjusted returns.

## Data and Methodology

The data pipeline pulls from Binance public bulk downloads for funding rates, spot klines, and perpetual klines at hourly resolution, covering BTCUSDT and ETHUSDT from January 2020 through March 2026 (6,846 eight-hour funding periods per asset). VIX daily closes come from FRED. On-chain exchange inflows at hourly resolution are sourced from Dune Analytics curated tables.

The baseline signal enters carry when the 8-hour funding rate exceeds 0.01%. Position sizing uses inverse 30-day realized volatility normalized across assets, scaling down during high-volatility periods. The cost model applies a configurable half-spread to both legs for each unit of turnover, defaulting to 5 bps per side. P&L decomposes into funding income, cost drag, and basis mark-to-market per period per asset.

Regime analysis splits the sample along two dimensions: a structural break at January 1, 2021, following Kroner, Mohammed, and Vega's identification of a shift in crypto-macro sensitivity coinciding with institutional entry, and a VIX threshold at 25 separating low and high macro uncertainty.

## Results

At default parameters, the full-sample strategy produces an annualized Sharpe of 0.370 with 286 cumulative basis points over 6.2 years. P&L attribution exposes the cost structure: gross funding income totals +6,112 bps, of which -5,955 bps is consumed by cost drag. The net 286 bps includes +129 bps of basis mark-to-market, confirming approximate delta neutrality.

VIX regime is the dominant performance variable. During low-VIX environments (VIX ≤ 25, 78% of the sample), carry delivers a Sharpe of 1.017 and 128 bps per year. During high-VIX environments, Sharpe is -2.174 with losses of 253 bps per year. The mechanism is straightforward: macro stress compresses crypto funding rates as leveraged longs unwind, but the strategy still incurs turnover costs cycling around the entry threshold. Win rate drops from 63% to 50%.

The 2×2 grid crossing the structural break with VIX level sharpens this:

|  | VIX ≤ 25 | VIX > 25 |
|---|---|---|
| Pre-2021 | 4.687 | -4.140 |
| Post-2021 | 0.429 | -0.427 |

Pre-2021 low-VIX was the golden regime — Sharpe 4.69, 1,105 bps/yr — driven by elevated funding rates and minimal institutional competition. Post-2021 low-VIX remains positive but marginal (Sharpe 0.43). Every high-VIX cell is negative.

Spread sensitivity reveals the binding constraint. At 1 bps per side, Sharpe is 9.03. At 3 bps (institutional execution), 4.25. At 5 bps (default), 0.37. At 7 bps (retail), -2.19. The breakeven spread is approximately 5.2 bps per side. This is a spread capture trade: the edge is in execution quality, not signal construction.

## On-Chain Signal Test

The test estimates whether hourly exchange inflows predict subsequent funding rate changes using the regression:

> Δfunding(T+lag) = α + β₁·inflow_z(T) + β₂·funding_rate(T) + β₃·realized_vol(T) + ε

estimated with Newey-West HAC standard errors, across BTC, ETH, and USDT inflows separately; pooled, per-asset, and per-regime scopes; and lags from 1 to 24 periods (8 to 192 hours) — over 75 specifications total.

The result is null. All inflow Z-score coefficients have p-values above 0.20. The overlay contributes exactly zero Sharpe improvement. USDT shows a marginal signal at lag 24 (p = 0.085), but at an implausible 8-day horizon this is a multiple-testing artifact, not a tradeable finding.

This is consistent with Chi, Chu, and Hao (2024), who find that BTC and ETH exchange inflows lack predictive power for returns. The implication is that on-chain flow information is incorporated into perpetual futures pricing faster than the 8-hour settlement cycle. If a transmission mechanism exists from exchange deposits to funding rate compression, it operates at frequencies this framework cannot capture.

## Conclusion

Delta-neutral crypto carry is viable under two conditions: low macro volatility (VIX ≤ 25) and institutional execution costs (≤ 3 bps per side). Outside these conditions it loses money. The post-2021 regime shows structural degradation even within low-VIX environments, consistent with increased institutional participation compressing the carry premium. On-chain exchange inflows do not improve timing at 8-hour resolution.

Natural extensions include testing sub-hourly inflow data where the information transmission may still be observable, using open interest as a crowding and liquidation risk indicator, replacing realized volatility with a directional persistence measure that better captures the conditions under which funding rates remain elevated, and expanding to additional perpetual markets where the carry premium may be less competed away.
