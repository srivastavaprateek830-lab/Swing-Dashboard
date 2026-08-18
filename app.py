import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

from dhan_api import DhanClient, DhanAPIError
from indicators import build_signal
from universe import load_fno_universe

st.set_page_config(page_title="FNO SWING TERMINAL", page_icon="📈", layout="wide")

st.markdown("""
<style>
.stApp { background:#07111f; color:#d8e7f5; }
.block-container { padding:1rem 1.5rem 2rem; max-width:1500px; }
.terminal-title {font-size:28px;font-weight:800;letter-spacing:2px;color:#45e6a5;}
.subtitle {color:#7fa0bd;font-size:12px;letter-spacing:1px;}
.ticker-wrap {overflow:hidden;white-space:nowrap;background:#0b1a2c;border:1px solid #163450;padding:9px 0;margin:8px 0 16px;}
.ticker {display:inline-block;animation:scroll 28s linear infinite;}
.tick {margin-right:42px;font-family:monospace;font-size:13px;}
.green{color:#45e6a5}.red{color:#ff5f70}.amber{color:#ffc857}
@keyframes scroll{0%{transform:translateX(100%)}100%{transform:translateX(-100%)}}
div[data-testid="stMetric"]{background:#0b1a2c;border:1px solid #163450;padding:8px;border-radius:7px;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_client():
    token = st.secrets.get("DHAN_ACCESS_TOKEN", "")
    client_id = st.secrets.get("DHAN_CLIENT_ID", "")
    return DhanClient(token=token, client_id=client_id)

client = get_client()

st.markdown('<div class="terminal-title">FNO SWING TERMINAL</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">RSI OVERSOLD → FRESH MACD CROSS → HIGH VOLUME → SUPERTREND CONFIRMATION</div>',
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("ENGINE")
    timeframe = st.selectbox(
        "Swing timeframe",
        ["1D", "4H", "1H"],
        index=0,
        help="1D = swing; 4H = short swing; 1H = tactical short swing."
    )
    rsi_limit = st.slider("RSI below", 20, 40, 30)
    volume_multiple = st.slider("Volume / 20D avg", 1.0, 3.0, 1.5, 0.1)
    st.caption("Universe: NSE F&O stocks only")
    st.caption("Signals only — no order execution.")
    refresh = st.button("↻ RUN SCAN", use_container_width=True)

@st.cache_data(ttl=86400, show_spinner=False)
def get_universe():
    return load_fno_universe()

@st.cache_data(ttl=600, show_spinner=False)
def run_scan(timeframe, rsi_limit, volume_multiple):
    universe = get_universe()
    rows, errors = [], []

    for item in universe:
        try:
            df = client.history(item["security_id"], timeframe=timeframe)
            if df is None or len(df) < 60:
                continue
            result = build_signal(df, rsi_limit=rsi_limit, volume_multiple=volume_multiple)
            if result:
                result["SYMBOL"] = item["symbol"]
                result["SECURITY_ID"] = item["security_id"]
                rows.append(result)
        except Exception as e:
            errors.append({
                "symbol": item["symbol"],
                "error": str(e)
            })

    return pd.DataFrame(rows), errors, len(universe)

if refresh:
    run_scan.clear()
    get_universe.clear()

if not client.ready:
    st.error("Dhan credentials are missing. Add DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID to Streamlit Secrets.")
    st.stop()

with st.spinner(f"Scanning NSE F&O stocks on {timeframe}…"):
    signals, errors, universe_count = run_scan(timeframe, rsi_limit, volume_multiple)

if errors:
    st.warning(
        f"{len(errors)} of {universe_count} symbols returned API/data errors. "
        f"The first actual Dhan error is shown below — this is more useful than the old generic message."
    )
    with st.expander("Show Dhan API errors"):
        st.dataframe(pd.DataFrame(errors[:25]), use_container_width=True, hide_index=True)

if signals.empty:
    st.info(
        f"No stock currently meets the complete {timeframe} swing setup. "
        f"F&O universe scanned: {universe_count}."
    )
    st.caption(f"Last scan: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
    st.stop()

signals = signals.sort_values(["SCORE", "VOLUME_RATIO"], ascending=False).reset_index(drop=True)

ticker_html = "".join(
    f'<span class="tick green">{r.SYMBOL} {r.SCORE:.0f} | ₹{r.PRICE:.2f}</span>'
    for _, r in signals.head(20).iterrows()
)
st.markdown(f'<div class="ticker-wrap"><div class="ticker">{ticker_html}</div></div>', unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
c1.metric("F&O SCANNED", universe_count)
c2.metric("LONG SETUPS", len(signals))
c3.metric("TOP SCORE", f'{signals.iloc[0]["SCORE"]:.0f}')
c4.metric("TIMEFRAME", timeframe)

st.subheader("HIGH-CONVICTION SWING SETUPS")

display_cols = [
    "SYMBOL","PRICE","RSI","MACD_HIST","VOLUME_RATIO",
    "SUPERTREND","DIST_ST_%","SCORE","ENTRY","STOP","TARGET"
]
table = signals[display_cols].copy()
table.columns = ["Ticker","Price","RSI","MACD Hist","Vol / 20D","Supertrend","ST Dist %","Score","Entry","Trail SL","Target"]

st.dataframe(
    table.style.format({
        "Price":"₹{:.2f}","RSI":"{:.1f}","MACD Hist":"{:.3f}",
        "Vol / 20D":"{:.2f}x","Supertrend":"₹{:.2f}",
        "ST Dist %":"{:.2f}%","Score":"{:.0f}",
        "Entry":"₹{:.2f}","Trail SL":"₹{:.2f}","Target":"₹{:.2f}"
    }),
    use_container_width=True, hide_index=True
)

st.subheader("CHART CHECK")
symbol = st.selectbox("Select setup", signals["SYMBOL"].tolist())
row = signals.loc[signals["SYMBOL"] == symbol].iloc[0]
df = client.history(str(row["SECURITY_ID"]), timeframe=timeframe, days=90)
st_series = build_signal(df, rsi_limit=100, volume_multiple=0)["ST_SERIES"]

fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=df.index, open=df["open"], high=df["high"],
    low=df["low"], close=df["close"], name="Price"
))
fig.add_trace(go.Scatter(x=df.index, y=st_series, name="Supertrend", mode="lines"))
fig.update_layout(
    template="plotly_dark", paper_bgcolor="#07111f", plot_bgcolor="#07111f",
    height=520, margin=dict(l=10,r=10,t=30,b=10), xaxis_rangeslider_visible=False
)
st.plotly_chart(fig, use_container_width=True)

a,b,c,d = st.columns(4)
a.metric("ENTRY", f'₹{row["ENTRY"]:.2f}')
b.metric("TRAIL SL", f'₹{row["STOP"]:.2f}')
c.metric("TARGET", f'₹{row["TARGET"]:.2f}')
d.metric("RISK / SHARE", f'₹{row["ENTRY"]-row["STOP"]:.2f}')

st.caption(
    "Strategy: RSI below threshold + fresh bullish MACD crossover + high volume + price above Supertrend. "
    "Trail the stop below the Supertrend line. Signals only."
)
