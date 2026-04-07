# ABOUTME: Constructs baseline carry signal from funding rates and computes realized vol for position sizing.
# ABOUTME: Outputs data/signals.parquet — run: python3 src/2_signal.py

import os

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
SYMBOLS = {"BTCUSDT": "btc", "ETHUSDT": "eth"}

# Default threshold: 0.01% per 8h funding period
DEFAULT_THRESHOLD = 0.0001

# Realized vol: rolling window of hourly log returns (30 days = 720 hours)
VOL_WINDOW_HOURS = 30 * 24


def load_parquet(filename):
    return pd.read_parquet(os.path.join(DATA_DIR, filename))


def compute_realized_vol(klines):
    """Annualized 30-day realized vol from hourly spot log returns."""
    klines = klines.sort_values("timestamp")
    log_ret = np.log(klines["close"] / klines["close"].shift(1))
    vol = log_ret.rolling(VOL_WINDOW_HOURS, min_periods=VOL_WINDOW_HOURS // 2).std() * np.sqrt(8760)
    return pd.DataFrame({"timestamp": klines["timestamp"], "realized_vol_30d": vol.values})


def build_signal(prefix, threshold=DEFAULT_THRESHOLD):
    """Build carry signal for one asset at 8h frequency.

    Returns DataFrame with columns:
        timestamp, symbol, funding_rate, realized_vol_30d, signal
    """
    funding = load_parquet(f"{prefix}_funding_rates.parquet").sort_values("timestamp")
    klines = load_parquet(f"{prefix}_spot_klines.parquet")

    vol = compute_realized_vol(klines).dropna(subset=["realized_vol_30d"]).sort_values("timestamp")

    # Asof join: for each funding timestamp, grab the most recent vol reading
    merged = pd.merge_asof(funding, vol, on="timestamp", direction="backward")

    # Signal: 1 = in carry (collect funding), 0 = out
    # Binance publishes indicative funding rate before settlement, so using
    # the concurrent rate is not look-ahead — it's observable pre-settlement.
    merged["signal"] = (merged["funding_rate"] > threshold).astype(int)
    merged["symbol"] = prefix.upper()

    return merged[["timestamp", "symbol", "funding_rate", "realized_vol_30d", "signal"]]


def print_threshold_sensitivity(signals):
    """Print % of time in carry across threshold levels and assets."""
    thresholds = [0.0, 0.00005, 0.0001, 0.00015, 0.0002, 0.0003, 0.0005]
    print("\nThreshold sensitivity (% of time in carry):")
    header = f"  {'threshold':>12s}"
    for prefix in SYMBOLS.values():
        header += f"  {prefix.upper():>6s}"
    print(header)
    for t in thresholds:
        row = f"  {t*100:>11.4f}%"
        for prefix in SYMBOLS.values():
            sub = signals[signals["symbol"] == prefix.upper()]
            pct = (sub["funding_rate"] > t).mean() * 100
            row += f"  {pct:>5.1f}%"
        print(row)


def main():
    frames = []
    for symbol, prefix in SYMBOLS.items():
        print(f"Building signal for {symbol}...")
        df = build_signal(prefix)
        frames.append(df)

        n = len(df)
        on = df["signal"].sum()
        print(f"  {n} periods, signal on {on}/{n} ({on/n*100:.1f}%)")
        print(f"  Funding: mean={df['funding_rate'].mean()*100:.4f}%  "
              f"median={df['funding_rate'].median()*100:.4f}%")
        vol = df["realized_vol_30d"].dropna()
        print(f"  Vol (30d ann): mean={vol.mean():.3f}  median={vol.median():.3f}")

    signals = pd.concat(frames, ignore_index=True)
    print_threshold_sensitivity(signals)

    out_path = os.path.join(DATA_DIR, "signals.parquet")
    signals.to_parquet(out_path, index=False)
    print(f"\nSaved {len(signals)} rows to {out_path}")


if __name__ == "__main__":
    main()
