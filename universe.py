from pathlib import Path
import pandas as pd
import requests

MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
CACHE = Path("data/dhan_scrip_master.csv")

def _download_master():
    r = requests.get(MASTER_URL, timeout=40)
    r.raise_for_status()
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_bytes(r.content)

def load_master():
    if not CACHE.exists():
        _download_master()
    try:
        df = pd.read_csv(CACHE, low_memory=False)
        if len(df) < 1000:
            _download_master()
            df = pd.read_csv(CACHE, low_memory=False)
        return df
    except Exception:
        _download_master()
        return pd.read_csv(CACHE, low_memory=False)

def load_fno_universe():
    df = load_master()

    # Derive F&O underlyings from current NSE_FNO instruments.
    fno = df[
        (df["EXCH_ID"].astype(str) == "NSE") &
        (df["SEGMENT"].astype(str) == "D")
    ].copy()

    symbols = set(
        fno["UNDERLYING_SYMBOL"].dropna().astype(str).str.upper().str.strip()
    )

    eq = df[
        (df["EXCH_ID"].astype(str) == "NSE") &
        (df["SEGMENT"].astype(str) == "E") &
        (df["INSTRUMENT"].astype(str).str.upper() == "EQUITY")
    ].copy()

    eq["symbol_key"] = eq["SYMBOL_NAME"].astype(str).str.upper().str.strip()
    eq = eq[eq["symbol_key"].isin(symbols)].copy()

    # Prefer one cash equity security ID per underlying.
    eq = eq.drop_duplicates("symbol_key")

    return [
        {
            "symbol": row["symbol_key"],
            "security_id": str(row["SECURITY_ID"]),
        }
        for _, row in eq.iterrows()
        if str(row["SECURITY_ID"]).strip() not in ("", "nan")
    ]
