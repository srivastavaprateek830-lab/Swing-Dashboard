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
    df = pd.read_csv(CACHE, low_memory=False)

    # Dhan's detailed master uses NSE/D/E for NSE derivatives and
    # NSE/E for NSE equity. Use UNDERLYING_SECURITY_ID rather than matching
    # symbol strings; this is much more robust.
    return df

def load_fno_universe():
    df = load_master()

    required = {"EXCH_ID","SEGMENT","SECURITY_ID","INSTRUMENT"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Dhan instrument master missing columns: {sorted(missing)}")

    nse_fno = df[
        (df["EXCH_ID"].astype(str).str.upper() == "NSE") &
        (df["SEGMENT"].astype(str).str.upper() == "D")
    ].copy()

    # Stock F&O underlyings have an UNDERLYING_SECURITY_ID. Index derivatives
    # such as NIFTY/BANKNIFTY do not map to an NSE_EQ stock and are excluded.
    underlying_ids = set(
        nse_fno["UNDERLYING_SECURITY_ID"]
        .dropna()
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
    )

    eq = df[
        (df["EXCH_ID"].astype(str).str.upper() == "NSE") &
        (df["SEGMENT"].astype(str).str.upper() == "E")
    ].copy()

    eq_ids = eq["SECURITY_ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    eq = eq[eq_ids.isin(underlying_ids)].copy()

    # Keep equity instruments only where possible; exclude ETFs, indices, etc.
    if "INSTRUMENT" in eq.columns:
        eq = eq[eq["INSTRUMENT"].astype(str).str.upper().eq("EQUITY")]

    name_col = "SYMBOL_NAME" if "SYMBOL_NAME" in eq.columns else "DISPLAY_NAME"
    eq["symbol"] = eq[name_col].astype(str).str.upper().str.strip()
    eq["security_id"] = eq["SECURITY_ID"].astype(str).str.replace(r"\.0$", "", regex=True)

    eq = eq.drop_duplicates("security_id").sort_values("symbol")

    return [
        {"symbol": row["symbol"], "security_id": row["security_id"]}
        for _, row in eq.iterrows()
        if row["symbol"] not in ("NAN", "") and row["security_id"] not in ("NAN", "")
    ]
