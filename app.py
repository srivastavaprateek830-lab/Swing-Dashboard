import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz  # Forces synchronization with Indian Standard Time (IST)
from dhanhq import DhanContext, dhanhq  # Official Dhan Connect Gateway components

# ==========================================
# 1. PAGE CONFIG & TERMINAL CSS STYLING
# ==========================================
st.set_page_config(
    page_title="FnO Daily Swing Momentum Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom injection for professional micro monospace typography, deep dark layout, and low cell padding
st.markdown("""
    <style>
        @import url('https://googleapis.com');
        * { font-family: 'JetBrains Mono', monospace !important; font-size: 11px; }
        html, body, [data-testid="stAppViewContainer"] { background-color: #0A0A0A !important; color: #CCCCCC !important; }
        [data-testid="stSidebar"] { background-color: #111111 !important; border-right: 1px solid #222222; }
        .terminal-table { width: 100%; border-collapse: collapse; font-size: 10px !important; margin-bottom: 20px; }
        .terminal-table th { background-color: #161616; color: #888888; text-align: left; padding: 5px 6px; border-bottom: 2px solid #222222; font-weight: 700; }
        .terminal-table td { padding: 4px 6px; border-bottom: 1px solid #161616; }
        .txt-bull { color: #00FF66 !important; font-weight: bold; }
        .txt-bear { color: #FF3344 !important; font-weight: bold; }
        .txt-wait { color: #444444 !important; }
        .txt-gray { color: #555555 !important; }
        div.stButton > button { background-color: #1A1A1A !important; color: #FFFFFF !important; border: 1px solid #333333 !important; font-size: 12px !important; border-radius: 0px !important; padding: 10px !important;}
        div.stButton > button:hover { border-color: #00FF66 !important; color: #00FF66 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INSTRUMENT REGISTRY WITH OFFICIAL DHAN SECURITY IDs
# ==========================================
STOCKS_UNIVERSE = {
    "RELIANCE": {"id": "2885", "sym": "RELIANCE"}, "HDFCBANK": {"id": "1333", "sym": "HDFCBANK"}, 
    "ICICIBANK": {"id": "4963", "sym": "ICICIBANK"}, "SBIN": {"id": "3045", "sym": "SBIN"}, 
    "AXISBANK": {"id": "5900", "sym": "AXISBANK"}, "KOTAKBANK": {"id": "1922", "sym": "KOTAKBANK"}, 
    "BAJFINANCE": {"id": "317", "sym": "BAJFINANCE"}, "BAJAJFINSV": {"id": "16675", "sym": "BAJAJFINSV"}, 
    "SHRIRAMFIN": {"id": "3232", "sym": "SHRIRAMFIN"}, "LT": {"id": "11483", "sym": "LT"}, 
    "BHARTIARTL": {"id": "10604", "sym": "BHARTIARTL"}, "INFY": {"id": "1594", "sym": "INFY"}, 
    "TCS": {"id": "11536", "sym": "TCS"}, "HCLTECH": {"id": "7229", "sym": "HCLTECH"}, 
    "TATAMOTORS": {"id": "3456", "sym": "TATAMOTORS"}, "M&M": {"id": "2031", "sym": "M&M"}, 
    "MARUTI": {"id": "10999", "sym": "MARUTI"}, "EICHERMOT": {"id": "910", "sym": "EICHERMOT"}, 
    "TVSMOTOR": {"id": "8424", "sym": "TVSMOTOR"}, "HEROMOTOCO": {"id": "1348", "sym": "HEROMOTOCO"}, 
    "ADANIENT": {"id": "25", "sym": "ADANIENT"}, "ADANIPORTS": {"id": "15083", "sym": "ADANIPORTS"}, 
    "BEL": {"id": "383", "sym": "BEL"}, "HAL": {"id": "2303", "sym": "HAL"}, 
    "TRENT": {"id": "1964", "sym": "TRENT"}, "POWERGRID": {"id": "14977", "sym": "POWERGRID"}, 
    "NTPC": {"id": "11630", "sym": "NTPC"}, "COALINDIA": {"id": "20374", "sym": "COALINDIA"}, 
    "ONGC": {"id": "2475", "sym": "ONGC"}, "BPCL": {"id": "526", "sym": "BPCL"}, 
    "TATASTEEL": {"id": "3499", "sym": "TATASTEEL"}, "JSWSTEEL": {"id": "11723", "sym": "JSWSTEEL"}, 
    "HINDALCO": {"id": "1363", "sym": "HINDALCO"}, "VEDL": {"id": "3063", "sym": "VEDL"}, 
    "JINDALSTEL": {"id": "6733", "sym": "JINDALSTEL"}, "SUNPHARMA": {"id": "3351", "sym": "SUNPHARMA"}, 
    "CIPLA": {"id": "694", "sym": "CIPLA"}, "DRREDDY": {"id": "881", "sym": "DRREDDY"}, 
    "TECHM": {"id": "13538", "sym": "TECHM"}, "WIPRO": {"id": "3787", "sym": "WIPRO"}, 
    "LTIM": {"id": "17818", "sym": "LTIM"}, "PERSISTENT": {"id": "18365", "sym": "PERSISTENT"}, 
    "COFORGE": {"id": "11543", "sym": "COFORGE"}, "DIXON": {"id": "21690", "sym": "DIXON"}, 
    "INDIGO": {"id": "11195", "sym": "INDIGO"}, "ASHOKLEY": {"id": "212", "sym": "ASHOKLEY"}, 
    "BHEL": {"id": "438", "sym": "BHEL"}, "IOC": {"id": "1624", "sym": "IOC"}, 
    "VOLTAS": {"id": "3718", "sym": "VOLTAS"}, "ETERNAL": {"id": "14416", "sym": "BERGEPAINT"}
}

# Session state cache structure to hold calculated values until a manual refresh is pushed
if "stored_data" not in st.session_state:
    st.session_state.stored_data = None
if "trade_states" not in st.session_state:
    st.session_state.trade_states = {sym: {"bull": "WAIT", "bear": "WAIT"} for sym in STOCKS_UNIVERSE.keys()}
# ==========================================
# 3. SIDEBAR PARAMETERS & AUTH CONTROLS
# ==========================================
st.sidebar.markdown("### 📊 WORKSTATION CONFIG")
st.sidebar.info("INTERVAL FIXED: 1D (DAILY CONTEXT)\nREFRESH: EXCLUSIVELY MANUAL")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔐 DHAN SECURE STORAGE AUTH")

client_id = st.secrets.get("dhan_client_id", st.secrets.get("DHAN_CLIENT_ID", ""))
access_token = st.secrets.get("dhan_access_token", st.secrets.get("DHAN_ACCESS_TOKEN", ""))

# Explicit context wrapper mapping to resolve argument tracking errors
dhan = None
if client_id and access_token:
    try:
        dhan_context = DhanContext(client_id=str(client_id).strip(), access_token=str(access_token).strip())
        dhan = dhanhq(dhan_context)
        st.sidebar.success("✅ DHAN SECURE ENGINE LINKED")
    except Exception as init_err:
        st.sidebar.error(f"AUTHENTICATION FAULT: {str(init_err)}")
else:
    st.sidebar.error("❌ VAULT APP SECRETS ARE NOT CONFIGURED")

# ==========================================
# 4. MATH & ENGINE DATA LOGIC FUNCTIONS
# ==========================================
def calculate_indicators(df):
    if df.empty or len(df) < 30:
        return None, None
    
    # Volume 1.5x Multiplier Benchmark
    df['avg_vol'] = df['volume'].rolling(window=20).mean()
    df['RVOL'] = df['volume'] / (df['avg_vol'] + 1e-9)
    
    # Native True Range & 14-Period ATR Calculation
    high_low = df['high'] - df['low']
    high_cp = (df['high'] - df['close'].shift(1)).abs()
    low_cp = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=14).mean()
    
    # Supertrend Structural Array Implementation (7, 3.0 Multiplier)
    hl2 = (df['high'] + df['low']) / 2
    upper = hl2 + (3.0 * df['atr'])
    lower = hl2 - (3.0 * df['atr'])
    supertrend, direction = np.zeros(len(df)), np.ones(len(df))
    
    for i in range(1, len(df)):
        direction[i] = 1 if df['close'].iloc[i] > upper.iloc[i-1] else (-1 if df['close'].iloc[i] < lower.iloc[i-1] else direction[i-1])
        supertrend[i] = lower.iloc[i] if direction[i] == 1 else upper.iloc[i]
    df['Supertrend'] = supertrend
    df['ST_Direction'] = direction
    
    # Native RSI Calculation
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / (loss + 1e-9))))
    
    # Native MACD Convergence Calculations
    ema12 = df['close'].ewm(span=12, adjust=False).mean()
    ema26 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Sig'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    return df.iloc[-1], df.iloc[-2]

def evaluate_stock(symbol, cur, prev):
    close, rvol, rsi = cur['close'], cur['RVOL'], cur['RSI']
    macd, msig, pmacd, pmsig = cur['MACD'], cur['MACD_Sig'], prev['MACD'], prev['MACD_Sig']
    
    prev_close = prev['close']
    chg = close - prev_close
    chg_pct = (chg / prev_close) * 100

    fresh_macd_bull = (pmacd <= pmsig) and (macd > msig)
    fresh_macd_bear = (pmacd >= pmsig) and (macd < msig)
    
    past_state = st.session_state.trade_states.get(symbol, {"bull": "WAIT", "bear": "WAIT"})

    # ==========================================
    # 🟢 BULLISH POSITION LOCK SYSTEM (HYSTERESIS)
    # ==========================================
    if past_state["bull"] == "BUY":
        # Keep holding signal active unless price structurally closes below Supertrend line
        if close < cur['Supertrend'] or cur['ST_Direction'] == -1:
            bull_action = "WAIT"
        else:
            bull_action = "BUY"
    else:
        # Evaluate clean checklist trigger breakout entries
        if rsi < 30 and fresh_macd_bull and rvol > 1.5 and close > cur['Supertrend']:
            bull_action = "BUY"
        else:
            bull_action = "WAIT"

    # ==========================================
    # 🔴 BEARISH POSITION LOCK SYSTEM (HYSTERESIS)
    # ==========================================
    if past_state["bear"] == "SELL":
        # Keep short trade active unless price structures back above Supertrend line
        if close > cur['Supertrend'] or cur['ST_Direction'] == 1:
            bear_action = "WAIT"
        else:
            bear_action = "SELL"
    else:
        # Evaluate reverse checklist trigger short entries
        if rsi > 70 and fresh_macd_bear and rvol > 1.5 and close < cur['Supertrend']:
            bear_action = "SELL"
        else:
            bear_action = "WAIT"

    # Save calculated trend signals back into persistent vault cache
    st.session_state.trade_states[symbol] = {"bull": bull_action, "bear": bear_action}

    return {
        "Symbol": symbol, "LTP": f"{close:.2f}", "CHG_Pct": f"{chg_pct:+.2f}%", "is_pos": chg_pct > 0,
        "RVOL": f"{rvol:.1f}x", "RSI": f"{rsi:.1f}",
        "Bull_Action": bull_action, "Bear_Action": bear_action,
        "Trend": "▲" if cur['ST_Direction'] == 1 else "▼"
    }
def fetch_screener_data():
    results = []
    
    # Process only if the context constructor has successfully linked to real tokens
    if dhan is not None:
        for key, data in STOCKS_UNIVERSE.items():
            sec_id = data["id"]
            symbol_lbl = data["sym"]
            
            try:
                # Query historical daily closed candle profiles directly from NSE servers
                raw_data = dhan.get_historical_data(
                    security_id=str(sec_id),
                    exchange_segment="NSE_EQ",
                    instrument_type="EQUITY",
                    expiry_code=0,
                    from_date=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
                    to_date=datetime.now().strftime("%Y-%m-%d"),
                    historical_data="DAY"
                )
                
                if raw_data and raw_data.get('status') == 'success' and 'data' in raw_data:
                    candles = raw_data['data']
                    df = pd.DataFrame(candles, columns=['open', 'high', 'low', 'close', 'volume', 'timestamp'])
                    
                    cur, prev = calculate_indicators(df)
                    if cur is not None:
                        results.append(evaluate_stock(symbol_lbl, cur, prev))
                        continue
            except Exception:
                pass
                
    # If the token array is empty or fails, return an empty tracking dataframe
    return pd.DataFrame(results)

# ==========================================
# 5. RENDER SYSTEM INTERFACE
# ==========================================
# Convert server timestamps to Indian Standard Time (IST)
ist_zone = pytz.timezone('Asia/Kolkata')
ist_now = datetime.now(ist_zone)

st.title("📟 F&O DAILY SWING MOMENTUM TERMINAL")
st.caption(f"WORKSPACE STATUS: STATIC SWEET | TIME CONTEXT: 1-DAY BARS | UNIVERSE CONQUANT: 50 INS")

# Render Manual Execution Control Panel
col_meta, col_btn = st.columns([3, 1])
with col_meta:
    st.markdown(f"<p style='color:#555555; padding-top:12px;'>LAST WORKSTATION ENGINE RUN (IST): {ist_now.strftime('%d-%b-%Y %H:%M:%S')}</p>", unsafe_allow_html=True)
with col_btn:
    # Clicking this button runs the query engine, fetches the data, and saves it into the session state
    trigger_refresh = st.button("RUN ENGINE SWEEP 🔄", use_container_width=True)

# Run logic loop if the workspace storage is empty OR if the manual refresh button is clicked
if st.session_state.stored_data is None or trigger_refresh:
    with st.spinner("COMMUNICATING WITH EXCHANGE CLIENT SERVERS..."):
        st.session_state.stored_data = fetch_screener_data()

# Read the cached dataset
raw_matrix = st.session_state.stored_data

grid_left, grid_right = st.columns(2)

if not raw_matrix.empty:
    # 📌 PINNED ACTION FLOATING ROW SORTER
    # Any row locking an active BUY or SELL action completely overrides standard sorting to float to the top
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
    st.warning("⚠️ EXCHANGE API LOADED BUT RETURNED EMPTY ROW DATASETS. COMPILE WORKSPACE VAULT PARAMETERS AGAIN.")
