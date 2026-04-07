# ABOUTME: Splits carry strategy performance by market regime (pre/post-2021, VIX level).
# ABOUTME: Outputs output/regime_analysis.csv — run: python3 src/6_regime.py

import importlib.util
import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")

# Import compute_metrics and aggregate_pnl from 4_backtest.py
_spec = importlib.util.spec_from_file_location(
    "backtest_mod", os.path.join(os.path.dirname(__file__), "4_backtest.py"))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
aggregate_pnl = _mod.aggregate_pnl
compute_metrics = _mod.compute_metrics
run_backtest = _mod.run_backtest
load_signals = _mod.load_signals
load_8h_prices = _mod.load_8h_prices

SPLIT_DATE = pd.Timestamp("2021-01-01", tz="UTC")
VIX_THRESHOLD = 25


def load_vix():
    """Load VIX daily data, localize to UTC, and return with date column for merging."""
    vix = pd.read_parquet(os.path.join(DATA_DIR, "vix_daily.parquet"))
    vix["timestamp"] = pd.to_datetime(vix["timestamp"]).dt.tz_localize("UTC")
    vix = vix.sort_values("timestamp").dropna(subset=["vix"])
    return vix


def merge_vix_to_backtest(bt, vix):
    """Forward-fill daily VIX onto 8h backtest timestamps via asof join."""
    bt = bt.sort_values("timestamp")
    vix = vix.sort_values("timestamp")
    merged = pd.merge_asof(bt, vix, on="timestamp", direction="backward")
    return merged


def regime_metrics(agg, label):
    """Compute metrics for a regime slice and return as a dict with label."""
    if len(agg) == 0:
        return None
    m = compute_metrics(agg)
    # Add carry-specific stats
    active_periods = (agg["total_pnl"] != 0).sum()
    m["regime"] = label
    m["active_periods"] = int(active_periods)
    m["pct_time_in_carry"] = active_periods / len(agg) if len(agg) > 0 else 0.0
    return m


def main():
    signals = load_signals()
    prices = load_8h_prices()
    bt = run_backtest(signals, prices)
    vix = load_vix()

    # Merge VIX onto per-asset backtest, then aggregate to portfolio level
    bt_vix = merge_vix_to_backtest(bt, vix)
    agg = aggregate_pnl(bt_vix)

    # Re-merge VIX onto aggregated series (agg lost the vix column)
    agg = pd.merge_asof(agg.sort_values("timestamp"),
                        vix.sort_values("timestamp"),
                        on="timestamp", direction="backward")

    print(f"Portfolio-level periods: {len(agg)}")
    print(f"VIX coverage: {agg['vix'].notna().sum()} / {len(agg)} "
          f"({agg['vix'].notna().mean()*100:.1f}%)")
    print(f"VIX > {VIX_THRESHOLD}: {(agg['vix'] > VIX_THRESHOLD).sum()} periods "
          f"({(agg['vix'] > VIX_THRESHOLD).mean()*100:.1f}%)")

    # --- Define regime slices ---
    pre = agg[agg["timestamp"] < SPLIT_DATE]
    post = agg[agg["timestamp"] >= SPLIT_DATE]
    low_vix = agg[agg["vix"] <= VIX_THRESHOLD]
    high_vix = agg[agg["vix"] > VIX_THRESHOLD]

    # Cross regimes (2x2)
    pre_low = agg[(agg["timestamp"] < SPLIT_DATE) & (agg["vix"] <= VIX_THRESHOLD)]
    pre_high = agg[(agg["timestamp"] < SPLIT_DATE) & (agg["vix"] > VIX_THRESHOLD)]
    post_low = agg[(agg["timestamp"] >= SPLIT_DATE) & (agg["vix"] <= VIX_THRESHOLD)]
    post_high = agg[(agg["timestamp"] >= SPLIT_DATE) & (agg["vix"] > VIX_THRESHOLD)]

    slices = [
        (agg, "Full Sample"),
        (pre, "Pre-2021"),
        (post, "Post-2021"),
        (low_vix, f"VIX <= {VIX_THRESHOLD}"),
        (high_vix, f"VIX > {VIX_THRESHOLD}"),
        (pre_low, f"Pre-2021 & VIX <= {VIX_THRESHOLD}"),
        (pre_high, f"Pre-2021 & VIX > {VIX_THRESHOLD}"),
        (post_low, f"Post-2021 & VIX <= {VIX_THRESHOLD}"),
        (post_high, f"Post-2021 & VIX > {VIX_THRESHOLD}"),
    ]

    rows = []
    for data, label in slices:
        m = regime_metrics(data, label)
        if m is not None:
            rows.append(m)

    results = pd.DataFrame(rows)

    # Reorder columns for readability
    col_order = ["regime", "sharpe", "total_bps", "annual_bps", "max_dd_bps",
                 "max_dd_days", "win_rate", "active_periods", "pct_time_in_carry",
                 "n_periods", "years", "mean_turnover",
                 "funding_bps", "cost_bps", "basis_bps"]
    results = results[col_order]

    # --- Print results ---
    print("\n" + "=" * 80)
    print("  REGIME ANALYSIS — Baseline Carry (threshold=0.01%, spread=5bps)")
    print("=" * 80)

    for _, r in results.iterrows():
        print(f"\n--- {r['regime']} ---")
        print(f"  Periods: {r['n_periods']:.0f} ({r['years']:.1f} yrs)")
        print(f"  Sharpe:  {r['sharpe']:.3f}")
        print(f"  Return:  {r['total_bps']:.1f} bps total, {r['annual_bps']:.1f} bps/yr")
        print(f"  Max DD:  {r['max_dd_bps']:.1f} bps ({r['max_dd_days']:.0f} days)")
        print(f"  Win rate: {r['win_rate']:.1%}")
        print(f"  In carry: {r['pct_time_in_carry']:.1%} of periods ({r['active_periods']:.0f} active)")
        print(f"  P&L: +{r['funding_bps']:.0f} funding, {r['cost_bps']:.0f} cost, "
              f"{r['basis_bps']:+.0f} basis")

    # --- Conditional performance summary ---
    print("\n" + "=" * 80)
    print("  CONDITIONAL PERFORMANCE COMPARISON")
    print("=" * 80)

    def _get(label):
        return results[results["regime"] == label].iloc[0]

    full = _get("Full Sample")
    pre_m = _get("Pre-2021")
    post_m = _get("Post-2021")
    low_m = _get(f"VIX <= {VIX_THRESHOLD}")
    high_m = _get(f"VIX > {VIX_THRESHOLD}")

    print(f"\n  Structural break (pre vs post 2021):")
    print(f"    Pre-2021 Sharpe:  {pre_m['sharpe']:.3f}  ({pre_m['annual_bps']:.1f} bps/yr)")
    print(f"    Post-2021 Sharpe: {post_m['sharpe']:.3f}  ({post_m['annual_bps']:.1f} bps/yr)")
    print(f"    Delta Sharpe:     {post_m['sharpe'] - pre_m['sharpe']:+.3f}")

    print(f"\n  VIX regime:")
    print(f"    Low VIX Sharpe:   {low_m['sharpe']:.3f}  ({low_m['annual_bps']:.1f} bps/yr)")
    print(f"    High VIX Sharpe:  {high_m['sharpe']:.3f}  ({high_m['annual_bps']:.1f} bps/yr)")
    print(f"    Delta Sharpe:     {high_m['sharpe'] - low_m['sharpe']:+.3f}")

    print(f"\n  2x2 Sharpe grid:")
    print(f"    {'':>20s}  {'VIX<=25':>8s}  {'VIX>25':>8s}")
    pl = _get(f"Pre-2021 & VIX <= {VIX_THRESHOLD}")
    ph = _get(f"Pre-2021 & VIX > {VIX_THRESHOLD}")
    ol = _get(f"Post-2021 & VIX <= {VIX_THRESHOLD}")
    oh = _get(f"Post-2021 & VIX > {VIX_THRESHOLD}")
    print(f"    {'Pre-2021':>20s}  {pl['sharpe']:>8.3f}  {ph['sharpe']:>8.3f}")
    print(f"    {'Post-2021':>20s}  {ol['sharpe']:>8.3f}  {oh['sharpe']:>8.3f}")

    # --- Save output ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_path = os.path.join(OUTPUT_DIR, "regime_analysis.csv")
    results.to_csv(out_path, index=False)
    print(f"\nSaved {len(results)} regime rows to {out_path}")


if __name__ == "__main__":
    main()
