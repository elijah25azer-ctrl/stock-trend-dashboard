
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Stock Decision Dashboard",
    page_icon="📈",
    layout="wide"
)

DEFAULT_WATCHLIST = [
    "MSFT", "NVDA", "AAPL", "AMZN", "GOOGL",
    "META", "TSLA", "AMD", "SPY", "QQQ"
]

st.title("📈 Stock Decision Dashboard")
st.caption(
    "Stock chart research assistant using technical indicators. "
    "Signals are estimates, not guaranteed predictions."
)

# SIDEBAR SETTINGS
with st.sidebar:
    st.header("Stock settings")

    ticker_input = st.text_input(
        "Stock ticker",
        value="MSFT",
        help="Examples: MSFT, NVDA, AAPL, TSLA, SPY"
    )

    period = st.selectbox(
        "Chart history",
        ["3mo", "6mo", "1y", "2y", "5y"],
        index=2
    )

    interval = st.selectbox(
        "Price interval",
        ["1d", "1wk"],
        index=0
    )

    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Popular stocks")

    selected_watch = st.selectbox(
        "Choose a ticker",
        DEFAULT_WATCHLIST
    )

    if st.button("Use selected ticker", use_container_width=True):
        st.session_state["ticker_override"] = selected_watch
        st.rerun()

ticker = st.session_state.get(
    "ticker_override", ticker_input
).strip().upper()

if not ticker:
    st.warning("Enter a stock ticker.")
    st.stop()

# DOWNLOAD STOCK DATA
@st.cache_data(ttl=300, show_spinner=False)
def load_history(symbol, selected_period, selected_interval):
    data = yf.download(
        symbol,
        period=selected_period,
        interval=selected_interval,
        auto_adjust=True,
        progress=False,
        threads=False
    )

    if data.empty:
        return pd.DataFrame()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data.dropna(subset=["Close"]).copy()


try:
    with st.spinner(f"Studying chart data for {ticker}..."):
        df = load_history(ticker, period, interval)
except Exception as exc:
    st.error("Could not load stock data. Check the ticker and try again.")
    st.caption(f"Technical detail: {exc}")
    st.stop()

if df.empty or len(df) < 25:
    st.error(
        "Not enough price history was returned. "
        "Check the ticker or choose a longer chart history."
    )
    st.stop()

# TECHNICAL INDICATORS
df["SMA20"] = df["Close"].rolling(20).mean()
df["SMA50"] = df["Close"].rolling(50).mean()

delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()

rs = gain / loss.replace(0, float("nan"))
df["RSI14"] = (
    100 - (100 / (1 + rs))
).fillna(50)

df["Volatility20"] = (
    df["Close"].pct_change().rolling(20).std()
    * (252 ** 0.5 if interval == "1d" else 52 ** 0.5)
)

latest = df.iloc[-1]
previous = df.iloc[-2]

price = float(latest["Close"])
previous_price = float(previous["Close"])

sma20 = (
    float(latest["SMA20"])
    if pd.notna(latest["SMA20"]) else price
)

sma50 = (
    float(latest["SMA50"])
    if pd.notna(latest["SMA50"]) else sma20
)

rsi = float(latest["RSI14"])

recent_low = (
    float(df["Low"].tail(20).min())
    if "Low" in df.columns
    else float(df["Close"].tail(20).min())
)

five_period_change = (
    (price / float(df["Close"].iloc[-6]) - 1) * 100
)

# ANALYZE THE CHART
# These are fixed rules, not a trained AI prediction model.
score = 0
reasons = []

if price > sma20:
    score += 1
    reasons.append(
        "Positive sign: price is above its 20-period average."
    )
else:
    score -= 1
    reasons.append(
        "Negative sign: price is below its 20-period average."
    )

if sma20 > sma50:
    score += 1
    reasons.append(
        "Positive trend: the 20-period average is above the 50-period average."
    )
else:
    score -= 1
    reasons.append(
        "Weaker trend: the 20-period average is below the 50-period average."
    )

if 45 <= rsi <= 65:
    score += 1
    reasons.append(
        f"RSI is {rsi:.1f}, within the dashboard's middle momentum range."
    )
elif rsi < 35:
    reasons.append(
        f"RSI is {rsi:.1f}. Weak momentum does not guarantee a rebound."
    )
elif rsi >= 75:
    score -= 1
    reasons.append(
        f"RSI is {rsi:.1f}, indicating potentially stretched momentum."
    )
elif rsi > 65:
    reasons.append(
        f"RSI is {rsi:.1f}; momentum may be getting stretched."
    )
else:
    reasons.append(
        f"RSI is {rsi:.1f}, outside the preferred middle range."
    )

if five_period_change > 0:
    score += 1
    reasons.append(
        f"Price rose {five_period_change:.2f}% over the last five data points."
    )
elif five_period_change < 0:
    score -= 1
    reasons.append(
        f"Price fell {abs(five_period_change):.2f}% over the last five data points."
    )

# BUY / HOLD / SELL SIGNAL
if score >= 2 and rsi < 70:
    signal = "BUY WATCH"
    explanation = (
        "Several indicators lean positive. Research further; "
        "this is not a guarantee or an instruction to buy."
    )
elif score <= -1 or rsi >= 75:
    signal = "SELL / AVOID NEW ENTRY"
    explanation = (
        "The rules detect weakness or potentially stretched momentum. "
        "This does not guarantee the stock will fall."
    )
else:
    signal = "HOLD / WAIT"
    explanation = (
        "The indicators are mixed or do not show a clear setup."
    )

# TOP BUTTON
st.subheader(f"{ticker} — Stock Decision Center")

if st.button(
    f"📊 CHECK SIGNAL: {signal}",
    key="top_signal_button",
    use_container_width=True,
    type="primary"
):
    st.session_state["show_signal_details"] = (
        not st.session_state.get("show_signal_details", False)
    )

if st.session_state.get("show_signal_details", False):
    st.info(explanation)

    st.markdown("**Chart analysis:**")
    for reason in reasons:
        st.write(f"• {reason}")

st.caption(
    f"Latest data point returned: {df.index[-1].date()}. "
    "Market data may be delayed or incomplete."
)

# MAIN DASHBOARD METRICS
col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Latest adjusted close",
    f"${price:,.2f}",
    f"{(price / previous_price - 1) * 100:+.2f}% vs prior point"
)

col2.metric("Current signal", signal)
col3.metric("RSI (14)", f"{rsi:.1f}")
col4.metric("20-period average", f"${sma20:,.2f}")

st.info(explanation)

st.markdown("### Why the dashboard gave this signal")

for reason in reasons:
    st.write(f"• {reason}")

# EXAMPLE RISK AND TARGET LEVELS
if {"High", "Low"}.issubset(df.columns):
    movement = float(
        (df["High"] - df["Low"]).tail(14).mean()
    )
else:
    movement = float(
        df["Close"].diff().abs().tail(14).mean()
    )

if pd.isna(movement):
    movement = price * 0.02

movement = max(movement, price * 0.005)

stop_level = max(
    0.01,
    min(recent_low, price - 1.5 * movement)
)

risk_per_share = max(
    price - stop_level,
    price * 0.01
)

target_level = price + 2 * risk_per_share

st.markdown("### Example levels to research")

col1, col2, col3 = st.columns(3)

col1.metric("Reference price", f"${price:,.2f}")

col2.metric(
    "Illustrative risk level",
    f"${stop_level:,.2f}",
    help="Historical-price example, not a guaranteed protection level."
)

col3.metric(
    "Illustrative target",
    f"${target_level:,.2f}",
    help="Mathematical example, not a price prediction."
)

st.caption(
    "These levels are mechanical examples based on historical prices. "
    "Actual prices can move beyond them."
)

# PRICE CHART
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["Close"],
        mode="lines",
        name="Adjusted close"
    )
)

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["SMA20"],
        mode="lines",
        name="20-period average"
    )
)

fig.add_trace(
    go.Scatter(
        x=df.index,
        y=df["SMA50"],
        mode="lines",
        name="50-period average"
    )
)

fig.add_hline(
    y=stop_level,
    line_dash="dash",
    annotation_text="Example risk level"
)

fig.add_hline(
    y=target_level,
    line_dash="dash",
    annotation_text="Example target"
)

fig.update_layout(
    height=480,
    xaxis_title="Date",
    yaxis_title="Price (USD)",
    legend_orientation="h",
    legend_y=1.08,
    margin=dict(l=10, r=10, t=50, b=10)
)

st.plotly_chart(fig, use_container_width=True)

# COMPARE POPULAR STOCKS
st.divider()
st.subheader("Compare popular stocks")

compare_symbols = st.multiselect(
    "Choose stocks to compare",
    DEFAULT_WATCHLIST,
    default=["MSFT", "NVDA", "AAPL", "TSLA"]
)

rows = []

if compare_symbols:
    with st.spinner("Loading comparison data..."):
        for symbol in compare_symbols:
            try:
                hist = load_history(symbol, "1mo", "1d")

                if len(hist) >= 2:
                    values = hist["Close"].dropna()

                    rows.append({
                        "Ticker": symbol,
                        "Latest close": round(float(values.iloc[-1]), 2),
                        "Last data-point change (%)": round(
                            (float(values.iloc[-1]) /
                             float(values.iloc[-2]) - 1) * 100, 2
                        ),
                        "1-month change (%)": round(
                            (float(values.iloc[-1]) /
                             float(values.iloc[0]) - 1) * 100, 2
                        )
                    })
            except Exception:
                continue

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Comparison data unavailable. Try refreshing later.")

# EXPLANATION
with st.expander("How this decision system works"):
    st.write(
        "The dashboard studies price versus its 20-period average, "
        "the 20-period versus 50-period average, RSI (14), "
        "and recent price movement."
    )

    st.write(
        "This is a transparent rule-based system, not a trained AI model. "
        "It has not been proven profitable and does not calculate a "
        "reliable probability that a stock will rise or fall."
    )

    st.write(
        "BUY WATCH means indicators lean positive. HOLD / WAIT means "
        "the setup is unclear. SELL / AVOID NEW ENTRY means the rules "
        "detect weakness or potentially stretched momentum. These signals can be wrong."
    )

    st.write(
        "The app does not place trades or know your personal financial situation. "
        "Verify prices independently and discuss real investing decisions "
        "with a trusted adult or qualified financial professional."
    )

st.divider()

st.caption(
    "Educational use only • No guaranteed predictions • "
    "Not a recommendation to buy or sell any specific security"
)

st.caption(
    "Dashboard rendered " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)
