import numpy as np
import pandas as pd

def rsi(close, length=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def macd(close, fast=12, slow=26, signal=9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return line, sig, hist

def atr(df, length=10):
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def supertrend(df, length=10, multiplier=3.0):
    a = atr(df, length)
    hl2 = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * a
    lower = hl2 - multiplier * a

    final_upper = upper.copy()
    final_lower = lower.copy()
    direction = pd.Series(1, index=df.index, dtype=float)
    st = pd.Series(index=df.index, dtype=float)

    for i in range(1, len(df)):
        if upper.iloc[i] < final_upper.iloc[i-1] or df["close"].iloc[i-1] > final_upper.iloc[i-1]:
            final_upper.iloc[i] = upper.iloc[i]
        else:
            final_upper.iloc[i] = final_upper.iloc[i-1]

        if lower.iloc[i] > final_lower.iloc[i-1] or df["close"].iloc[i-1] < final_lower.iloc[i-1]:
            final_lower.iloc[i] = lower.iloc[i]
        else:
            final_lower.iloc[i] = final_lower.iloc[i-1]

        if direction.iloc[i-1] == -1 and df["close"].iloc[i] > final_upper.iloc[i-1]:
            direction.iloc[i] = 1
        elif direction.iloc[i-1] == 1 and df["close"].iloc[i] < final_lower.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]

        st.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]

    st.iloc[0] = lower.iloc[0]
    return st, direction

def build_signal(df, rsi_limit=30, volume_multiple=1.5):
    if len(df) < 60:
        return None

    x = df.copy()
    x["RSI"] = rsi(x["close"])
    x["MACD"], x["MACD_SIGNAL"], x["MACD_HIST"] = macd(x["close"])
    x["ATR"] = atr(x)
    x["ST"], x["ST_DIR"] = supertrend(x)
    x["VOL_AVG20"] = x["volume"].rolling(20).mean()
    x["VOL_RATIO"] = x["volume"] / x["VOL_AVG20"]

    last = x.iloc[-1]
    prev = x.iloc[-2]

    # "Fresh" = bullish MACD crossover occurred on the latest completed candle.
    fresh_macd_cross = (
        prev["MACD"] <= prev["MACD_SIGNAL"]
        and last["MACD"] > last["MACD_SIGNAL"]
    )

    oversold = last["RSI"] < rsi_limit
    high_volume = last["VOL_RATIO"] >= volume_multiple
    above_supertrend = last["close"] > last["ST"]

    if not (oversold and fresh_macd_cross and high_volume and above_supertrend):
        return None

    entry = float(last["close"])
    stop = float(last["ST"])
    risk = max(entry - stop, entry * 0.01)
    target = entry + 2.0 * risk

    score = (
        min(35, max(0, (rsi_limit - last["RSI"]) * 2.0))
        + 30
        + min(20, max(0, (last["VOL_RATIO"] - volume_multiple) * 10))
        + min(15, max(0, (entry / stop - 1) * 100))
    )

    return {
        "SIGNAL": "LONG",
        "PRICE": entry,
        "RSI": float(last["RSI"]),
        "MACD_HIST": float(last["MACD_HIST"]),
        "VOLUME_RATIO": float(last["VOL_RATIO"]),
        "SUPERTREND": stop,
        "DIST_ST_%": float((entry / stop - 1) * 100),
        "SCORE": float(score),
        "ENTRY": entry,
        "STOP": stop,
        "TARGET": target,
        "ST_SERIES": x["ST"],
    }
