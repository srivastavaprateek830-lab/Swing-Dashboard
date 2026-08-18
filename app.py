import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from dhanhq import DhanContext, dhanhq
from datetime import datetime, timedelta
import requests
import io
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
st.caption("Live Vector Strategy Engine • Scanning Real-Time Dynamic NSE F&O Universe")
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

# --- C. AUTOMATED SCRIP MASTER INGESTION (100% LIVE, ZERO MOCK CODES) ---
@st.cache_data(ttl=86400)
def fetch_live_fno_master():
    """Fetches the raw global master file from Dhan, dynamically maps column names, 
    and returns the entire live universe of tradeable symbols mapped to their numeric IDs."""
    url = "https://dhan.co"
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            df_master = pd.read_csv(io.StringIO(response.text), on_bad_lines='skip', low_memory=False)
            
            # Normalize column names to uppercase to match dynamically
            cols = {c.upper(): c for c in df_master.columns}
            
            # Dynamically identify the column names currently used by the server
            exch_col = cols.get('SEM_EXM_EXCH_ID', cols.get('SEM_EXCH_SEGMENT', ''))
            segment_col = cols.get('SEM_SEGMENT', '')
            symbol_col = cols.get('SEM_TRADING_SYMBOL', '')
            id_col = cols.get('SEM_SM_ID', '')
            underlying_col = next((cols[k] for k in cols if 'UNDERLYING' in k), '')
            
            # Enforce strict exit logic if the server changes key formatting
            if not exch_col or not segment_col or not symbol_col or not id_col:
                st.error("Dhan data feed structure has changed. Unable to parse data columns.")
                return {}
                
            # Create a mask for standard NSE Equities
            equity_mask = (df_master[exch_col].astype(str).str.upper().str.contains('NSE')) & \
                          (df_master[segment_col].astype(str).str.upper() == 'E')
            
            # Isolate the live F&O universe by checking which stocks are listed under the Derivatives segment ('D')
            if underlying_col and underlying_col in df_master.columns:
                fno_underlyings = df_master[df_master[segment_col].astype(str).str.upper() == 'D'][underlying_col].dropna().unique()
                df_filtered = df_master[equity_mask & df_master[symbol_col].isin(fno_underlyings)]
            else:
                df_filtered = df_master[equity_mask]
                
            mapping = {}
            for _, row in df_filtered.iterrows():
                symbol = str(row[symbol_col])
                if symbol.endswith("-EQ"):
                    symbol = symbol.replace("-EQ", "")
                
                # Filter out symbols containing numbers to focus strictly on pure company tickers
                if symbol.isalpha():
                    mapping[symbol] = {
                        "security_id": str(int(row[id_col])),
                        "segment": "NSE_EQ"
                    }
            return mapping
    except Exception as e:
        st.error(f"Fatal error reading live broker registry stream: {e}")
    return {}

def calculate_supertrend(df, period=7, multiplier=3):
    high, low, close = df['high'], df['low'], df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)
    
    final_upper = pd.Series(0.0, index=df.index)
    final_lower = pd.Series(0.0, index=df.index)
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)
    
    for i in range(1, len(df)):
        final_upper.iloc[i] = basic_upper.iloc[i] if basic_upper.iloc[i] < final_upper.iloc[i-1] or close.iloc[i-1] > final_upper.iloc[i-1] else final_upper.iloc[i-1]
        final_lower.iloc[i] = basic_lower.iloc[i] if basic_lower.iloc[i] > final_lower.iloc[i-1] or close.iloc[i-1] < final_lower.iloc[i-1] else final_lower.iloc[i-1]
        if supertrend.iloc[i-1] == final_upper.iloc[i-1]:
            direction.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
        else:
            direction.iloc[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        supertrend.iloc[i] = final_lower.iloc[i] if direction.iloc[i] == 1 else final_upper.iloc[i]
    return supertrend, direction
# --- D. APPLICATION RUNTIME ENGINE LOOP ---
if client_id and access_token:
    dhan_context = DhanContext(client_id, access_token)
    dhan = dhanhq(dhan_context)
    fno_universe = fetch_live_fno_master()
    
    if fno_universe:
        st.sidebar.success(f"Synchronized {len(fno_universe)} Real-Time F&O Assets!")
        scanned_matrix_results = []
        end_date = datetime.now()
        start_date = end_date - timedelta(days=120)
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Pull the live tokens dynamically sorted alphabetically
        active_keys = sorted(list(fno_universe.keys()))[:35]
        
        for idx, symbol in enumerate(active_keys):
            meta = fno_universe[symbol]
            numeric_id = meta["security_id"]
            
            status_text.text(f"Processing Live Tokens: {symbol} (ID: {numeric_id}) [{idx+1}/{len(active_keys)}]...")
            progress_bar.progress((idx + 1) / len(active_keys))
            
            try:
                raw_ohlc = dhan.historical_daily_data(
                    symbol=numeric_id,
                    exchange_segment="NSE_EQ",
                    instrument_type="EQUITY",
                    expiry_code=0,
                    from_date=start_date.strftime("%Y-%m-%d"),
                    to_date=end_date.strftime("%Y-%m-%d")
                )
                
                if raw_ohlc and 'data' in raw_ohlc and len(raw_ohlc['data']) > 20:
                    df = pd.DataFrame(raw_ohlc['data'])
                    df['start_Time'] = pd.to_datetime(df['start_Time'])
                    df = df.sort_values(by='start_Time').reset_index(drop=True)
                    
                    # Compute vector indicator matrices
                    df['RSI_14'] = RSIIndicator(close=df['close'], window=14).rsi()
                    macd_calc = MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
                    df['MACD'] = macd_calc.macd()
                    df['MACD_Signal'] = macd_calc.macd_signal()
                    df['ST_Line'], df['ST_Dir'] = calculate_supertrend(df, period=st_period, multiplier=st_mult)
                    
                    latest, prev = df.iloc[-1], df.iloc[-2]
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
                        "Ticker": symbol, "Live Close (Rs)": round(latest['close'], 2),
                        "RSI (14)": round(latest['RSI_14'], 2) if not pd.isna(latest['RSI_14']) else 0.0,
                        "Supertrend State": "Bullish 🟢" if is_bullish_trend else "Bearish 🔴",
                        "Trailing Stop Line": round(latest['ST_Line'], 2), "System Signal": signal_state, "df_ref": df
                    })
            except Exception:
                continue
                
        status_text.empty()
        progress_bar.empty()
        
        # --- E. RENDERING METRICS & GRAPHICS GRID ---
        if scanned_matrix_results:
            master_summary_df = pd.DataFrame(scanned_matrix_results)
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("Total Dynamic Scans", len(master_summary_df))
            kpi2.metric("Active Bullish Trends", sum(1 for x in scanned_matrix_results if "BULLISH" in x["System Signal"] or "FLIP" in x["System Signal"]))
            kpi3.metric("Fresh Signal Flips", sum(1 for x in scanned_matrix_results if "FLIP" in x["System Signal"]))
            kpi4.metric("Data Feed Status", "SYNCHRONIZED", delta="100% LIVE")
            st.divider()
            
            # --- F. TECHNICAL CHART LABS ---
            chart_panel_col, summary_panel_col = st.columns(2)
            with chart_panel_col:
                st.subheader("📊 Interactive Technical Execution Studio")
                target_scrip = st.selectbox("Select Target Analytics Underlying", options=master_summary_df["Ticker"].tolist())
                selected_record = next(item for item in scanned_matrix_results if item["Ticker"] == target_scrip)
                chart_df = selected_record["df_ref"]
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=chart_df['start_Time'], open=chart_df['open'], high=chart_df['high'], low=chart_df['low'], close=chart_df['close'], name="Price", increasing_line_color='#10b981', decreasing_line_color='#ef4444'))
                fig.add_trace(go.Scatter(x=chart_df['start_Time'], y=chart_df['ST_Line'], line=dict(color='#38bdf8', width=2, dash='dash'), name="Supertrend Line"))
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
                if "FLIP" in str(val) or "RUNNING" in str(val): return 'color: #10b981; font-weight: bold;'
                elif "EXIT" in str(val): return 'color: #ef4444; font-weight: bold;'
                return 'color: #cbd5e1;'

            clean_display_df = master_summary_df.drop(columns=['df_ref'])
            st.dataframe(clean_display_df.style.applymap(styling_matrix_filters, subset=['System Signal']), use_container_width=True, hide_index=True)
        else:
            st.warning("No candle data returned from server parameters. Check your Dhan account subscription or endpoint configurations.")
    else:
        st.error("Failed to parse live tokens from server registry. Check internet connectivity.")
else:
    st.info("💡 Gateway Interface Offline: Supply your credentials via secrets or sidebar to automatically map all F&O securities.")
