# Session 1: Data Pull (2026-04-02)

## What was done

### 1. Implemented `src/1_data_pull.py`
Built the full data ingestion pipeline. The Binance REST API is geo-blocked (returns 451), so the script uses **bulk CSV downloads from `data.binance.vision`** instead. VIX comes from FRED.

Key implementation details:
- Monthly zip files for funding rates and klines (spot + perp)
- Daily metric files for open interest (last 90 days only)
- Handles inconsistent CSV formats: some files have headers, some don't; Binance switched from ms to μs timestamps in 2025
- Header detection: checks if first character is a digit (headerless) vs letter (has header)
- Timestamp normalization: values ≥ 1e13 are divided by 1000 (μs → ms)
- FRED VIX column name is `observation_date` (not `DATE`), uses `"."` for missing values
- Rate limiting: 0.05s sleep per request
- Retry with backoff on 429/418

### 2. Generated 9 parquet files in `data/`

| File | Rows | Columns | Range |
|---|---|---|---|
| `btc_funding_rates.parquet` | 6,846 | timestamp, funding_rate | 2020-01 → 2026-03 |
| `eth_funding_rates.parquet` | 6,846 | timestamp, funding_rate | 2020-01 → 2026-03 |
| `btc_spot_klines.parquet` | 53,993 | timestamp, open, high, low, close, volume, quote_volume | 2020-01 → 2026-02 |
| `eth_spot_klines.parquet` | 53,993 | timestamp, open, high, low, close, volume, quote_volume | 2020-01 → 2026-02 |
| `btc_perp_klines.parquet` | 54,768 | timestamp, open, high, low, close, volume, quote_volume | 2020-01 → 2026-03 |
| `eth_perp_klines.parquet` | 54,768 | timestamp, open, high, low, close, volume, quote_volume | 2020-01 → 2026-03 |
| `btc_open_interest.parquet` | 25,920 | timestamp, open_interest, open_interest_value | last 90 days |
| `eth_open_interest.parquet` | 25,920 | timestamp, open_interest, open_interest_value | last 90 days |
| `vix_daily.parquet` | 9,156 | timestamp, vix | 1990-01 → 2026-04 |

- All Binance timestamps are UTC-aware (`datetime64[ns, UTC]`)
- VIX timestamps are timezone-naive (trading days only)
- Spot klines end 1 month earlier than perp because the March 2026 spot monthly zip wasn't published yet on data.binance.vision
- Open interest is 5-min resolution, only last 90 days — supplementary data, not used in any signal

### 3. Created exploration notebooks in `notebooks/`
- `funding_rates.ipynb` — schema, coverage, gap check (with ±10s tolerance for ms rounding), distribution, extremes, monthly averages
- `klines.ipynb` — spot vs perp comparison, basis in bps, gap check, basis→funding correlation analysis, rolling 1-month regression, slope vs realized vol chart
- `vix.ipynb` — distribution, regime thresholds (VIX > 25), pre/post-2021 split
- `open_interest.ipynb` — schema, daily averages, BTC vs ETH comparison

### 4. Key findings from exploration
- **Overall basis→funding correlation**: r = 0.689 (BTC). The relationship is real but not perfect — funding is an 8h time-weighted average, not a snapshot.
- **Rolling 1-month r swings between ~0.1 and 0.9** — highly variable over time.
- **Slope (pass-through) interpretation**: `slope × 10000` = bps of funding per bps of basis. Mean ~0.19, meaning funding captures ~19% of the instantaneous basis (the rest averages out over the 8h window).
- **COVID crash observation**: March 2020 had the highest realized vol but did NOT spike the slope. Crashes are bidirectional/chaotic within each 8h window, so the snapshot basis is noisy. Slope spikes instead during sustained directional moves (2021 bull run, Jan 2023 recovery, mid-2024).
- **Implication**: Raw realized vol is the wrong conditioning variable for the basis→funding relationship. Directional persistence within the 8h window matters more.

### 5. Created `ideas.md`
Running doc of observations and extension ideas beyond the core build. Covers: slope spike analysis, directionality measures, time-averaged basis, funding momentum, ETH/BTC spread, OI as crowding indicator, threshold optimization, sub-hourly data.

## Installed dependencies
```
pip3 install pandas requests pyarrow matplotlib scipy
```

## What's next
**Step 2 per `project_brief.md` build order: `src/2_signal.py`**
- Baseline funding rate carry signal (Layer 1)
- Binary entry/exit flag: enter when funding_rate > threshold, exit when below or negative
- Test multiple threshold levels
- The on-chain timing overlay (Layer 2) comes later in step 5

## Current directory structure
```
carry_project/
  data/              9 parquet files (see table above)
  logs/              session logs (this file)
  notebooks/         4 exploration notebooks
  output/            empty (for future charts/tables)
  src/
    1_data_pull.py   ✅ implemented and tested
    2_signal.py      stub (next)
    3_portfolio.py   stub
    4_backtest.py    stub
    5_onchain.py     stub
    6_regime.py      stub
  ideas.md           running ideas doc
  project_brief.md   full project spec
  README.md          project overview (checklist, all unchecked)
  .gitignore         excludes data/, .parquet, .csv, .env, __pycache__
```
