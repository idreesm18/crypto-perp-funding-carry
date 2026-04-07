# ABOUTME: On-chain exchange inflow ingestion (Dune Analytics API), predictive regression, timing overlay.
# ABOUTME: Fetches hourly BTC+ETH+USDT exchange inflows via Dune API — run: python3 src/5_onchain.py
#
# Setup (one-time):
#   1. Create a free account at https://dune.com
#   2. Save src/dune_{btc,eth,usdt}_inflows.sql as Dune queries → note query IDs
#   3. Get a free API key: Dune → Settings → API Keys → Create
#   4. Set DUNE_API_KEY in .env
#   5. Set query IDs below
#
# Regression model (OLS, HAC errors):
#   Δfunding(T+1) = α + β₁·inflow_z(T) + β₂·funding_rate(T) + β₃·realized_vol(T) + ε
#   Criterion: only build timing overlay if β₁ significant (p < 0.10) and negative

import importlib.util
import os
import time

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

# Load .env from project root (one level up from src/)
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# ── Fill these in after saving the SQL files as Dune queries ──────────────
DUNE_BTC_QUERY_ID  = 6950674
DUNE_ETH_QUERY_ID  = 6950695
DUNE_USDT_QUERY_ID = 6957748      # ← set after saving dune_usdt_inflows.sql
# ─────────────────────────────────────────────────────────────────────────

DUNE_API_BASE  = "https://api.dune.com/api/v1"
DUNE_PAGE_SIZE = 50_000    # rows per page (Dune max)

ZSCORE_WINDOW = 30   # days for rolling Z-score
HAC_LAGS = 3         # Newey-West lag truncation

# Import backtest machinery from 4_backtest.py
_spec = importlib.util.spec_from_file_location(
    "backtest_mod", os.path.join(os.path.dirname(__file__), "4_backtest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
run_backtest   = _mod.run_backtest
aggregate_pnl  = _mod.aggregate_pnl
compute_metrics = _mod.compute_metrics
print_metrics  = _mod.print_metrics
load_8h_prices = _mod.load_8h_prices
load_signals   = _mod.load_signals
build_portfolio = _mod.build_portfolio

DEFAULT_THRESHOLD = 0.0001
DEFAULT_SPREAD_BPS = 5


# ---------------------------------------------------------------------------
# 1. Dune API helpers
# ---------------------------------------------------------------------------

def _dune_headers():
    key = os.environ.get("DUNE_API_KEY", "").strip()
    if not key:
        raise EnvironmentError(
            "DUNE_API_KEY not set.\n"
            "Get a free key at https://dune.com → Settings → API Keys, then:\n"
            "  export DUNE_API_KEY=your_key_here"
        )
    return {"X-Dune-API-Key": key}


def _dune_execute(query_id):
    """Trigger execution of a saved Dune query. Returns execution_id."""
    url  = f"{DUNE_API_BASE}/query/{query_id}/execute"
    resp = requests.post(url, headers=_dune_headers(), json={"performance": "medium"})
    resp.raise_for_status()
    return resp.json()["execution_id"]


def _dune_poll(execution_id, poll_interval=5):
    """Block until execution completes. Raises on failure."""
    url = f"{DUNE_API_BASE}/execution/{execution_id}/status"
    while True:
        resp = requests.get(url, headers=_dune_headers())
        resp.raise_for_status()
        state = resp.json()["state"]
        if state == "QUERY_STATE_COMPLETED":
            return
        if state in ("QUERY_STATE_FAILED", "QUERY_STATE_CANCELED", "QUERY_STATE_EXPIRED"):
            raise RuntimeError(f"Dune execution {execution_id} ended with state: {state}")
        print(f"  [{state}] waiting...", flush=True)
        time.sleep(poll_interval)


def _dune_fetch_rows(query_id):
    """Fetch all result rows for a query, paginating automatically."""
    rows = []
    offset = 0
    while True:
        url    = f"{DUNE_API_BASE}/query/{query_id}/results"
        params = {"limit": DUNE_PAGE_SIZE, "offset": offset}
        resp   = requests.get(url, headers=_dune_headers(), params=params)
        resp.raise_for_status()
        body  = resp.json()
        page  = body["result"]["rows"]
        rows.extend(page)
        total = body["result"]["metadata"]["total_row_count"]
        offset += len(page)
        print(f"  fetched {offset}/{total} rows", flush=True)
        if offset >= total:
            break
        time.sleep(0.2)
    return rows


# ---------------------------------------------------------------------------
# 2. Data ingestion
# ---------------------------------------------------------------------------

def fetch_inflows(force=False):
    """Fetch hourly BTC + ETH + USDT exchange inflows from Dune Analytics.

    Caches results to data/dune_{btc,eth,usdt}_inflows.parquet.
    Set force=True to re-execute even if cache exists.

    Returns combined DataFrame with columns: timestamp, symbol, inflow
    """
    if DUNE_BTC_QUERY_ID is None or DUNE_ETH_QUERY_ID is None:
        raise ValueError(
            "Set DUNE_BTC_QUERY_ID and DUNE_ETH_QUERY_ID in src/5_onchain.py.\n"
            "Save src/dune_btc_inflows.sql and src/dune_eth_inflows.sql as Dune queries,\n"
            "then paste the numeric IDs from the query URLs into those constants."
        )

    configs = [
        ("BTC",  DUNE_BTC_QUERY_ID,  "btc_inflow"),
        ("ETH",  DUNE_ETH_QUERY_ID,  "eth_inflow"),
    ]
    if DUNE_USDT_QUERY_ID is not None:
        configs.append(("USDT", DUNE_USDT_QUERY_ID, "usdt_inflow"))
    frames = []
    for symbol, query_id, value_col in configs:
        cache = os.path.join(DATA_DIR, f"dune_{symbol.lower()}_inflows.parquet")

        if not force and os.path.exists(cache):
            print(f"{symbol}: loading from cache ({cache})")
            df = pd.read_parquet(cache)
        else:
            print(f"{symbol}: executing Dune query {query_id}...")
            exec_id = _dune_execute(query_id)
            print(f"  execution_id: {exec_id}")
            _dune_poll(exec_id)
            print(f"  fetching results...")
            rows = _dune_fetch_rows(query_id)

            df = pd.DataFrame(rows)
            df.columns = df.columns.str.strip().str.lower()
            df["timestamp"] = pd.to_datetime(df["hour"], utc=True)
            df["inflow"]    = pd.to_numeric(df[value_col], errors="coerce")
            df["symbol"]    = symbol
            df = (df[["timestamp", "symbol", "inflow"]]
                  .dropna()
                  .drop_duplicates("timestamp")
                  .sort_values("timestamp")
                  .reset_index(drop=True))
            df.to_parquet(cache, index=False)
            print(f"  cached to {cache}")

        print(f"  {len(df)} hourly rows  "
              f"{df['timestamp'].min().date()} → {df['timestamp'].max().date()}")
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 2. Z-score construction
# ---------------------------------------------------------------------------

def compute_inflow_zscore(inflows, window=ZSCORE_WINDOW):
    """Rolling Z-score of hourly inflows per asset over a trailing window.

    window is in days; converted to hours internally.
    Returns DataFrame with added inflow_z column.
    """
    window_hours = window * 24
    frames = []
    for sym in inflows["symbol"].unique():
        sub = inflows[inflows["symbol"] == sym].copy().sort_values("timestamp")
        roll = sub["inflow"].rolling(window_hours, min_periods=window_hours // 2)
        sub["inflow_z"] = (sub["inflow"] - roll.mean()) / roll.std()
        frames.append(sub)
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# 3. Merge inflow Z-scores onto 8h funding timestamps
# ---------------------------------------------------------------------------

def merge_inflow_with_funding(inflows_z, signals):
    """Asof-join hourly inflow Z-score onto 8h funding timestamps.

    Uses backward merge: each funding period gets the most recent inflow
    reading at or before that timestamp. No look-ahead.
    """
    frames = []
    for sym in signals["symbol"].unique():
        sig = signals[signals["symbol"] == sym].sort_values("timestamp")
        inf = (inflows_z[inflows_z["symbol"] == sym]
               [["timestamp", "inflow", "inflow_z"]]
               .sort_values("timestamp"))
        merged = pd.merge_asof(sig, inf, on="timestamp", direction="backward")
        frames.append(merged)
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "timestamp"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3b. Merge USDT inflow (market-wide signal) onto all funding timestamps
# ---------------------------------------------------------------------------

def merge_usdt_with_funding(usdt_z, signals):
    """Asof-join USDT inflow Z-score onto all funding timestamps.

    USDT inflow is a market-wide signal (not per-asset), so the same
    Z-score is applied to both BTC and ETH funding settlements.
    """
    usdt = (usdt_z[usdt_z["symbol"] == "USDT"]
            [["timestamp", "inflow", "inflow_z"]]
            .rename(columns={"inflow": "usdt_inflow", "inflow_z": "usdt_z"})
            .sort_values("timestamp"))
    frames = []
    for sym in signals["symbol"].unique():
        sig = signals[signals["symbol"] == sym].sort_values("timestamp")
        merged = pd.merge_asof(sig, usdt, on="timestamp", direction="backward")
        frames.append(merged)
    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "timestamp"]).reset_index(drop=True)


def run_usdt_regression(merged_usdt, lag=1):
    """OLS: does usdt_z(T) predict Δfunding(T+lag)?

    Expected sign: POSITIVE (USDT on exchanges → buying pressure → basis
    expansion → funding increase). Chi, Chu & Hao (2024) find this at 1-6h.
    """
    results = {}
    scopes = [
        ("pooled",    merged_usdt),
        ("BTC",       merged_usdt[merged_usdt["symbol"] == "BTC"]),
        ("ETH",       merged_usdt[merged_usdt["symbol"] == "ETH"]),
        ("pre_2021",  merged_usdt[merged_usdt["timestamp"] < pd.Timestamp("2021-01-01", tz="UTC")]),
        ("post_2021", merged_usdt[merged_usdt["timestamp"] >= pd.Timestamp("2021-01-01", tz="UTC")]),
    ]
    for name, df in scopes:
        df = df.dropna(subset=["usdt_z", "funding_rate", "realized_vol_30d"]).copy()
        df = df.sort_values("timestamp")
        df["funding_change"] = df.groupby("symbol")["funding_rate"].diff(lag).shift(-lag)
        df = df.dropna(subset=["funding_change"])

        if len(df) < 50:
            results[name] = {"n": len(df), "status": "insufficient_data"}
            continue

        X = sm.add_constant(df[["usdt_z", "funding_rate", "realized_vol_30d"]])
        model = sm.OLS(df["funding_change"], X).fit(
            cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})

        results[name] = {
            "n": len(df),
            "r2": model.rsquared,
            "usdt_z_coef":  model.params.get("usdt_z", np.nan),
            "usdt_z_tstat": model.tvalues.get("usdt_z", np.nan),
            "usdt_z_pval":  model.pvalues.get("usdt_z", np.nan),
            "status": "ok",
            "model": model,
        }
    return results


# ---------------------------------------------------------------------------
# 4. Predictive regression (BTC/ETH inflows — per-asset)
# ---------------------------------------------------------------------------

def run_predictive_regression(merged, lag=1):
    """OLS with HAC errors: does inflow_z(T) predict Δfunding(T+lag)?

    Model per scope:
      Δfunding(T+lag) = α + β₁·inflow_z(T) + β₂·funding_rate(T) + β₃·realized_vol(T) + ε

    Returns dict of results keyed by scope name.
    """
    results = {}
    for name, df in _regression_scopes(merged):
        df = df.dropna(subset=["inflow_z", "funding_rate", "realized_vol_30d"]).copy()
        df = df.sort_values("timestamp")
        df["funding_change"] = df.groupby("symbol")["funding_rate"].diff(lag).shift(-lag)
        df = df.dropna(subset=["funding_change"])

        if len(df) < 50:
            results[name] = {"n": len(df), "status": "insufficient_data"}
            continue

        X = sm.add_constant(df[["inflow_z", "funding_rate", "realized_vol_30d"]])
        model = sm.OLS(df["funding_change"], X).fit(
            cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})

        results[name] = {
            "n": len(df),
            "r2": model.rsquared,
            "inflow_z_coef":  model.params.get("inflow_z", np.nan),
            "inflow_z_tstat": model.tvalues.get("inflow_z", np.nan),
            "inflow_z_pval":  model.pvalues.get("inflow_z", np.nan),
            "funding_coef":   model.params.get("funding_rate", np.nan),
            "funding_pval":   model.pvalues.get("funding_rate", np.nan),
            "vol_coef":       model.params.get("realized_vol_30d", np.nan),
            "vol_pval":       model.pvalues.get("realized_vol_30d", np.nan),
            "status": "ok",
            "model": model,
        }
    return results


def _regression_scopes(merged):
    """Yield (name, df) for pooled, per-asset, and pre/post-2021 regimes."""
    yield ("pooled",    merged)
    for sym in sorted(merged["symbol"].unique()):
        yield (sym, merged[merged["symbol"] == sym])
    split = pd.Timestamp("2021-01-01", tz="UTC")
    yield ("pre_2021",  merged[merged["timestamp"] < split])
    yield ("post_2021", merged[merged["timestamp"] >= split])


def print_regression_results(results):
    print(f"\n{'='*75}")
    print("  Predictive Regression: inflow_z(T) → Δfunding(T+1)")
    print(f"  HAC standard errors (Newey-West, {HAC_LAGS} lags)")
    print(f"{'='*75}")
    print(f"  {'Scope':<12s}  {'N':>6s}  {'β(z)':>10s}  {'t(z)':>7s}  {'p(z)':>7s}  {'R²':>7s}  {'Sig?':>5s}")
    print(f"  {'-'*67}")
    for name, r in results.items():
        if r["status"] != "ok":
            print(f"  {name:<12s}  {r['n']:>6d}  {'insufficient data':>40s}")
            continue
        sig = ("***" if r["inflow_z_pval"] < 0.01 else
               "**"  if r["inflow_z_pval"] < 0.05 else
               "*"   if r["inflow_z_pval"] < 0.10 else "")
        print(f"  {name:<12s}  {r['n']:>6d}  {r['inflow_z_coef']:>10.2e}  "
              f"{r['inflow_z_tstat']:>7.3f}  {r['inflow_z_pval']:>7.4f}  "
              f"{r['r2']:>7.4f}  {sig:>5s}")


# ---------------------------------------------------------------------------
# 5. Timing overlay — only built if regression is significant
# ---------------------------------------------------------------------------

def apply_overlay(signals, inflows_z, z_threshold=2.0, funding_threshold=DEFAULT_THRESHOLD):
    """Suppress carry entry when inflow Z-score > z_threshold."""
    merged = merge_inflow_with_funding(inflows_z, signals)
    merged["suppress"] = (merged["inflow_z"] > z_threshold).astype(int)
    merged["overlay_signal"] = np.where(
        (merged["funding_rate"] > funding_threshold) & (merged["suppress"] == 0), 1, 0)
    return merged


def run_overlay_backtest(signals, inflows_z, prices, z_threshold=2.0,
                         funding_threshold=DEFAULT_THRESHOLD, spread_bps=DEFAULT_SPREAD_BPS):
    overlay = apply_overlay(signals, inflows_z, z_threshold, funding_threshold)
    overlay_signals = overlay[["timestamp", "symbol", "funding_rate", "realized_vol_30d"]].copy()
    overlay_signals["signal"] = overlay["overlay_signal"]
    bt = run_backtest(overlay_signals, prices, threshold=funding_threshold, spread_bps=spread_bps)
    return bt, overlay


def sweep_z_thresholds(signals, inflows_z, prices,
                       funding_threshold=DEFAULT_THRESHOLD, spread_bps=DEFAULT_SPREAD_BPS):
    rows = []
    for zt in [1.0, 1.5, 2.0, 2.5, 3.0]:
        bt, overlay = run_overlay_backtest(signals, inflows_z, prices, zt,
                                           funding_threshold, spread_bps)
        m = compute_metrics(aggregate_pnl(bt))
        m["z_threshold"] = zt
        n_active = (overlay["funding_rate"] > funding_threshold).sum()
        m["pct_suppressed"] = (overlay["suppress"] == 1).sum() / max(n_active, 1) * 100
        rows.append(m)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # --- 1. Fetch inflows via Dune API ---
    print("Fetching exchange inflow data from Dune Analytics...")
    inflows = fetch_inflows()
    print(f"Total: {len(inflows)} hourly rows across BTC + ETH\n")

    for sym in sorted(inflows["symbol"].unique()):
        sub = inflows[inflows["symbol"] == sym]
        print(f"  {sym}: mean={sub['inflow'].mean():,.2f}  "
              f"median={sub['inflow'].median():,.2f}  std={sub['inflow'].std():,.2f}")

    # --- 2. Z-scores ---
    inflows_z = compute_inflow_zscore(inflows)
    print(f"\nZ-score stats (rolling {ZSCORE_WINDOW}-day window):")
    for sym in sorted(inflows_z["symbol"].unique()):
        sub = inflows_z[inflows_z["symbol"] == sym].dropna(subset=["inflow_z"])
        print(f"  {sym}: mean={sub['inflow_z'].mean():.3f}  std={sub['inflow_z'].std():.3f}  "
              f"max={sub['inflow_z'].max():.2f}  >2σ={(sub['inflow_z'] > 2).mean()*100:.1f}%")

    # --- 3. Merge with funding ---
    signals = load_signals()
    merged = merge_inflow_with_funding(inflows_z, signals)
    n_matched = merged["inflow_z"].notna().sum()
    print(f"\nMerged: {len(merged)} funding periods, {n_matched} with inflow Z-score "
          f"({n_matched/len(merged)*100:.0f}%)")

    # --- 4. Predictive regression ---
    reg_results = run_predictive_regression(merged)
    print_regression_results(reg_results)

    # Save regression summary
    reg_rows = [{"scope": k, **{kk: vv for kk, vv in v.items() if kk != "model"}}
                for k, v in reg_results.items()]
    pd.DataFrame(reg_rows).to_csv(os.path.join(OUTPUT_DIR, "onchain_regression.csv"), index=False)
    print(f"\nSaved regression results to {OUTPUT_DIR}/onchain_regression.csv")

    # Also run multi-lag sweep for completeness
    print(f"\nMulti-lag sweep (pooled):")
    print(f"  {'Lag':>4s}  {'~Hours':>6s}  {'β(z)':>10s}  {'t(z)':>7s}  {'p(z)':>7s}")
    for lag in [1, 3, 8, 16, 24]:
        df = merged.dropna(subset=["inflow_z", "funding_rate", "realized_vol_30d"]).copy()
        df["funding_change"] = df.groupby("symbol")["funding_rate"].diff(lag).shift(-lag)
        df = df.dropna(subset=["funding_change"])
        X = sm.add_constant(df[["inflow_z", "funding_rate", "realized_vol_30d"]])
        m = sm.OLS(df["funding_change"], X).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
        p = m.pvalues.get("inflow_z", 1)
        sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
        print(f"  {lag:>4d}  {lag*8:>6d}h  {m.params['inflow_z']:>10.2e}  "
              f"{m.tvalues['inflow_z']:>7.3f}  {p:>7.4f}  {sig}")

    # --- 5. USDT inflow analysis (market-wide signal) ---
    usdt_data = inflows_z[inflows_z["symbol"] == "USDT"]
    if len(usdt_data) > 0:
        print(f"\n\n{'#'*75}")
        print("#  USDT Exchange Inflow Analysis (stablecoin = dry powder)")
        print(f"{'#'*75}")

        merged_usdt = merge_usdt_with_funding(inflows_z, signals)
        n_usdt = merged_usdt["usdt_z"].notna().sum()
        print(f"\nMerged USDT Z-score onto {n_usdt}/{len(merged_usdt)} funding periods")

        usdt_results = run_usdt_regression(merged_usdt)

        print(f"\n{'='*75}")
        print("  Predictive Regression: usdt_z(T) → Δfunding(T+1)")
        print(f"  Expected sign: POSITIVE (USDT on exchanges → buying → funding up)")
        print(f"  HAC standard errors (Newey-West, {HAC_LAGS} lags)")
        print(f"{'='*75}")
        print(f"  {'Scope':<12s}  {'N':>6s}  {'β(z)':>10s}  {'t(z)':>7s}  {'p(z)':>7s}  {'R²':>7s}  {'Sig?':>5s}")
        print(f"  {'-'*67}")
        for name, r in usdt_results.items():
            if r["status"] != "ok":
                print(f"  {name:<12s}  {r['n']:>6d}  {'insufficient data':>40s}")
                continue
            sig = ("***" if r["usdt_z_pval"] < 0.01 else
                   "**"  if r["usdt_z_pval"] < 0.05 else
                   "*"   if r["usdt_z_pval"] < 0.10 else "")
            print(f"  {name:<12s}  {r['n']:>6d}  {r['usdt_z_coef']:>10.2e}  "
                  f"{r['usdt_z_tstat']:>7.3f}  {r['usdt_z_pval']:>7.4f}  "
                  f"{r['r2']:>7.4f}  {sig:>5s}")

        # USDT multi-lag sweep
        print(f"\n  USDT multi-lag sweep (pooled):")
        print(f"  {'Lag':>4s}  {'~Hours':>6s}  {'β(z)':>10s}  {'t(z)':>7s}  {'p(z)':>7s}")
        for lag in [1, 3, 8, 16, 24]:
            df_u = merged_usdt.dropna(subset=["usdt_z", "funding_rate", "realized_vol_30d"]).copy()
            df_u["funding_change"] = df_u.groupby("symbol")["funding_rate"].diff(lag).shift(-lag)
            df_u = df_u.dropna(subset=["funding_change"])
            X = sm.add_constant(df_u[["usdt_z", "funding_rate", "realized_vol_30d"]])
            m = sm.OLS(df_u["funding_change"], X).fit(cov_type="HAC", cov_kwds={"maxlags": HAC_LAGS})
            p = m.pvalues.get("usdt_z", 1)
            sig = "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""
            print(f"  {lag:>4d}  {lag*8:>6d}h  {m.params['usdt_z']:>10.2e}  "
                  f"{m.tvalues['usdt_z']:>7.3f}  {p:>7.4f}  {sig}")

        # Save USDT regression results
        usdt_rows = [{"scope": k, **{kk: vv for kk, vv in v.items() if kk != "model"}}
                     for k, v in usdt_results.items()]
        pd.DataFrame(usdt_rows).to_csv(
            os.path.join(OUTPUT_DIR, "onchain_usdt_regression.csv"), index=False)
        print(f"\n  Saved USDT regression to {OUTPUT_DIR}/onchain_usdt_regression.csv")

        # Save merged USDT data
        merged_usdt.to_parquet(os.path.join(DATA_DIR, "onchain_usdt_merged.parquet"), index=False)
    else:
        print("\n(USDT query not configured — skipping stablecoin inflow analysis)")

    # --- 6. Overlay decision (BTC/ETH inflows) ---
    pooled = reg_results.get("pooled", {})
    is_significant = (pooled.get("status") == "ok" and
                      pooled.get("inflow_z_pval", 1.0) < 0.10 and
                      pooled.get("inflow_z_coef", 0) < 0)

    prices = load_8h_prices()

    if is_significant:
        print(f"\n{'='*75}")
        print("  RESULT: Significant lead-lag detected (p < 0.10, β < 0) — building overlay")
        print(f"{'='*75}")

        bt_base = run_backtest(signals, prices)
        m_base  = compute_metrics(aggregate_pnl(bt_base))
        print_metrics(m_base, "Baseline (no overlay)")

        bt_over, overlay_df = run_overlay_backtest(signals, inflows_z, prices)
        m_over  = compute_metrics(aggregate_pnl(bt_over))
        print_metrics(m_over, "On-chain overlay (z_threshold=2.0)")

        print(f"\n  Overlay impact:")
        print(f"    ΔSharpe:  {m_over['sharpe'] - m_base['sharpe']:+.3f}")
        print(f"    ΔReturn:  {m_over['total_bps'] - m_base['total_bps']:+.1f} bps")
        n_supp   = (overlay_df["suppress"] == 1).sum()
        n_active = (overlay_df["funding_rate"] > DEFAULT_THRESHOLD).sum()
        print(f"    Suppressed: {n_supp}/{n_active} ({n_supp/max(n_active,1)*100:.1f}%)")

        zs = sweep_z_thresholds(signals, inflows_z, prices)
        print(f"\n  Z-threshold sweep:")
        print(f"  {'z_thresh':>8s}  {'sharpe':>7s}  {'total_bps':>9s}  {'ann_bps':>7s}  "
              f"{'max_dd':>7s}  {'%suppr':>7s}")
        for _, r in zs.iterrows():
            print(f"  {r['z_threshold']:>8.1f}  {r['sharpe']:>7.3f}  {r['total_bps']:>9.1f}  "
                  f"{r['annual_bps']:>7.1f}  {r['max_dd_bps']:>7.1f}  {r['pct_suppressed']:>6.1f}%")
        zs.to_csv(os.path.join(OUTPUT_DIR, "onchain_z_sweep.csv"), index=False)

        split = pd.Timestamp("2021-01-01", tz="UTC")
        agg_base = aggregate_pnl(bt_base)
        agg_over = aggregate_pnl(bt_over)
        for label, fn in [("Pre-2021",  lambda d: d[d["timestamp"] < split]),
                          ("Post-2021", lambda d: d[d["timestamp"] >= split])]:
            mb = compute_metrics(fn(agg_base))
            mo = compute_metrics(fn(agg_over))
            print(f"  {label}: baseline Sharpe={mb['sharpe']:.3f} → "
                  f"overlay Sharpe={mo['sharpe']:.3f} (Δ={mo['sharpe']-mb['sharpe']:+.3f})")

    else:
        print(f"\n{'='*75}")
        print("  RESULT: No significant lead-lag relationship detected")
        print(f"{'='*75}")
        if pooled.get("status") == "ok":
            sign = "negative (expected direction)" if pooled["inflow_z_coef"] < 0 else "positive (unexpected)"
            print(f"  Pooled: β={pooled['inflow_z_coef']:.2e}, "
                  f"p={pooled['inflow_z_pval']:.4f}, R²={pooled['r2']:.4f}")
            print(f"  Coefficient sign: {sign}")
        print(f"\n  NULL RESULT: hourly exchange inflow Z-score does not significantly")
        print(f"  predict next-period funding rate changes at the 10% level.")
        print(f"\n  Running overlay for completeness...")
        bt_base = run_backtest(signals, prices)
        bt_over, _ = run_overlay_backtest(signals, inflows_z, prices)
        m_base = compute_metrics(aggregate_pnl(bt_base))
        m_over = compute_metrics(aggregate_pnl(bt_over))
        print(f"  Baseline Sharpe: {m_base['sharpe']:.3f}")
        print(f"  Overlay Sharpe:  {m_over['sharpe']:.3f}")
        print(f"  ΔSharpe:         {m_over['sharpe'] - m_base['sharpe']:+.3f}")

    # Save merged data for downstream use
    merged.to_parquet(os.path.join(DATA_DIR, "onchain_merged.parquet"), index=False)
    print(f"\nSaved merged data to data/onchain_merged.parquet")


if __name__ == "__main__":
    main()
