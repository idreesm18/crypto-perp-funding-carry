# ABOUTME: P&L engine — runs carry strategy through history, computes performance metrics.
# ABOUTME: Outputs data/backtest.parquet + sweep tables — run: python3 src/4_backtest.py

import importlib.util
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
PERIODS_PER_YEAR = 365.25 * 3  # 8h funding periods per year

# Import build_portfolio from 3_portfolio.py (numeric prefix needs importlib)
_spec = importlib.util.spec_from_file_location(
    "portfolio_mod", os.path.join(os.path.dirname(__file__), "3_portfolio.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build_portfolio = _mod.build_portfolio
load_signals = _mod.load_signals

DEFAULT_THRESHOLD = 0.0001  # 0.01% per 8h
DEFAULT_SPREAD_BPS = 5


def load_8h_prices():
    """Load spot and perp prices at 8h funding settlement times.

    Uses candle open price (= price at timestamp, since Binance kline
    timestamps mark candle start).
    """
    frames = []
    for prefix in ["btc", "eth"]:
        spot = pd.read_parquet(os.path.join(DATA_DIR, f"{prefix}_spot_klines.parquet"))
        perp = pd.read_parquet(os.path.join(DATA_DIR, f"{prefix}_perp_klines.parquet"))

        sp = spot.loc[spot["timestamp"].dt.hour.isin([0, 8, 16]),
                      ["timestamp", "open"]].rename(columns={"open": "spot_price"})
        pp = perp.loc[perp["timestamp"].dt.hour.isin([0, 8, 16]),
                      ["timestamp", "open"]].rename(columns={"open": "perp_price"})

        merged = sp.merge(pp, on="timestamp", how="inner")
        merged["symbol"] = prefix.upper()
        frames.append(merged)

    return pd.concat(frames, ignore_index=True).sort_values(["symbol", "timestamp"])


def run_backtest(signals, prices, threshold=DEFAULT_THRESHOLD,
                 spread_bps=DEFAULT_SPREAD_BPS):
    """Run carry backtest with P&L decomposition.

    P&L components per period per asset:
      1. funding_pnl = weight × funding_rate (collected at settlement)
      2. cost_drag   = -cost (spread on both legs per unit of turnover)
      3. basis_pnl   = weight_{t-1} × (spot_return - perp_return)
                       MtM from holding carry position between settlements;
                       near zero for a delta-neutral trade

    Returns per-period per-asset DataFrame.
    """
    portfolio = build_portfolio(signals, threshold, spread_bps)

    df = portfolio.merge(prices, on=["timestamp", "symbol"], how="left")
    df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

    # 1. Funding income
    df["funding_pnl"] = df["weight"] * df["funding_rate"]

    # 2. Cost drag
    df["cost_drag"] = -df["cost"]

    # 3. Basis P&L: position held from T-8h to T has weight_{T-8h}
    df["spot_ret"] = df.groupby("symbol")["spot_price"].pct_change(fill_method=None)
    df["perp_ret"] = df.groupby("symbol")["perp_price"].pct_change(fill_method=None)
    prev_weight = df.groupby("symbol")["weight"].shift(1).fillna(0)
    df["basis_pnl"] = prev_weight * (df["spot_ret"].fillna(0) - df["perp_ret"].fillna(0))

    df["total_pnl"] = df["funding_pnl"] + df["cost_drag"] + df["basis_pnl"]

    cols = ["timestamp", "symbol", "weight", "funding_rate", "turnover",
            "funding_pnl", "cost_drag", "basis_pnl", "total_pnl"]
    return df[cols].reset_index(drop=True)


def aggregate_pnl(bt):
    """Sum per-asset P&L to portfolio level per timestamp."""
    return (bt.groupby("timestamp")
            .agg(funding_pnl=("funding_pnl", "sum"),
                 cost_drag=("cost_drag", "sum"),
                 basis_pnl=("basis_pnl", "sum"),
                 total_pnl=("total_pnl", "sum"),
                 turnover=("turnover", "sum"))
            .reset_index()
            .sort_values("timestamp"))


def _max_consecutive_true(arr):
    """Longest run of True in a boolean array."""
    best = current = 0
    for v in arr:
        if v:
            current += 1
            if current > best:
                best = current
        else:
            current = 0
    return best


def compute_metrics(agg):
    """Compute performance metrics from portfolio-level P&L series."""
    pnl = agg["total_pnl"].values
    n = len(pnl)
    years = n / PERIODS_PER_YEAR

    # Sharpe (annualized)
    sharpe = (pnl.mean() / pnl.std() * np.sqrt(PERIODS_PER_YEAR)) if pnl.std() > 0 else 0.0

    # Cumulative P&L
    cum = np.cumsum(pnl)
    total_bps = cum[-1] * 10_000
    ann_bps = total_bps / years if years > 0 else 0.0

    # Max drawdown
    peak = np.maximum.accumulate(cum)
    dd = cum - peak
    max_dd_bps = dd.min() * 10_000

    # Max drawdown duration
    underwater = dd < -1e-10
    max_dd_days = _max_consecutive_true(underwater) / 3

    # Turnover
    mean_to = agg["turnover"].mean()

    # Win rate (active periods only)
    active = pnl[pnl != 0]
    win_rate = (active > 0).mean() if len(active) > 0 else 0.0

    # Decomposition totals
    fund_bps = agg["funding_pnl"].sum() * 10_000
    cost_bps = agg["cost_drag"].sum() * 10_000
    basis_bps = agg["basis_pnl"].sum() * 10_000

    return {
        "sharpe": sharpe,
        "total_bps": total_bps,
        "annual_bps": ann_bps,
        "max_dd_bps": max_dd_bps,
        "max_dd_days": max_dd_days,
        "mean_turnover": mean_to,
        "win_rate": win_rate,
        "n_periods": n,
        "years": years,
        "funding_bps": fund_bps,
        "cost_bps": cost_bps,
        "basis_bps": basis_bps,
    }


def print_metrics(m, label=""):
    """Print formatted performance summary."""
    if label:
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")
    print(f"  Period:          {m['n_periods']} periods ({m['years']:.1f} yrs)")
    print(f"  Sharpe (ann):    {m['sharpe']:>8.3f}")
    print(f"  Total return:    {m['total_bps']:>8.1f} bps")
    print(f"  Annual return:   {m['annual_bps']:>8.1f} bps/yr")
    print(f"  Max drawdown:    {m['max_dd_bps']:>8.1f} bps")
    print(f"  Max DD duration: {m['max_dd_days']:>8.0f} days")
    print(f"  Turnover/period: {m['mean_turnover']:>8.4f}")
    print(f"  Win rate:        {m['win_rate']:>8.1%}")
    print(f"  --- P&L decomposition ---")
    print(f"  Funding income:  {m['funding_bps']:>8.1f} bps")
    print(f"  Cost drag:       {m['cost_bps']:>8.1f} bps")
    print(f"  Basis (MtM):     {m['basis_bps']:>8.1f} bps")


def sweep_thresholds(signals, prices, spread_bps=DEFAULT_SPREAD_BPS):
    """Run backtest across funding rate threshold values."""
    thresholds = [0.0, 0.00005, 0.0001, 0.00015, 0.0002, 0.0003, 0.0005]
    rows = []
    for t in thresholds:
        bt = run_backtest(signals, prices, threshold=t, spread_bps=spread_bps)
        m = compute_metrics(aggregate_pnl(bt))
        m["threshold"] = t
        rows.append(m)
    return pd.DataFrame(rows)


def sweep_spreads(signals, prices, threshold=DEFAULT_THRESHOLD):
    """Run backtest across spread assumptions."""
    spreads = [1, 2, 3, 5, 7, 10]
    rows = []
    for s in spreads:
        bt = run_backtest(signals, prices, threshold=threshold, spread_bps=s)
        m = compute_metrics(aggregate_pnl(bt))
        m["spread_bps"] = s
        rows.append(m)
    return pd.DataFrame(rows)


def main():
    signals = load_signals()
    prices = load_8h_prices()
    print(f"Loaded {len(signals)} signal rows, {len(prices)} price rows")

    # --- Baseline ---
    bt = run_backtest(signals, prices)
    agg = aggregate_pnl(bt)
    m = compute_metrics(agg)
    print_metrics(m, "Baseline Carry (threshold=0.01%, spread=5bps)")

    # --- Pre/post 2021 regime split ---
    split = pd.Timestamp("2021-01-01", tz="UTC")
    pre = agg[agg["timestamp"] < split]
    post = agg[agg["timestamp"] >= split]
    if len(pre) > 0:
        print_metrics(compute_metrics(pre), "Pre-2021")
    if len(post) > 0:
        print_metrics(compute_metrics(post), "Post-2021")

    # --- Threshold sweep ---
    print("\n\nThreshold sweep (spread=5bps):")
    ts = sweep_thresholds(signals, prices)
    hdr = f"  {'threshold':>10s}  {'sharpe':>7s}  {'total_bps':>9s}  {'ann_bps':>7s}  {'max_dd':>7s}  {'win%':>6s}"
    print(hdr)
    for _, r in ts.iterrows():
        print(f"  {r['threshold']*100:>9.4f}%  {r['sharpe']:>7.3f}  {r['total_bps']:>9.1f}  "
              f"{r['annual_bps']:>7.1f}  {r['max_dd_bps']:>7.1f}  {r['win_rate']:>5.1%}")

    # --- Spread sweep ---
    print("\nSpread sweep (threshold=0.01%):")
    ss = sweep_spreads(signals, prices)
    hdr = f"  {'bps/side':>8s}  {'sharpe':>7s}  {'total_bps':>9s}  {'ann_bps':>7s}  {'funding':>8s}  {'cost':>8s}"
    print(hdr)
    for _, r in ss.iterrows():
        print(f"  {r['spread_bps']:>8.0f}  {r['sharpe']:>7.3f}  {r['total_bps']:>9.1f}  "
              f"{r['annual_bps']:>7.1f}  {r['funding_bps']:>8.1f}  {r['cost_bps']:>8.1f}")

    # --- Save outputs ---
    out_path = os.path.join(DATA_DIR, "backtest.parquet")
    bt.to_parquet(out_path, index=False)
    print(f"\nSaved {len(bt)} rows to {out_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts.to_csv(os.path.join(OUTPUT_DIR, "threshold_sweep.csv"), index=False)
    ss.to_csv(os.path.join(OUTPUT_DIR, "spread_sweep.csv"), index=False)
    print(f"Saved sweep tables to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
