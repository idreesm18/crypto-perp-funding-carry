# ABOUTME: Builds position weights (inverse-vol sizing) and trade costs from signals.
# ABOUTME: Outputs data/portfolio.parquet — run: python3 src/3_portfolio.py

import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

DEFAULT_THRESHOLD = 0.0001  # 0.01% per 8h (same as 2_signal.py)
SPREAD_BPS = 5  # half-spread per instrument per trade direction (conservative)


def load_signals():
    return pd.read_parquet(os.path.join(DATA_DIR, "signals.parquet"))


def build_portfolio(signals=None, threshold=DEFAULT_THRESHOLD, spread_bps=SPREAD_BPS):
    """Build portfolio weights and costs from signals.

    Position sizing: inverse of 30d realized vol, normalized across assets so
    weights sum to 1.  When signal is off for an asset its weight is 0.

    Cost model: fixed half-spread applied to both legs (spot + perp) for each
    unit of turnover.  Cost per unit turnover = 2 * spread_bps / 10_000.

    Args:
        signals: DataFrame with [timestamp, symbol, funding_rate, realized_vol_30d].
                 Loads from data/signals.parquet if None.
        threshold: Funding rate threshold for carry entry.
        spread_bps: Half-spread per instrument per trade direction.

    Returns:
        DataFrame: timestamp, symbol, funding_rate, realized_vol_30d,
                   signal, weight, turnover, cost
    """
    if signals is None:
        signals = load_signals()

    df = signals.dropna(subset=["realized_vol_30d"]).copy()

    # (Re-)apply threshold so backtest can call with different values
    df["signal"] = (df["funding_rate"] > threshold).astype(int)

    # Inverse-vol raw weight, zero when signal off
    df["raw_weight"] = np.where(df["signal"] == 1, 1.0 / df["realized_vol_30d"], 0.0)

    # Normalize per timestamp so active weights sum to 1
    total = df.groupby("timestamp")["raw_weight"].transform("sum")
    df["weight"] = np.where(total > 0, df["raw_weight"] / total, 0.0)

    # Turnover: |delta weight| from prior period per asset
    df = df.sort_values(["symbol", "timestamp"])
    prev = df.groupby("symbol")["weight"].shift(1).fillna(0.0)
    df["turnover"] = (df["weight"] - prev).abs()

    # Cost: spread on both legs (spot + perp) per unit of turnover
    df["cost"] = df["turnover"] * (2 * spread_bps / 10_000)

    cols = ["timestamp", "symbol", "funding_rate", "realized_vol_30d",
            "signal", "weight", "turnover", "cost"]
    return df[cols].sort_values(["timestamp", "symbol"]).reset_index(drop=True)


def print_summary(df):
    """Print per-asset and portfolio-level summary."""
    for sym in sorted(df["symbol"].unique()):
        sub = df[df["symbol"] == sym]
        n = len(sub)
        active = (sub["weight"] > 0).sum()
        mean_w = sub.loc[sub["weight"] > 0, "weight"].mean() if active > 0 else 0
        total_cost = sub["cost"].sum() * 10_000
        trade_periods = (sub["turnover"] > 0).sum()
        print(f"\n{sym}:")
        print(f"  {n} periods, active {active}/{n} ({active/n*100:.1f}%)")
        print(f"  Mean weight when active: {mean_w:.3f}")
        print(f"  Trade events: {trade_periods}")
        print(f"  Total cost: {total_cost:.1f} bps")

    per_ts = df.groupby("timestamp").agg({"cost": "sum", "turnover": "sum"})
    print(f"\nPortfolio:")
    print(f"  Mean period turnover: {per_ts['turnover'].mean():.4f}")
    print(f"  Mean period cost: {per_ts['cost'].mean()*10_000:.2f} bps")
    print(f"  Cumulative cost: {per_ts['cost'].sum()*10_000:.1f} bps")


def main():
    signals = load_signals()
    n_null = signals["realized_vol_30d"].isna().sum()
    print(f"Loaded {len(signals)} signal rows, dropping {n_null} null-vol warm-up rows")

    df = build_portfolio(signals)
    print(f"Portfolio: {len(df)} rows")
    print_summary(df)

    # Threshold sensitivity
    print("\n\nThreshold sensitivity (% time active, cumulative cost):")
    print(f"  {'threshold':>12s}  {'pct_on':>7s}  {'cost_bps':>9s}")
    for t in [0.0, 0.00005, 0.0001, 0.00015, 0.0002, 0.0003, 0.0005]:
        p = build_portfolio(signals, threshold=t)
        pct = (p["weight"] > 0).mean() * 100
        cost = p["cost"].sum() * 10_000
        print(f"  {t*100:>11.4f}%  {pct:>6.1f}%  {cost:>8.1f}")

    # Spread sensitivity at default threshold
    print("\nSpread sensitivity (total cost at default threshold):")
    print(f"  {'bps/side':>8s}  {'cost_bps':>9s}")
    for bps in [1, 2, 3, 5, 7, 10]:
        p = build_portfolio(signals, spread_bps=bps)
        cost = p["cost"].sum() * 10_000
        print(f"  {bps:>8d}  {cost:>8.1f}")

    out_path = os.path.join(DATA_DIR, "portfolio.parquet")
    df.to_parquet(out_path, index=False)
    print(f"\nSaved {len(df)} rows to {out_path}")


if __name__ == "__main__":
    main()
