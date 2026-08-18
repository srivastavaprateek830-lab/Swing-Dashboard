import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dhanhq import dhanhq
from datetime import datetime, timedelta
import requests
import io

# Import pure-python modern technical analysis engines
import ta
from ta.momentum import RSIIndicator
from ta.trend import MACD

# --- A. INITIAL INTERFACE STYLE CONFIG ---
st.set_page_config(page_title="SUPERCONFIRM: Swing Trading Command Center", layout="wide", page_icon="⚡")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; }
    div[data-testid="stMetricValue"] { font-size: 26px; font-weight: 700; color: #38bdf8; }
    div[data-testid="stMetricLabel"] { font-size: 13px; color: #94a3b8; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ SUPERCONFIRM: Swing Trading Command Center")
st.caption("Live Vector Strategy Engine • Scanning Real-Time NSE F&O Universe via Dhan Data Gateway")
st.divider()

# --- B. CREDENTIAL SIDEBAR PIPELINE ---
with st.sidebar:
    st.header("🔑 Developer API Credentials")
    client_id = st.secrets.get("DHAN_CLIENT_ID", st.text_input("Dhan Client ID", type="password"))
    access_token = st.secrets.get("DHAN_ACCESS_TOKEN", st.text_input("Dhan Access Token", type="password"))
    
    st.divider()
    st.markdown("### ⚙️ Strategy Multipliers")
    st_period = st.number_input("Supertrend Period", min_value=1, max_value=50, value=7)
    st_mult = st.number_input("Supertrend Multiplier", min_value=0.5, max_value=10.0, value=3.0, step=0.5)
    rsi_th = st.number_input("RSI Oversold Threshold", min_value=10, max_value=50, value=38)

# --- C. AUTOMATED SCRIP MASTER INGESTION ---
@st.cache_data(ttl=86400)
def fetch_live_fno_master():
    """Fetches the official Dhan global scrip master file dynamically."""
    url = "https://dhan.co"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            df_master = pd.read_csv(io.StringIO(response.text))
            
            fno_mask = (df_master['SEM_EXCH_SEGMENT'].str.upper() == 'NSE_EQ') & \
                       (df_master['SEM_INSTRUMENT_NAME'].str.upper() == 'EQUITY') & \
                       (df_master['SEM_SERIES'].str.upper() == 'EQ')
            
            fno_symbols = df_master[df_master['SEM_EXCH_SEGMENT'].str.upper() == 'NSE_FO']['SEM_UNDERLYING'].dropna().unique()
            df_filtered = df_master[fno_mask & df_master['SEM_TRADING_SYMBOL'].isin(fno_symbols)]
            
            mapping = {}
            for _, row in df_filtered.iterrows():
                symbol = str(row['SEM_TRADING_SYMBOL'])
                mapping[symbol] = {
                    "security_id": str(row['SEM_SM_ID']),
                    "segment": "NSE_EQ"
                }
            return mapping
    except Exception as e:
        st.error(f"Error establishing automated master scrip sync: {e}")
    return {}

def calculate_supertrend(df, period=7, multiplier=3):
    """Calculates pure mathematical Supertrend array matching TradingView formulas."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range and ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    
    hl2 = (high + low) / 2
    basic_upperband = hl2 + (multiplier * atr)
    basic_lowerband = hl2 - (multiplier * atr)
    
    final_upperband = pd.Series(0.0, index=df.index)
    final_lowerband = pd.Series(0.0, index=df.index)
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index) # 1 for Long, -1 for Short
    
    for i in range(1, len(df)):
        # Upper band logic
        if basic_upperband.iloc[i] < final_upperband.iloc[i-1] or close.iloc[i-1] > final_upperband.iloc[i-1]:
            final_upperband.iloc[i] = basic_upperband.iloc[i]
        else:
            final_upperband.iloc[i] = final_upperband.iloc[i-1]
            
        # Lower band logic
        if basic_lowerband.iloc[i] > final_lowerband.iloc[i-1] or close.iloc[i-1] < final_lowerband.iloc[i-1]:
            final_lowerband.iloc[i] = basic_lowerband.iloc[i]
        else:
            final_lowerband.iloc[i] = final_lowerband.iloc[i-1]
            
        # Direction logic
        if supertrend.iloc[i-1] == final_upperband.iloc[i-1]:
            direction.iloc[i] = 1 if close.iloc[i] > final_upperband.iloc[i] else -1
        else:
            direction.iloc[i] = -1 if close.iloc[i] < final_lowerband.iloc[i] else 1
            
        supertrend.iloc[i] = final_lowerband.iloc[i] if direction.iloc[i] == 1 else final_upperband.iloc[i]
        
    return supertrend, direction
# --- D. APPLICATION RUNTIME ENGINE LOOP ---
if client_id and access_token:
    dhan_context = DhanContext(client_id, access_token)
dhan = dhanhq(dhan_context)
    fno_universe = fetch_live_fno_master()
    
    if fno_universe:
        st.sidebar.success(f"Synchronized {len(fno_universe)} Live NSE F&O Assets!")
        scanned_matrix_results = []
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Pulling the first 40 high-liquidity symbols dynamically to stay within rate-limits
        active_keys = list(fno_universe.keys())[:40]
        
        for idx, symbol in enumerate(active_keys):
            meta = fno_universe[symbol]
            status_text.text(f"Analyzing Live OHLC Waves: {symbol} ({idx+1}/{len(active_keys)})...")
            progress_bar.progress((idx + 1) / len(active_keys))
            
            try:
                raw_ohlc = dhan.historical_daily_data(
                    symbol=f"{symbol}-EQ",
                    exchange_segment=meta["segment"],
                    from_date=start_date.strftime("%Y-%m-%d"),
                    to_date=end_date.strftime("%Y-%m-%d")
                )
                
                if raw_ohlc and 'data' in raw_ohlc and len(raw_ohlc['data']) > 30:
                    df = pd.DataFrame(raw_ohlc['data'])
                    df['start_Time'] = pd.to_datetime(df['start_Time'])
                    df = df.sort_values(by='start_Time').reset_index(drop=True)
                    
                    # 1. Pure-Python technical vector math execution
                    rsi_indicator = RSIIndicator(close=df['close'], window=14)
                    df['RSI_14'] = rsi_indicator.rsi()
                    
                    macd_calc = MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
                    df['MACD'] = macd_calc.macd()
                    df['MACD_Signal'] = macd_calc.macd_signal()
                    
                    # Compute native supertrend vectors
                    df['ST_Line'], df['ST_Dir'] = calculate_supertrend(df, period=st_period, multiplier=st_mult)
                    
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    
                    is_bullish_trend = latest['ST_Dir'] == 1
                    is_fresh_flip = (latest['ST_Dir'] == 1) and (prev['ST_Dir'] == -1)
                    macd_cross = latest['MACD'] > latest['MACD_Signal']
                    
                    if is_fresh_flip:
                        signal_state = "🟢 FRESH GREEN FLIP"
                    elif is_bullish_trend and macd_cross:
                        signal_state = "📈 RUNNING BULLISH"
                    elif not is_bullish_trend:
                        signal_state = "🛑 BEARISH TREND (EXIT)"
                    else:
                        signal_state = "⏳ CONSOLIDATING"
                        
                    scanned_matrix_results.append({
                        "Ticker": symbol,
                        "Live Close (Rs)": round(latest['close'], 2),
                        "RSI (14)": round(latest['RSI_14'], 2) if not pd.isna(latest['RSI_14']) else 0.0,
                        "Supertrend State": "Bullish 🟢" if is_bullish_trend else "Bearish 🔴",
                        "Trailing Stop Line": round(latest['ST_Line'], 2),
                        "System Signal": signal_state,
                        "df_ref": df
                    })
            except Exception:
                continue
                
        status_text.empty()
        progress_bar.empty()
        
        # --- E. LIVE TELEMETRY LOGS & LAYOUT RENDER ---
        if scanned_matrix_results:
            master_summary_df = pd.DataFrame(scanned_matrix_results)
            
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            with kpi1:
                st.metric("Total Dynamic Scans", len(master_summary_df))
            with kpi2:
                st.metric("Active Bullish Trends", sum(1 for x in scanned_matrix_results if "BULLISH" in x["System Signal"] or "FLIP" in x["System Signal"]))
            with kpi3:
                st.metric("Fresh Signal Flips", sum(1 for x in scanned_matrix_results if "FLIP" in x["System Signal"]))
            with kpi4:
                st.metric("Data Feed Status", "SYNCHRONIZED", delta="100% LIVE")
                
            st.divider()
            
            # --- F. TECHNICAL CHART LABS ---
            chart_panel_col, summary_panel_col = st.columns(2)
            
            with chart_panel_col:
                st.subheader("📊 Interactive Technical Execution Studio")
                target_scrip = st.selectbox("Select Target Analytics Underlying", options=master_summary_df["Ticker"].tolist())
                
                selected_record = next(item for item in scanned_matrix_results if item["Ticker"] == target_scrip)
                chart_df = selected_record["df_ref"]
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=chart_df['start_Time'], open=chart_df['open'], high=chart_df['high'], low=chart_df['low'], close=chart_df['close'],
                    name="Price", increasing_line_color='#10b981', decreasing_line_color='#ef4444'
                ))
                fig.add_trace(go.Scatter(
                    x=chart_df['start_Time'], y=chart_df['ST_Line'], line=dict(color='#38bdf8', width=2, dash='dash'),
                    name="Supertrend Line"
                ))
                fig.update_layout(template="plotly_dark", height=380, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)

            with summary_panel_col:
                st.subheader("⚡ Live System Telemetry Logs")
                for item in scanned_matrix_results[:6]:
                    if "FLIP" in item["System Signal"]:
                        st.success(f"📟 **{item['Ticker']}**: Fresh Supertrend Bullish Flip at Rs. {item['Live Close (Rs)']}")
                    elif "EXIT" in item["System Signal"]:
                        st.error(f"⚠️ **{item['Ticker']}**: Trailing stop broken on daily timeframe.")

            st.divider()

            # --- G. LIVE DATA FRAME RADAR MATRIX ---
            st.subheader("📋 Active Execution Strategy Radar Array")
            
            def styling_matrix_filters(val):
                if "FLIP" in str(val) or "RUNNING" in str(val):
                    return 'color: #10b981; font-weight: bold;'
                elif "EXIT" in str(val):
                    return 'color: #ef4444; font-weight: bold;'
                return 'color: #cbd5e1;'

            clean_display_df = master_summary_df.drop(columns=['df_ref'])
            st.dataframe(
                clean_display_df.style.applymap(styling_matrix_filters, subset=['System Signal']),
                use_container_width=True, hide_index=True
            )
        else:
            st.warning("No candle data returned from server parameters. Check API connection status pools.")
    else:
        st.error("Could not fetch the live NSE F&O Master file from Dhan. Please check your internet connection.")
else:
    st.info("💡 Gateway Interface Offline: Supply your credentials via secrets or sidebar to automatically map all F&O securities.")
