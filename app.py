import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from dhan_api import DhanClient
from indicators import build_signal
from universe import load_fno_universe

st.set_page_config(
    page_title="FNO SWING TERMINAL",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.stApp { background:#07111f; color:#d8e7f5; }
.block-container { padding: 1rem 1.5rem 2rem; max-width: 1500px; }
h1,h2,h3 { color:#d8e7f5; }
.terminal-title { font-size:28px; font-weight:800; letter-spacing:2px; color:#45e6a5; }
.subtitle { color:#7fa0bd; font-size:12px; letter-spacing:1px; }
.ticker-wrap { overflow:hidden; white-space:nowrap; background:#0b1a2c; border:1px solid #163450; padding:9px 0; margin:8px 0 16px; }
.ticker { display:inline-block; animation:scroll 28s linear infinite; }
.tick { margin-right:42px; font-family:monospace; font-size:13px; }
.green { color:#45e6a5; } .red { color:#ff5f70; } .amber { color:#ffc857; }
@keyframes scroll { 0% { transform:translateX(100%); } 100% { transform:translateX(-100%); } }
.card { background:#0b1a2c; border:1px solid #163450; border-radius:8px; padding:14px; }
.small { color:#7fa0bd; font-size:11px; }
.signal { font-size:24px; font-weight:800; color:#45e6a5; }
div[data-testid="stMetric"] { background:#0b1a2c; border:1px solid #163450; padding:8px; border-radius:7px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    token = st.secrets.get("DHAN_ACCESS_TOKEN", "")
    client_id = st.secrets.get("DHAN_CLIENT_ID", "")
    return DhanClient(token=token, client_id=client_id)

st.markdown('<div class="terminal-title">FNO SWING TERMINAL</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">RSI OVERSOLD → FRESH MACD CROSS → HIGH VOLUME → SUPERTREND CONFIRMATION</div>', unsafe_allow_html=True)

client = get_client()

if not client.ready:
    st.error("Dhan credentials are missing. Add DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID to Streamlit Secrets.")
    st.stop()

with st.sidebar:
    st.header("ENGINE")
    interval = st.selectbox("Swing timeframe", ["1D"], index=0)
    rsi_limit = st.slider("RSI below", 20, 40, 30)
    volume_multiple = st.slider("Volume / 20D avg", 1.0, 3.0, 1.5, 0.1)
    st.caption("Universe: NSE F&O stocks only")
    st.caption("Signals only — no order execution.")
    refresh = st.button("↻ RUN SCAN", use_container_width=True)

@st.cache_data(ttl=86400, show_spinner=False)
def get_universe():
    return load_fno_universe()

@st.cache_data(ttl=600, show_spinner=False)
def run_scan(rsi_limit, volume_multiple):
    universe = get_universe()
    rows = []
    errors = []
    for item in universe:
        try:
            df = client.daily_history(item["security_id"], days=180)
            if df is None or len(df) < 60:
                continue
            result = build_signal(
                df,
                rsi_limit=rsi_limit,
                volume_multiple=volume_multiple
            )
            if result:
                result["SYMBOL"] = item["symbol"]
                result["SECURITY_ID"] = item["security_id"]
                rows.append(result)
        except Exception as e:
            errors.append(f'{item["symbol"]}: {e}')

    return pd.DataFrame(rows), errors, len(universe)

if refresh:
    run_scan.clear()

with st.spinner("Scanning NSE F&O universe…"):
    signals, errors, universe_count = run_scan(rsi_limit, volume_multiple)

if signals.empty:
    st.warning("No stock currently meets the complete swing setup.")
    st.caption(f"F&O universe scanned: {universe_count} | Last scan: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
    if errors:
        st.caption(f"API/data issues on {len(errors)} symbols. Check Dhan Data API access/subscription if this persists.")
    st.stop()

signals = signals.sort_values(["SCORE", "VOLUME_RATIO"], ascending=False).reset_index(drop=True)

ticker_html = "".join(
    f'<span class="tick { "green" if r.SIGNAL=="LONG" else "red" }">'
    f'{r.SYMBOL} {r.SCORE:.0f} | ₹{r.PRICE:.2f}'
    f'</span>'
    for _, r in signals.head(20).iterrows()
)
st.markdown(f'<div class="ticker-wrap"><div class="ticker">{ticker_html}</div></div>', unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
c1.metric("F&O SCANNED", universe_count)
c2.metric("LONG SETUPS", len(signals))
c3.metric("TOP SCORE", f'{signals.iloc[0]["SCORE"]:.0f}')
c4.metric("SCAN TIME", datetime.now().strftime("%H:%M:%S"))

st.subheader("HIGH-CONVICTION SWING SETUPS")

display_cols = [
    "SYMBOL","PRICE","RSI","MACD_HIST","VOLUME_RATIO",
    "SUPERTREND","DIST_ST_%","SCORE","ENTRY","STOP","TARGET"
]
table = signals[display_cols].copy()
table.columns = [
    "Ticker","Price","RSI","MACD Hist","Vol / 20D",
    "Supertrend","ST Dist %","Score","Entry","Trail SL","Target"
]
st.dataframe(
    table.style.format({
        "Price":"₹{:.2f}","RSI":"{:.1f}","MACD Hist":"{:.3f}",
        "Vol / 20D":"{:.2f}x","Supertrend":"₹{:.2f}",
        "ST Dist %":"{:.2f}%","Score":"{:.0f}",
        "Entry":"₹{:.2f}","Trail SL":"₹{:.2f}","Target":"₹{:.2f}"
    }),
    use_container_width=True,
    hide_index=True,
)

st.subheader("CHART CHECK")

symbol = st.selectbox("Select setup", signals["SYMBOL"].tolist())
row = signals.loc[signals["SYMBOL"] == symbol].iloc[0]
df = client.daily_history(str(int(row["SECURITY_ID"])), days=120)

df["ST"] = build_signal(df, rsi_limit=100, volume_multiple=0)["ST_SERIES"]
fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=df.index, open=df["open"], high=df["high"],
    low=df["low"], close=df["close"], name="Price"
))
fig.add_trace(go.Scatter(x=df.index, y=df["ST"], name="Supertrend", mode="lines"))
fig.update_layout(
    template="plotly_dark",
    paper_bgcolor="#07111f",
    plot_bgcolor="#07111f",
    height=520,
    margin=dict(l=10,r=10,t=30,b=10),
    xaxis_rangeslider_visible=False,
)
st.plotly_chart(fig, use_container_width=True)

a,b,c,d = st.columns(4)
a.metric("ENTRY", f'₹{row["ENTRY"]:.2f}')
b.metric("TRAIL SL", f'₹{row["STOP"]:.2f}')
c.metric("TARGET", f'₹{row["TARGET"]:.2f}')
d.metric("RISK / SHARE", f'₹{row["ENTRY"]-row["STOP"]:.2f}')

st.caption(
    "Logic: RSI below threshold + bullish MACD crossover on latest daily candle + "
    "volume above 20-day average + price above Supertrend. "
    "Trail the stop below the live Supertrend line."
)
