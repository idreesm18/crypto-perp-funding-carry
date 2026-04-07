# Ideas & Future Work

Running list of observations and extensions beyond the core backtest.

---

## From the basis → funding rate analysis

### Slope spikes and volatility regimes
The rolling slope (pass-through from basis to funding) spikes during sustained directional moves. When the market trends in one direction throughout the 8h window, the perp premium stays elevated and the settlement-time snapshot is representative of the period average. In choppy or bidirectional markets the basis oscillates and the snapshot is noise.

**Key observation from the chart:** The March 2020 COVID crash produced the largest realized vol spike (~1.8 annualized) but did NOT spike the slope — slope was actually low during that period. This is a direct counterexample to the simple "high vol = high slope" hypothesis. A crash is chaotic and bidirectional within each 8h settlement window, so the basis flips rather than staying elevated. The slope spikes instead cluster around the 2021 bull run (Jan–Apr 2021) and isolated sharp rallies (Jan 2023 post-FTX recovery, mid-2024) — all periods of sustained upward pressure, not crash vol.

**Implication:** Raw realized vol is the wrong conditioning variable. What drives slope is *directional persistence* within the 8h window, not magnitude of moves. A better proxy might be: did the market close higher/lower than it opened across the majority of hourly candles in the window? Or a trend-strength indicator (e.g. ADX, or the ratio of |sum of returns| to sum of |returns|).

**Ideas:**
- Replace realized vol with a directionality measure: `|sum(hourly returns)| / sum(|hourly returns|)` over the 8h window — 1.0 means perfectly trending, 0 means perfectly mean-reverting
- Test if slope spikes are predictive of the *next* period's funding rate (does a trending market persist into the next settlement?)
- Crash regimes (high vol, negative returns) may warrant a different carry strategy — funding can go sharply negative as longs get liquidated; consider a regime filter that exits carry during drawdown environments

### Correlation is noisy at 1-month windows
Rolling r (1-month) swings between ~0.1 and ~0.9. The relationship is real but highly variable. Implications:
- A pure basis-at-settlement signal will have a lot of false signals
- Worth testing longer averaging windows for the basis (e.g. average basis over last 3 or 8 hours rather than snapshot)
- Compare ETH vs BTC — does ETH have higher or lower pass-through? ETH tends to have more retail speculation which may mean more persistent premiums

---

## Signal ideas

### Time-averaged basis instead of snapshot
Instead of basis at the moment of funding settlement, use the TWAP of the basis over the preceding 8h. This should correlate better with the actual funding rate (which is itself a time-average). Data is available from hourly klines.

### Lagged basis as predictor
Does the basis in the *previous* 8h window predict the funding rate in the *next* window? If yes, you can build a forward-looking signal rather than a concurrent one. Preliminary step: run a lag-1 regression (basis_t → funding_t+1).

### Funding rate momentum
Do high funding rate periods cluster? If funding > threshold today, is it likely to be high tomorrow? A simple autocorrelation check on the funding rate series would answer this.

---

## Portfolio ideas

### ETH/BTC funding spread
ETH typically has higher and more volatile funding than BTC. Is there a systematic spread? Could trade long ETH carry, short BTC carry when the spread is wide.

### Threshold optimization
The baseline signal uses a fixed funding rate threshold to enter. Is there an optimal threshold that maximizes Sharpe? Worth running a grid search (0.01% to 0.05% per 8h) and checking if the result holds out-of-sample.

---

## Data ideas

### Intraday basis (sub-hourly)
The 1h klines miss intraday basis swings. If the perp spikes mid-candle and reverts by the close, we don't see it. 1-minute klines are available on data.binance.vision — would let us compute a true TWAP basis and better understand intraday dynamics.

### Open interest as a crowding / risk indicator
OI data is pulled but not used in the current build. Potential future uses:

- **Crowding warning**: High OI + positive funding = the carry trade is crowded. Many leveraged longs are paying shorts, making the trade profitable but fragile. Rapid OI growth could be a signal to reduce position size rather than add.
- **Liquidation cascade detector**: A sharp OI spike followed by a sudden collapse is typically a mass liquidation event — exactly when funding goes sharply negative and carry loses money. Could use OI drawdown as a stop-loss trigger.
- **Regime conditioning**: Split backtest results by OI quartile (low/high crowding) to see if carry performs differently depending on how leveraged the market is.

Note: OI history is currently limited to 90 days. Full history back to 2020 is available via ~2000 individual daily downloads on data.binance.vision — worth pulling only if OI becomes part of the signal.

### More symbols
Only BTC and ETH currently. Other liquid perp markets (SOL, BNB, XRP) may show different funding dynamics. Could extend the backtest to a multi-asset carry portfolio.

### Exchange inflow as a carry suppression signal
**[TESTED — NULL]** Tested BTC, ETH, and USDT hourly exchange inflows (Dune Analytics, 2020–2026) as predictors of funding rate changes. OLS with Newey-West HAC errors across pooled/per-asset/pre-post-2021 scopes and lags 1–24 (8h–192h). All p-values > 0.20. Overlay ΔSharpe = 0.000. USDT shows a marginal hit at lag 24 (p=0.085) — likely multiple-testing artifact at an implausible 8-day horizon, not acted upon. Consistent with Chi, Chu & Hao (2024, arXiv:2411.06327) finding that BTC/ETH inflows lack predictive power for returns; USDT predicts spot returns but the transmission to funding rates is too indirect or too fast to capture at 8h resolution.
