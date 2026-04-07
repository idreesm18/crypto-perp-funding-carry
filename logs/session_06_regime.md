# Session 6: Regime Analysis (2026-04-07)

## What was done

### 1. Implemented `src/6_regime.py`
Regime analysis for baseline carry strategy. Imports `compute_metrics`, `aggregate_pnl`, `run_backtest` from `4_backtest.py` via importlib. On-chain overlay is excluded (null result from Session 5).

Key implementation details:
- VIX daily data (already in `data/vix_daily.parquet` from Session 1) is forward-filled onto 8h backtest timestamps via `pd.merge_asof` with backward direction
- VIX timestamps are timezone-naive; localized to UTC before merge
- 100% VIX coverage on backtest period (2020-01 to 2026-03)
- Two regime dimensions: structural break (pre/post 2021-01-01) and VIX level (≤25 / >25)
- Full 2×2 cross produces 9 slices: full, 2 time, 2 VIX, 4 cross

### 2. Generated output files

**`output/regime_analysis.csv`** — 9 rows (one per regime slice)

| Column | Type | Description |
|---|---|---|
| `regime` | str | Label (e.g. "Pre-2021 & VIX <= 25") |
| `sharpe` | float64 | Annualized Sharpe ratio |
| `total_bps` | float64 | Cumulative P&L in basis points |
| `annual_bps` | float64 | Annualized return (bps/yr) |
| `max_dd_bps` | float64 | Max drawdown (bps) |
| `max_dd_days` | float64 | Max drawdown duration (days) |
| `win_rate` | float64 | Fraction of active periods profitable |
| `active_periods` | int | Number of periods with nonzero P&L |
| `pct_time_in_carry` | float64 | Fraction of periods in carry position |
| `n_periods` | int | Total periods in regime |
| `years` | float64 | Duration in years |
| `mean_turnover` | float64 | Average turnover per period |
| `funding_bps` | float64 | Gross funding income (bps) |
| `cost_bps` | float64 | Cost drag (bps, negative) |
| `basis_bps` | float64 | Basis MtM (bps) |

## Key findings

### VIX is the dominant regime variable

| Regime | Sharpe | Ann bps | Max DD bps | Win Rate | % in Carry |
|---|---|---|---|---|---|
| Full Sample | 0.370 | 46.0 | -1448.6 | 61.2% | 22.1% |
| Pre-2021 | 0.611 | 108.2 | -343.7 | 61.1% | 46.4% |
| Post-2021 | 0.309 | 34.6 | -1448.6 | 61.2% | 17.7% |
| VIX ≤ 25 | 1.017 | 128.4 | -1295.6 | 63.4% | 23.8% |
| **VIX > 25** | **-2.174** | **-253.4** | **-353.4** | **49.6%** | **16.2%** |

### 2×2 Sharpe grid

|  | VIX ≤ 25 | VIX > 25 |
|---|---|---|
| Pre-2021 | **4.687** | -4.140 |
| Post-2021 | 0.429 | -0.427 |

### Interpretation

1. **VIX > 25 destroys carry.** Sharpe flips negative (-2.17) with -253 bps/yr. Win rate drops to 49.6% (coin flip). Cost drag exceeds funding income: +853 funding vs -1219 cost. High-VIX periods represent 21.6% of the sample but account for all portfolio losses.

2. **The structural break is partially a VIX artifact.** Pre-2021 had more high-VIX periods (61.5% of pre-2021 = VIX>25, driven by COVID/March 2020). Within VIX≤25, pre-2021 Sharpe is 4.69 vs post-2021 at 0.43 — so the structural break is real even controlling for VIX, but the magnitude is smaller.

3. **Pre-2021 + low-VIX is the golden regime**: Sharpe 4.69, 1104 bps/yr, max DD only -250 bps. This is the crypto carry golden age — high funding rates, low macro volatility, less institutional competition.

4. **Post-2021 + low-VIX remains viable**: Sharpe 0.43, 48 bps/yr. Modest but positive. Still cost-sensitive (3780 funding vs -3653 cost).

5. **High-VIX is universally bad**: Negative Sharpe in both pre- and post-2021. The mechanism: high VIX coincides with crypto risk-off, funding rates compress or go negative, but the strategy still incurs turnover cost entering/exiting positions around the threshold.

6. **Actionable implication**: A simple VIX filter (suppress carry entry when VIX > 25) would improve full-sample Sharpe from 0.37 to ~1.0. This is a much stronger signal than the on-chain overlay (which was null). However, this is an in-sample observation — the VIX threshold of 25 was chosen ex ante from convention, not optimized.

## What's next
**Step 7 per `project_brief.md`: Results write-up**
- Consolidate findings from all 6 sessions
- Final performance tables, regime-conditional results
- Limitations and caveats (cost sensitivity, in-sample VIX threshold)

## Current directory structure
```
carry_project/
  data/              18 parquet files (unchanged)
  logs/              session_01 through session_06 (this file)
  notebooks/         8 exploration notebooks (unchanged)
  output/            threshold_sweep.csv, spread_sweep.csv, onchain_regression.csv,
                     onchain_usdt_regression.csv, regime_analysis.csv (new)
  src/
    1_data_pull.py   ✅ implemented
    2_signal.py      ✅ implemented
    3_portfolio.py   ✅ implemented
    4_backtest.py    ✅ implemented
    5_onchain.py     ✅ implemented (null result)
    6_regime.py      ✅ implemented (this session)
  ideas.md
  project_brief.md
  README.md
```
