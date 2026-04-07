# ABOUTME: Pulls raw market data from Binance bulk downloads (data.binance.vision) and VIX from FRED.
# ABOUTME: Outputs parquet files to data/ — run: python3 src/1_data_pull.py

import io
import os
import time
import zipfile
from datetime import datetime, timezone, timedelta

import pandas as pd
import requests

SYMBOLS = ["BTCUSDT", "ETHUSDT"]
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

BULK_BASE = "https://data.binance.vision/data"

# Binance perp funding starts 2020-01; spot klines go back further but we align to perp start
FUNDING_START = (2020, 1)
KLINE_START = (2020, 1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_zip_csv(url, names=None):
    """Download a zip from data.binance.vision, extract the CSV, return DataFrame.
    If names is provided, read as headerless CSV with those column names.
    If first row looks like a header, it will be used automatically.
    """
    resp = requests.get(url, timeout=60)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    try:
        z = zipfile.ZipFile(io.BytesIO(resp.content))
    except zipfile.BadZipFile:
        return None
    csv_name = z.namelist()[0]
    with z.open(csv_name) as f:
        raw = f.read().decode()
    time.sleep(0.05)  # light pacing

    # Detect whether first row is a header (starts with a letter) or data (starts with digit)
    first_char = raw.lstrip()[0] if raw.strip() else ""
    if names and first_char.isdigit():
        # Headerless CSV — assign column names
        df = pd.read_csv(io.StringIO(raw), header=None, names=names)
    else:
        # Has a header row
        df = pd.read_csv(io.StringIO(raw))
    return df


def _month_range(start_year, start_month):
    """Yield (year, month) tuples from start to current month (inclusive)."""
    now = datetime.now(timezone.utc)
    y, m = start_year, start_month
    while (y, m) <= (now.year, now.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


# ---------------------------------------------------------------------------
# Funding rates — monthly bulk zips
# ---------------------------------------------------------------------------

def fetch_funding_rates(symbol):
    """Download monthly funding rate CSVs and concatenate."""
    frames = []
    for y, m in _month_range(*FUNDING_START):
        url = f"{BULK_BASE}/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{y}-{m:02d}.zip"
        df = _download_zip_csv(url)
        if df is None:
            continue
        frames.append(df)
        print(f"    {y}-{m:02d}: {len(df)} rows")

    if not frames:
        raise RuntimeError(f"No funding rate data found for {symbol}")

    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["calc_time"], unit="ms", utc=True)
    df["funding_rate"] = df["last_funding_rate"].astype(float)
    return df[["timestamp", "funding_rate"]]


# ---------------------------------------------------------------------------
# Klines — monthly bulk zips (shared for spot and perp)
# ---------------------------------------------------------------------------

KLINE_COLS = [
    "open_time", "open", "high", "low", "close", "volume",
    "close_time", "quote_volume", "count",
    "taker_buy_base", "taker_buy_quote", "ignore",
]


def _fetch_klines_bulk(symbol, path_prefix):
    """Download monthly 1h kline zips from data.binance.vision."""
    frames = []
    for y, m in _month_range(*KLINE_START):
        url = f"{BULK_BASE}/{path_prefix}/monthly/klines/{symbol}/1h/{symbol}-1h-{y}-{m:02d}.zip"
        df = _download_zip_csv(url, names=KLINE_COLS)
        if df is None:
            continue
        frames.append(df)
        if len(frames) % 12 == 0:
            total = sum(len(f) for f in frames)
            print(f"    ... {total} candles through {y}-{m:02d}")

    if not frames:
        raise RuntimeError(f"No kline data found for {symbol} at {path_prefix}")

    df = pd.concat(frames, ignore_index=True)

    # Binance switched from ms to μs timestamps in 2025 — normalize to ms
    ot = df["open_time"].astype(float)
    ot = ot.where(ot < 1e13, ot / 1000)  # μs -> ms when value >= 1e13
    df["timestamp"] = pd.to_datetime(ot.astype(int), unit="ms", utc=True)

    for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[col] = df[col].astype(float)
    return df[["timestamp", "open", "high", "low", "close", "volume", "quote_volume"]]


def fetch_spot_klines(symbol):
    return _fetch_klines_bulk(symbol, "spot")


def fetch_perp_klines(symbol):
    return _fetch_klines_bulk(symbol, "futures/um")


# ---------------------------------------------------------------------------
# Open interest — daily metrics files (last 90 days)
# ---------------------------------------------------------------------------

def fetch_open_interest(symbol, lookback_days=90):
    """Download daily metrics CSVs for recent open interest history."""
    frames = []
    today = datetime.now(timezone.utc).date()

    for i in range(lookback_days, -1, -1):
        d = today - timedelta(days=i)
        url = (f"{BULK_BASE}/futures/um/daily/metrics/{symbol}/"
               f"{symbol}-metrics-{d.isoformat()}.zip")
        df = _download_zip_csv(url)
        if df is None:
            continue
        frames.append(df)

    if not frames:
        print("    No open interest data returned")
        return pd.DataFrame(columns=["timestamp", "open_interest", "open_interest_value"])

    print(f"    Downloaded {len(frames)} daily files")
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["create_time"], utc=True)
    df["open_interest"] = df["sum_open_interest"].astype(float)
    df["open_interest_value"] = df["sum_open_interest_value"].astype(float)
    return df[["timestamp", "open_interest", "open_interest_value"]]


# ---------------------------------------------------------------------------
# VIX from FRED
# ---------------------------------------------------------------------------

def fetch_vix(max_retries=3):
    """Download VIX daily close from FRED (with retry for flaky server)."""
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=VIXCLS"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), na_values=["."])
            # FRED columns: observation_date, VIXCLS
            df = df.rename(columns={"observation_date": "timestamp", "VIXCLS": "vix"})
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.dropna(subset=["vix"])
            return df
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"    FRED request failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    for symbol in SYMBOLS:
        prefix = symbol.replace("USDT", "").lower()

        print(f"Fetching funding rates for {symbol}...")
        df = fetch_funding_rates(symbol)
        df.to_parquet(os.path.join(DATA_DIR, f"{prefix}_funding_rates.parquet"), index=False)
        print(f"  Saved {len(df)} rows\n")

        print(f"Fetching spot 1h klines for {symbol}...")
        df = fetch_spot_klines(symbol)
        df.to_parquet(os.path.join(DATA_DIR, f"{prefix}_spot_klines.parquet"), index=False)
        print(f"  Saved {len(df)} rows\n")

        print(f"Fetching perp 1h klines for {symbol}...")
        df = fetch_perp_klines(symbol)
        df.to_parquet(os.path.join(DATA_DIR, f"{prefix}_perp_klines.parquet"), index=False)
        print(f"  Saved {len(df)} rows\n")

        print(f"Fetching open interest for {symbol}...")
        df = fetch_open_interest(symbol)
        df.to_parquet(os.path.join(DATA_DIR, f"{prefix}_open_interest.parquet"), index=False)
        print(f"  Saved {len(df)} rows\n")

    print("Fetching VIX from FRED...")
    df = fetch_vix()
    df.to_parquet(os.path.join(DATA_DIR, "vix_daily.parquet"), index=False)
    print(f"  Saved {len(df)} rows\n")

    print("Done.")


if __name__ == "__main__":
    main()
