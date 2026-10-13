import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# ---------------- PAGE SETTINGS ----------------
st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide"
)

# Refresh dashboard every 60 seconds while open
st_autorefresh(interval=60 * 1000, key="stock_refresh")

st.title("📈 Stock Signal Dashboard")
st.caption("Automatic price refresh • Rule-based stock signals")

# ---------------- SIDEBAR ----------------
st.sidebar.header("Settings")

ticker_input = st.sidebar.text_input(
    "Stock ticker",
    value="MSFT"
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1mo", "3mo", "6mo", "1y", "2y"],
    index=2
)

interval = st.sidebar.selectbox(
    "Chart interval",
    ["1d", "1h", "30m", "15m"],
    index=0
)

watchlist = st.sidebar.multiselect(
    "Watchlist",
    ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN", "GOOGL", "META"],
    default=["MSFT", "AAPL", "NVDA"]
)

if st.sidebar.button("🔄 Refresh data now"):
    st.cache_data.clear()
    st.rerun()

# ---------------- GET STOCK DATA ----------------
@st.cache_data(ttl=60)
def get_stock_data(symbol, history_period, chart_interval):
    data = yf.download(
        symbol,
        period=history_period,
        interval=chart_interval,
        auto_adjust=True,
        progress=False
    )

    if data.empty:
        return pd.DataFrame()

    # Handle yfinance MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.loc[:, ~data.columns.duplicated()]
    data = data.dropna(subset=["Close"])

    return data

if not ticker_input:
    st.error("Enter a stock ticker.")
    st.stop()

try:
    data = get_stock_data(ticker_input, period, interval)
except Exception as error:
    st.error(f"Could not retrieve stock data: {error}")
    st.stop()

if data.empty or len(data) < 2:
    st.error(
        "No usable stock data was returned. Check the ticker, "
        "internet connection, and selected chart interval."
    )
    st.stop()

# ---------------- CALCULATE INDICATORS ----------------
close = data["Close"].squeeze()
high = data["High"].squeeze()
low = data["Low"].squeeze()

data["SMA20"] = close.rolling(20).mean()
data["SMA50"] = close.rolling(50).mean()

change = close.diff()
gain = change.clip(lower=0)
loss = -change.clip(upper=0)

avg_gain = gain.rolling(14).mean()
avg_loss = loss.rolling(14).mean()

relative_strength = avg_gain / avg_loss.replace(0, float("nan"))
data["RSI"] = 100 - (100 / (1 + relative_strength))
data["RSI"] = data["RSI"].fillna(50)

data["Volatility20"] = close.pct_change().rolling(20).std() * 100

latest_price = float(close.iloc[-1])
previous_price = float(close.iloc[-2])
price_change = latest_price - previous_price
percent_change = (
    (latest_price / previous_price - 1) * 100
    if previous_price else 0
)

latest_rsi = float(data["RSI"].iloc[-1])
sma20 = data["SMA20"].iloc[-1]
sma50 = data["SMA50"].iloc[-1]

# ---------------- SIGNAL RULES ----------------
score = 0
reasons = []

if pd.notna(sma20) and pd.notna(sma50):
    if latest_price > sma20:
        score += 1
        reasons.append("Price is above its 20-period average.")
    else:
        score -= 1
        reasons.append("Price is below its 20-period average.")

    if sma20 > sma50:
        score += 1
        reasons.append("20-period average is above the 50-period average.")
    else:
        score -= 1
        reasons.append("20-period average is below the 50-period average.")
else:
    reasons.append("Not enough history for both moving averages.")

if latest_rsi < 30:
    score += 1
    reasons.append("RSI is below 30, often considered oversold.")
elif latest_rsi > 70:
    score -= 1
    reasons.append("RSI is above 70, often considered overbought.")
else:
    reasons.append("RSI is between 30 and 70.")

if score >= 2 and latest_rsi < 70:
    signal = "BUY"
    signal_color = "#00e676"
elif score <= -1 or latest_rsi >= 75:
    signal = "SELL"
    signal_color = "#ff5252"
else:
    signal = "HOLD"
    signal_color = "#ffd740"

# ---------------- BLACK SIGNAL BOX ----------------
st.markdown(
    f"""
    <div style="
        background:#000000;
        border:2px solid #333333;
        border-radius:10px;
        padding:30px 15px;
        text-align:center;
        margin:10px 0 25px 0;
    ">
        <div style="
            color:#aaaaaa;
            font-size:14px;
            letter-spacing:4px;
        ">CURRENT STOCK SIGNAL</div>
        <div style="
            color:{signal_color};
            font-size:48px;
            font-weight:900;
            margin:12px 0;
        ">{signal}</div>
        <div style="color:#ffffff;font-size:17px;">
            {ticker_input} · ${latest_price:,.2f}
        </div>
        <div style="color:#999999;font-size:12px;margin-top:10px;">
            Rule-based analysis · Updated {datetime.now().strftime("%I:%M:%S %p")}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------- TOP METRICS ----------------
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Latest available price",
    f"${latest_price:,.2f}",
    f"{percent_change:+.2f}%"
)

col2.metric("RSI (14)", f"{latest_rsi:.1f}")

col3.metric(
    "SMA 20",
    f"${float(sma20):,.2f}" if pd.notna(sma20) else "N/A"
)

col4.metric(
    "SMA 50",
    f"${float(sma50):,.2f}" if pd.notna(sma50) else "N/A"
)

# ---------------- CHART ----------------
st.subheader(f"{ticker_input} Price Chart")

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=data.index,
    y=close,
    mode="lines",
    name="Price"
))

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["SMA20"],
    mode="lines",
    name="SMA 20"
))

fig.add_trace(go.Scatter(
    x=data.index,
    y=data["SMA50"],
    mode="lines",
    name="SMA 50"
))

fig.update_layout(
    template="plotly_dark",
    height=500,
    xaxis_title="Date",
    yaxis_title="Adjusted price",
    hovermode="x unified",
    legend_title="Indicator"
)

st.plotly_chart(fig, use_container_width=True)

# ---------------- SIGNAL EXPLANATION ----------------
with st.expander("Why did the app choose this signal?"):
    st.write(f"**Signal:** {signal}")
    st.write(f"**Indicator score:** {score}")
    for reason in reasons:
        st.write(f"- {reason}")

# ---------------- WATCHLIST ----------------
st.subheader("👀 Watchlist")

if watchlist:
    rows = []

    for symbol in watchlist:
        try:
            watch_data = get_stock_data(symbol, "1mo", "1d")

            if watch_data.empty or len(watch_data) < 2:
                rows.append({
                    "Ticker": symbol,
                    "Price": "Unavailable",
                    "Daily Change": "N/A"
                })
                continue

            if isinstance(watch_data.columns, pd.MultiIndex):
                watch_data.columns = watch_data.columns.get_level_values(0)

            watch_close = watch_data["Close"].squeeze()
            price = float(watch_close.iloc[-1])
            old_price = float(watch_close.iloc[-2])
            daily_change = (price / old_price - 1) * 100 if old_price else 0

            rows.append({
                "Ticker": symbol,
                "Price": f"${price:,.2f}",
                "Daily Change": f"{daily_change:+.2f}%"
            })

        except Exception:
            rows.append({
                "Ticker": symbol,
                "Price": "Unavailable",
                "Daily Change": "N/A"
            })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True
    )

# ---------------- IMPORTANT NOTES ----------------
st.caption(
    "Signals are generated by simple technical rules, not a trained AI model. "
    "They are not guaranteed predictions or personalized financial advice."
)

st.caption(
    "Automatic refresh works while the dashboard is running and open. "
    "It does not guarantee 24/7 background monitoring. "
    "Yahoo Finance data can be delayed, incomplete, or unavailable."
)
