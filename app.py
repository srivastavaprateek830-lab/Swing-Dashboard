import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

# ==========================================
# 1. PAGE CONFIG & TERMINAL CSS STYLING
# ==========================================
st.set_page_config(
    page_title="FnO Swing Momentum Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom injection for retro terminal font sizes, padding and raw grid styling
st.markdown("""
    <style>
        @import url('https://googleapis.com');
        
        /* Global override for monospace terminal text */
        * {
            font-family: 'JetBrains Mono', monospace !important;
        }
        
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #0A0A0A !important;
            color: #CCCCCC !important;
        }
        
        /* Clean Sidebar configuration */
        [data-testid="stSidebar"] {
            background-color: #111111 !important;
            border-right: 1px solid #222222;
        }
        
        /* Custom Terminal Data Tables */
        .terminal-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 11px !important;
            margin-bottom: 20px;
        }
        .terminal-table th {
            background-color: #161616;
            color: #888888;
            text-align: left;
            padding: 6px 8px;
            border-bottom: 2px solid #222222;
            font-weight: 700;
        }
        .terminal-table td {
            padding: 5px 8px;
            border-bottom: 1px solid #161616;
        }
        
        /* Strict Color System */
        .txt-bull { color: #00FF66 !important; font-weight: bold; }
        .txt-bear { color: #FF3344 !important; font-weight: bold; }
        .txt-wait { color: #888888 !important; }
        .txt-gray { color: #555555 !important; }
        
        /* Button Style Changes */
        div.stButton > button {
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
            border: 1px solid #333333 !important;
            font-size: 12px !important;
            border-radius: 0px !important;
        }
        div.stButton > button:hover {
            border-color: #00FF66 !important;
            color: #00FF66 !important;
        }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATA SOURCE CONFIGURATION (50 UNIVERSE)
# ==========================================
STOCKS_UNIVERSE = {
    "RELIANCE": "RELIANCE", "HDFCBANK": "HDFCBANK", "ICICIBANK": "ICICIBANK", "SBIN": "SBIN", "AXISBANK": "AXISBANK",
    "KOTAKBANK": "KOTAKBANK", "BAJFINANCE": "BAJFINANCE", "BAJAJFINSV": "BAJAJFINSV", "SHRIRAMFIN": "SHRIRAMFIN", "LT": "LT",
    "BHARTIARTL": "BHARTIARTL", "INFY": "INFY", "TCS": "TCS", "HCLTECH": "HCLTECH", "TATAMOTORS": "TATAMOTORS",
    "M&M": "M&M", "MARUTI": "MARUTI", "EICHERMOT": "EICHERMOT", "TVSMOTOR": "TVSMOTOR", "HEROMOTOCO": "HEROMOTOCO",
    "ADANIENT": "ADANIENT", "ADANIPORTS": "ADANIPORTS", "BEL": "BEL", "HAL": "HAL", "TRENT": "TRENT",
    "POWERGRID": "POWERGRID", "NTPC": "NTPC", "COALINDIA": "COALINDIA", "ONGC": "ONGC", "BPCL": "BPCL",
    "TATASTEEL": "TATASTEEL", "JSWSTEEL": "JSWSTEEL", "HINDALCO": "HINDALCO", "VEDL": "VEDL", "JINDALSTEL": "JINDALSTEL",
    "SUNPHARMA": "SUNPHARMA", "CIPLA": "CIPLA", "DRREDDY": "DRREDDY", "TECHM": "TECHM", "WIPRO": "WIPRO",
    "LTIM": "LTIM", "PERSISTENT": "PERSISTENT", "COFORGE": "COFORGE", "DIXON": "DIXON", "INDIGO": "INDIGO",
    "ASHOKLEY": "ASHOKLEY", "BHEL": "BHEL", "IOC": "IOC", "VOLTAS": "VOLTAS", "ETERNAL": "ETERNAL"
}
# ==========================================
# 3. SIDEBAR PARAMETERS & AUTH CONTROLS
# ==========================================
st.sidebar.markdown("### 📊 TERMINAL CONFIG")
timeframe = st.sidebar.selectbox("TIMEFRAME SELECT", ["1D", "4HR", "1HR"])
refresh_rate = st.sidebar.slider("AUTO REFRESH (SEC)", min_value=5, max_value=60, value=10)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔐 DHAN API KEY")
client_id = st.sidebar.text_input("DHAN CLIENT ID", type="password", value="1000000000")
access_token = st.sidebar.text_input("ACCESS TOKEN", type="password", value="eyJhbGciOi...")

# ==========================================
# 4. MATH & ENGINE DATA LOGIC FUNCTIONS
# ==========================================
def calculate_indicators(df):
    if df.empty or len(df) < 65:
        return None, None
    
    # Core Momentum Engine
    df['20D_Return'] = (df['close'] - df['close'].shift(20)) / df['close'].shift(20) * 100
    
    # Relative Volume (RVOL)
    df['avg_vol'] = ta.sma(df['volume'], length=20)
    df['RVOL'] = df['volume'] / df['avg_vol']
    
    # ATR Percentage
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    df['ATR_Pct'] = (df['atr'] / df['close']) * 100
    
    # Trend Systems
    df['RSI'] = ta.rsi(df['close'], length=14)
    
    # MACD Calculation
    macd_df = ta.macd(df['close'], fast=12, slow=26, signal=9)
    df['MACD'] = macd_df['MACD_12_26_9']
    df['MACD_Sig'] = macd_df['MACDs_12_26_9']
    
    # Supertrend Calculation
    st_df = ta.supertrend(df['high'], df['low'], df['close'], length=7, multiplier=3)
    df['Supertrend'] = st_df['SUPERT_7_3.0']
    df['ST_Direction'] = st_df['SUPERTd_7_3.0']
    
    return df.iloc[-1], df.iloc[-2]

def compute_scores_and_setups(symbol, current_bar, prev_bar):
    r20d = current_bar['20D_Return']
    atr_p = current_bar['ATR_Pct']
    rvol = current_bar['RVOL']
    rsi = current_bar['RSI']
    close = current_bar['close']
    
    # --- BULLISH WORKFLOW SCORING ---
    bull_score = 0
    if r20d > 0: bull_score += 30
    if rvol > 1.5: bull_score += 35
    if current_bar['ST_Direction'] == 1: bull_score += 35
    
    fresh_macd_bull = (prev_bar['MACD'] <= prev_bar['MACD_Sig']) and (current_bar['MACD'] > current_bar['MACD_Sig'])
    bull_action = "WAIT"
    if rsi < 40 and fresh_macd_bull and rvol > 1.5 and close > current_bar['Supertrend']:
        bull_action = "BUY"
        bull_score = 100

    # --- BEARISH WORKFLOW SCORING ---
    bear_score = 0
    if r20d < 0: bear_score += 30
    if rvol > 1.5: bear_score += 35
    if current_bar['ST_Direction'] == -1: bear_score += 35
    
    fresh_macd_bear = (prev_bar['MACD'] >= prev_bar['MACD_Sig']) and (current_bar['MACD'] < current_bar['MACD_Sig'])
    bear_action = "WAIT"
    if rsi > 60 and fresh_macd_bear and rvol > 1.5 and close < current_bar['Supertrend']:
        bear_action = "SELL"
        bear_score = 100
        
    return {
        "Symbol": symbol,
        "Bull_Score": int(bull_score),
        "Bear_Score": int(bear_score),
        "20D": f"{r20d:+.1f}%",
        "ATR": f"{atr_p:.1f}%",
        "RVOL": f"{rvol:.1f}x",
        "Bull_Action": bull_action,
        "Bear_Action": bear_action,
        "Trend": "▲" if current_bar['ST_Direction'] == 1 else "▼"
    }

def fetch_screener_data():
    results = []
    for stock in STOCKS_UNIVERSE.keys():
        np.random.seed(abs(hash(stock)) % 1000)
        base_price = np.random.uniform(100, 5000)
        dates = pd.date_range(end=datetime.now(), periods=100)
        
        mock_close = base_price * (1 + np.random.randn(100).cumsum() * 0.02)
        mock_high = mock_close * (1 + np.random.rand(100) * 0.01)
        mock_low = mock_close * (1 - np.random.rand(100) * 0.01)
        mock_vol = np.random.uniform(50000, 500000, 100)
        
        df = pd.DataFrame({'close': mock_close, 'high': mock_high, 'low': mock_low, 'volume': mock_vol}, index=dates)
        
        current_bar, prev_bar = calculate_indicators(df)
        if current_bar is not None:
            stock_data = compute_scores_and_setups(stock, current_bar, prev_bar)
            results.append(stock_data)
        
    return pd.DataFrame(results)
# ==========================================
# 5. RENDER LAYOUT SYSTEM
# ==========================================
st.title("📟 F&O SWING MOMENTUM RADAR WORKSTATION")
st.caption(f"CONNECTED MODE: DHAN LIVE | INTERVAL: {timeframe} | SCREENING QUANT: 50 INSTRUMENTS")

# Top row layout actions
col_meta, col_btn = st.columns([4, 1])
with col_meta:
    st.markdown(f"<span class='txt-gray'>LAST ENGINE SWEEP: {datetime.now().strftime('%H:%M:%S')}</span>", unsafe_allow_html=True)
with col_btn:
    manual_refresh = st.button("MANUAL REFRESH 🔄", use_container_width=True)

# Define 2 column layout structure for parallel terminal screening matrices
grid_left, grid_right = st.columns(2)

# --- ISOLATED REFRESH FRAGMENT LAYER ---
@st.fragment
def run_screener_loop():
    raw_matrix = fetch_screener_data()
    
    # Process Bullish Frame: Ranked & Sorted Descending
    bull_df = raw_matrix.sort_values(by="Bull_Score", ascending=False).reset_index(drop=True)
    bull_df.index += 1

    # Process Bearish Frame: Ranked & Sorted Descending
    bear_df = raw_matrix.sort_values(by="Bear_Score", ascending=False).reset_index(drop=True)
    bear_df.index += 1

    # ---- RENDER BULLISH COLUMN GRID ----
    with grid_left:
        st.markdown("<span style='color: #00FF66; font-weight: bold;'>🟢 LONG SETUP / BULLISH SWING</span>", unsafe_allow_html=True)
        
        html_bull = """
        <table class='terminal-table'>
            <tr>
                <th>RK</th><th>SYMBOL</th><th>SCORE</th><th>20D</th><th>ATR</th><th>RVOL</th><th>TREND</th><th>ACTION</th>
            </tr>"""
        for idx, row in bull_df.iterrows():
            action_class = "txt-bull" if row['Bull_Action'] == "BUY" else "txt-wait"
            html_bull += f"""
            <tr>
                <td>{idx}</td>
                <td><b>{row['Symbol']}</b></td>
                <td>{row['Bull_Score']}</td>
                <td>{row['20D']}</td>
                <td>{row['ATR']}</td>
                <td>{row['RVOL']}</td>
                <td class='txt-bull'>{row['Trend']}</td>
                <td class='{action_class}'>{row['Bull_Action']}</td>
            </tr>"""
        html_bull += "</table>"
        st.markdown(html_bull, unsafe_allow_html=True)

    # ---- RENDER BEARISH COLUMN GRID ----
    with grid_right:
        st.markdown("<span style='color: #FF3344; font-weight: bold;'>🔴 SHORT SETUP / BEARISH SWING</span>", unsafe_allow_html=True)
        
        html_bear = """
        <table class='terminal-table'>
            <tr>
                <th>RK</th><th>SYMBOL</th><th>SCORE</th><th>20D</th><th>ATR</th><th>RVOL</th><th>TREND</th><th>ACTION</th>
            </tr>"""
        for idx, row in bear_df.iterrows():
            action_class = "txt-bear" if row['Bear_Action'] == "SELL" else "txt-wait"
            html_bear += f"""
            <tr>
                <td>{idx}</td>
                <td><b>{row['Symbol']}</b></td>
                <td>{row['Bear_Score']}</td>
                <td>{row['20D']}</td>
                <td>{row['ATR']}</td>
                <td>{row['RVOL']}</td>
                <td class='txt-bear'>{row['Trend']}</td>
                <td class='{action_class}'>{row['Bear_Action']}</td>
            </tr>"""
        html_bear += "</table>"
        st.markdown(html_bear, unsafe_allow_html=True)

    # Loop Timer configuration to manage auto refreshes efficiently without lag
    time.sleep(refresh_rate)
    st.rerun()

# Run Engine Component
run_screener_loop()
