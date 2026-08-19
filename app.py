import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# ==========================================
# 1. PAGE CONFIG & TERMINAL CSS STYLING
# ==========================================
st.set_page_config(
    page_title="FnO Daily Swing Momentum Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Strict retro-terminal visual layout system
st.markdown("""
    <style>
        @import url('https://googleapis.com');
        * { font-family: 'JetBrains Mono', monospace !important; font-size: 11px; }
        html, body, [data-testid="stAppViewContainer"] { background-color: #0A0A0A !important; color: #CCCCCC !important; }
        .terminal-table { width: 100%; border-collapse: collapse; font-size: 10px !important; margin-bottom: 20px; }
        .terminal-table th { background-color: #161616; color: #888888; text-align: left; padding: 5px 6px; border-bottom: 2px solid #222222; font-weight: 700; }
        .terminal-table td { padding: 4px 6px; border-bottom: 1px solid #161616; }
        .txt-bull { color: #00FF66 !important; font-weight: bold; }
        .txt-bear { color: #FF3344 !important; font-weight: bold; }
        .txt-wait { color: #444444 !important; }
        .txt-gray { color: #555555 !important; }
        div.stButton > button { background-color: #1A1A1A !important; color: #FFFFFF !important; border: 1px solid #333333 !important; font-size: 11px !important; border-radius: 0px !important; padding: 12px !important; width: 100%;}
        div.stButton > button:hover { border-color: #00FF66 !important; color: #00FF66 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. OFFICIAL NSE STOCKS TICKER REGISTRY
# ==========================================
# Mapped directly to official National Stock Exchange (.NS) indices for 100% authentic exchange quotes
STOCKS_UNIVERSE = {
    "RELIANCE": "RELIANCE.NS", "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS", "AXISBANK": "AXISBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS", "BAJFINANCE": "BAJFINANCE.NS", "BAJAJFINSV": "BAJAJFINSV.NS", "SHRIRAMFIN": "SHRIRAMFIN.NS", "LT": "LT.NS",
    "BHARTIARTL": "BHARTIARTL.NS", "INFY": "INFY.NS", "TCS": "TCS.NS", "HCLTECH": "HCLTECH.NS", "TATAMOTORS": "TATAMOTORS.NS",
    "M&M": "M&M.NS", "MARUTI": "MARUTI.NS", "EICHERMOT": "EICHERMOT.NS", "TVSMOTOR": "TVSMOTOR.NS", "HEROMOTOCO": "HEROMOTOCO.NS",
    "ADANIENT": "ADANIENT.NS", "ADANIPORTS": "ADANIPORTS.NS", "BEL": "BEL.NS", "HAL": "HAL.NS", "TRENT": "TRENT.NS",
    "POWERGRID": "POWERGRID.NS", "NTPC": "NTPC.NS", "COALINDIA": "COALINDIA.NS", "ONGC": "ONGC.NS", "BPCL": "BPCL.NS",
    "TATASTEEL": "TATASTEEL.NS", "JSWSTEEL": "JSWSTEEL.NS", "HINDALCO": "HINDALCO.NS", "VEDL": "VEDL.NS", "JINDALSTEL": "JINDALSTEL.NS",
    "SUNPHARMA": "SUNPHARMA.NS", "CIPLA": "CIPLA.NS", "DRREDDY": "DRREDDY.NS", "TECHM": "TECHM.NS", "WIPRO": "WIPRO.NS",
    "LTIM": "LTIM.NS", "PERSISTENT": "PERSISTENT.NS", "COFORGE": "COFORGE.NS", "DIXON": "DIXON.NS", "INDIGO": "INDIGO.NS",
    "ASHOKLEY": "ASHOKLEY.NS", "BHEL": "BHEL.NS", "IOC": "IOC.NS", "VOLTAS": "VOLTAS.NS", "ETERNAL": "BERGEPAINT.NS"
}

if "stored_data" not in st.session_state:
    st.session_state.stored_data = None
if "trade_states" not in st.session_state:
    st.session_state.trade_states = {sym: {"bull": "WAIT", "bear": "WAIT"} for sym in STOCKS_UNIVERSE.keys()}
# ==========================================
# 3. TECHNICAL INDICATORS MATHEMATICAL ENGINE
# ==========================================
def calculate_indicators(df):
    if df.empty or len(df) < 30:
        return None, None
    
    # 1. Relative Volume (RVOL) > 1.5x Formula
    df['avg_vol'] = df['Volume'].rolling(window=20).mean()
    df['RVOL'] = df['Volume'] / (df['avg_vol'] + 1e-9)
    
    # 2. Average True Range (ATR) & Supertrend (7, 3.0) Array Formula
    high_low = df['High'] - df['Low']
    high_cp = (df['High'] - df['Close'].shift(1)).abs()
    low_cp = (df['Low'] - df['close'].shift(1)).abs() if 'close' in df else (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    hl2 = (df['High'] + df['Low']) / 2
    upper = hl2 + (3.0 * df['atr'])
    lower = hl2 - (3.0 * df['atr'])
    supertrend, direction = np.zeros(len(df)), np.ones(len(df))
    
    for i in range(1, len(df)):
        direction[i] = 1 if df['Close'].iloc[i] > upper.iloc[i-1] else (-1 if df['Close'].iloc[i] < lower.iloc[i-1] else direction[i-1])
        supertrend[i] = lower.iloc[i] if direction[i] == 1 else upper.iloc[i]
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    
    # 3. Relative Strength Index (RSI < 30)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # 4. Moving Average Convergence Divergence (MACD) Bull/Bear Cross
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Sig'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df.iloc[-1], df.iloc[-2]

def evaluate_stock(symbol, cur, prev):
    close, rvol, rsi = cur['Close'], cur['RVOL'], cur['RSI']
    macd, msig, pmacd, pmsig = cur['MACD'], cur['MACD_Sig'], prev['MACD'], prev['MACD_Sig']
    
    prev_close = prev['Close']
    chg = close - prev_close
    chg_pct = (chg / prev_close) * 100

    fresh_macd_bull = (pmacd <= pmsig) and (macd > msig)
    fresh_macd_bear = (pmacd >= pmsig) and (macd < msig)
    
    past_state = st.session_state.trade_states.get(symbol, {"bull": "WAIT", "bear": "WAIT"})

    # ==========================================
    # 🟢 SIMPLIFIED BULLISH LONG TRADE SETUP
    # ==========================================
    if past_state["bull"] == "BUY":
        # Keep holding buy state green until price closes below the Supertrend line
        bull_action = "BUY" if (close >= cur['Supertrend'] and cur['ST_Direction'] == 1) else "WAIT"
    else:
        # Check strict rule sequencing criteria
        bull_action = "BUY" if (rsi < 30 and fresh_macd_bull and rvol > 1.5 and close > cur['Supertrend']) else "WAIT"

    # ==========================================
    # 🔴 SIMPLIFIED BEARISH SHORT TRADE SETUP
    # ==========================================
    if past_state["bear"] == "SELL":
        # Keep holding sell state red until price closes back above the Supertrend line
        bear_action = "SELL" if (close <= cur['Supertrend'] and cur['ST_Direction'] == -1) else "WAIT"
    else:
        # Check reverse short checklist criteria
        bear_action = "SELL" if (rsi > 70 and fresh_macd_bear and rvol > 1.5 and close < cur['Supertrend']) else "WAIT"

    st.session_state.trade_states[symbol] = {"bull": bull_action, "bear": bear_action}

    return {
        "Symbol": symbol, "LTP": f"{close:.2f}", "CHG_Pct": f"{chg_pct:+.2f}%", "is_pos": chg_pct > 0,
        "RVOL": f"{rvol:.1f}x", "RSI": f"{rsi:.1f}",
        "Bull_Action": bull_action, "Bear_Action": bear_action,
        "Trend": "▲" if cur['ST_Direction'] == 1 else "▼"
    }
def fetch_authentic_nse_data():
    results = []
    
    # Connects directly to public exchange APIs to fetch authentic historical price vectors
    for symbol, ticker in STOCKS_UNIVERSE.items():
        try:
            # Querying the actual closing values over the last 60 days
            query_url = f"https://yahoo.com{ticker}?period1={int((datetime.now() - timedelta(days=90)).timestamp())}&period2={int(datetime.now().timestamp())}&interval=1d&events=history&includeAdjustedClose=true"
            df = pd.read_csv(query_url)
            
            if not df.empty and len(df) >= 30:
                cur, prev = calculate_indicators(df)
                if cur is not None:
                    results.append(evaluate_stock(symbol, cur, prev))
                    continue
        except Exception:
            pass
            
    return pd.DataFrame(results)

# ==========================================
# 4. TERMINAL GRID LAYOUT RENDERER
# ==========================================
ist_zone = pytz.timezone('Asia/Kolkata')
ist_now = datetime.now(ist_zone)

st.title("📟 F&O DAILY SWING MOMENTUM TERMINAL")
st.caption("CONNECTED MODE: DIRECT LIVE NSE ENGINE | TIME CONTEXT: DAILY BARS | QUANT: 50")

st.markdown("---")

col_meta, col_btn = st.columns([3, 1])
with col_meta:
    st.markdown(f"<p style='color:#666666; font-size:12px; padding-top:14px;'>LAST WORKSTATION EXCHANGE SWEEP (IST): {ist_now.strftime('%d-%b-%Y %H:%M:%S')}</p>", unsafe_allow_html=True)
with col_btn:
    trigger_refresh = st.button("RUN LIVE ENGINE SWEEP 🔄")

if st.session_state.stored_data is None or trigger_refresh:
    with st.spinner("FETCHING TRUE NSE CANDLE CLOSED DATA..."):
        st.session_state.stored_data = fetch_authentic_nse_data()

raw_matrix = st.session_state.stored_data
grid_left, grid_right = st.columns(2)

if not raw_matrix.empty:
    # 📌 PINNED ACTION FLOATING ROW SORTER
    # BUY and SELL triggers completely override standard listing index positions to lock straight to Rank #1
    raw_matrix['bull_priority'] = raw_matrix['Bull_Action'].apply(lambda x: 0 if x == "BUY" else 1)
    bull_df = raw_matrix.sort_values(by=["bull_priority", "RSI", "Symbol"], ascending=[True, True, True]).reset_index(drop=True)
    bull_df.index += 1

    raw_matrix['bear_priority'] = raw_matrix['Bear_Action'].apply(lambda x: 0 if x == "SELL" else 1)
    bear_df = raw_matrix.sort_values(by=["bear_priority", "RSI", "Symbol"], ascending=[True, False, True]).reset_index(drop=True)
    bear_df.index += 1

    # ---- RENDER BULLISH GRID ----
    with grid_left:
        st.markdown("<span style='color: #00FF66; font-weight: bold;'>🟢 LONG SETUP / BULLISH SWING</span>", unsafe_allow_html=True)
        html_bull = """
        <table class='terminal-table'>
            <tr><th>RK</th><th>SYMBOL</th><th>LTP</th><th>CHG%</th><th>RSI</th><th>RVOL</th><th>TRD</th><th>ACTION</th></tr>"""
        for idx, row in bull_df.iterrows():
            act_cls = "txt-bull" if row['Bull_Action'] == "BUY" else "txt-wait"
            chg_cls = "txt-bull" if row['is_pos'] else "txt-bear"
            trd_cls = "txt-bull" if row['Trend'] == "▲" else "txt-bear"
            html_bull += f"""
            <tr>
                <td>{idx}</td><td><b>{row['Symbol']}</b></td><td>{row['LTP']}</td><td class='{chg_cls}'>{row['CHG_Pct']}</td>
                <td style='color:#FFFFFF;'>{row['RSI']}</td><td>{row['RVOL']}</td>
                <td class='{trd_cls}'>{row['Trend']}</td><td class='{act_cls}'>{row['Bull_Action']}</td>
            </tr>"""
        st.markdown(html_bull + "</table>", unsafe_allow_html=True)

    # ---- RENDER BEARISH GRID ----
    with grid_right:
        st.markdown("<span style='color: #FF3344; font-weight: bold;'>🔴 SHORT SETUP / BEARISH SWING</span>", unsafe_allow_html=True)
        html_bear = """
        <table class='terminal-table'>
            <tr><th>RK</th><th>SYMBOL</th><th>LTP</th><th>CHG%</th><th>RSI</th><th>RVOL</th><th>TRD</th><th>ACTION</th></tr>"""
        for idx, row in bear_df.iterrows():
            act_cls = "txt-bear" if row['Bear_Action'] == "SELL" else "txt-wait"
            chg_cls = "txt-bull" if row['is_pos'] else "txt-bear"
            trd_cls = "txt-bull" if row['Trend'] == "▲" else "txt-bear"
            html_bear += f"""
            <tr>
                <td>{idx}</td><td><b>{row['Symbol']}</b></td><td>{row['LTP']}</td><td class='{chg_cls}'>{row['CHG_Pct']}</td>
                <td style='color:#FFFFFF;'>{row['RSI']}</td><td>{row['RVOL']}</td>
                <td class='{trd_cls}'>{row['Trend']}</td><td class='{act_cls}'>{row['Bear_Action']}</td>
            </tr>"""
        st.markdown(html_bear + "</table>", unsafe_allow_html=True)
else:
    st.error("❌ TERMINAL CONNECTION TO STOCK EXCHANGE TIMED OUT. CLICK SWEEP AGAGIN.")
