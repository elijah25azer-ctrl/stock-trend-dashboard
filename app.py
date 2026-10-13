import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Stock Trend Dashboard", page_icon="📈", layout="wide")

DEFAULT_WATCHLIST = ["MSFT", "NVDA", "AAPL", "AMZN", "GOOGL", "META", "TSLA", "AMD"]

st.title("📈 Stock Trend Dashboard")
st.caption("An educational dashboard that studies recent stock-price trends. It cannot predict the future or guarantee profits.")

with st.sidebar:
    st.header("Settings")
    ticker_input = st.text_input("Stock ticker", value="MSFT", help="Examples: MSFT, NVDA, AAPL, AMZN, GOOGL")
    period = st.selectbox("Chart history", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    interval = st.selectbox("Price interval", ["1d", "1wk"], index=0)
    refresh = st.button("🔄 Refresh data", use_container_width=True)
    st.divider()
    st.subheader("Watchlist")
    st.caption("Choose a stock to inspect.")
    selected_watch = st.selectbox("Popular stocks", DEFAULT_WATCHLIST, index=0)
    if st.button("Use watchlist stock", use_container_width=True):
        ticker_input = selected_watch

ticker = (ticker_input or "").strip().upper()
if not ticker:
    st.warning("Enter a stock ticker in the sidebar.")
    st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def load_history(symbol, selected_period, selected_interval, refresh_token):
    data = yf.download(
        symbol,
        period=selected_period,
        interval=selected_interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    if data.empty:
        return pd.DataFrame()
    # yfinance may return a MultiIndex column layout in some versions.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(subset=["Close"])

with st.spinner(f"Loading {ticker} price history..."):
    try:
        # Changing refresh_token bypasses Streamlit's cache when Refresh is clicked.
        data = load_history(ticker, period, interval, int(refresh))
    except Exception as exc:
        st.error(f"Could not load market data. Check your internet connection and ticker. Details: {exc}")
        st.stop()

if data.empty or len(data) < 5:
    st.error("No usable price history was found. Check the ticker (for example, MSFT) and try again.")
    st.stop()

close = data["Close"].astype(float).dropna()
last_price = float(close.iloc[-1])
prior_price = float(close.iloc[-2])
day_change = (last_price / prior_price - 1) * 100 if prior_price else 0.0
change_period = (last_price / float(close.iloc[0]) - 1) * 100 if float(close.iloc[0]) else 0.0
sma20_series = close.rolling(20).mean()
sma50_series = close.rolling(50).mean()
sma20 = float(sma20_series.iloc[-1]) if pd.notna(sma20_series.iloc[-1]) else None
sma50 = float(sma50_series.iloc[-1]) if pd.notna(sma50_series.iloc[-1]) else None

delta = close.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / loss.replace(0, float("nan"))
rsi_series = 100 - (100 / (1 + rs))
rsi_now = float(rsi_series.iloc[-1]) if pd.notna(rsi_series.iloc[-1]) else None

score = 0
reasons = []
if sma20 is not None:
    if last_price > sma20:
        score += 1
        reasons.append("Latest price is above its 20-period moving average (positive trend sign).")
    else:
        score -= 1
        reasons.append("Latest price is below its 20-period moving average (negative trend sign).")
if sma20 is not None and sma50 is not None:
    if sma20 > sma50:
        score += 1
        reasons.append("20-period average is above the 50-period average (positive trend sign).")
    else:
        score -= 1
        reasons.append("20-period average is below the 50-period average (negative trend sign).")
if len(close) >= 6:
    five_change = (float(close.iloc[-1]) / float(close.iloc[-6]) - 1) * 100
    if five_change > 0:
        score += 1
        reasons.append(f"Price is up {five_change:.2f}% over the last 5 data points.")
    elif five_change < 0:
        score -= 1
        reasons.append(f"Price is down {abs(five_change):.2f}% over the last 5 data points.")
if rsi_now is not None:
    if 45 <= rsi_now <= 65:
        score += 1
        reasons.append(f"RSI is {rsi_now:.1f}, within a moderate momentum range.")
    elif rsi_now < 30:
        reasons.append(f"RSI is {rsi_now:.1f}; the stock may be oversold, but it can keep falling.")
    elif rsi_now > 70:
        reasons.append(f"RSI is {rsi_now:.1f}; the stock may be overbought, but it can keep rising.")

if score >= 2:
    signal = "UPWARD TREND"
    signal_color = "🟢"
    signal_desc = "Current indicators lean upward. This is not a promise that the price will rise."
elif score <= -2:
    signal = "DOWNWARD TREND"
    signal_color = "🔴"
    signal_desc = "Current indicators lean downward. This is not a promise that the price will fall."
else:
    signal = "MIXED / NO CLEAR SIGNAL"
    signal_color = "🟡"
    signal_desc = "The indicators do not agree strongly. Consider waiting for more information rather than treating this as a prediction."

last_date = data.index[-1]
try:
    last_date_text = last_date.strftime("%b %d, %Y")
except Exception:
    last_date_text = str(last_date)

st.subheader(f"{ticker} overview")
st.caption(f"Latest data point available: {last_date_text}. Market data may be delayed; this app does not promise real-time quotes.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Latest adjusted close", f"${last_price:,.2f}", f"{day_change:+.2f}% vs. prior data point")
m2.metric(f"Change across selected history", f"{change_period:+.2f}%")
m3.metric("20-period average", f"${sma20:,.2f}" if sma20 is not None else "Not enough data")
m4.metric("RSI (14)", f"{rsi_now:.1f}" if rsi_now is not None else "Not enough data")

st.divider()
left, right = st.columns([2, 1], gap="large")
with left:
    st.subheader("Price chart")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data.index, y=close, mode="lines", name="Adjusted close"))
    if sma20_series.notna().any():
        fig.add_trace(go.Scatter(x=data.index, y=sma20_series, mode="lines", name="20-period average"))
    if sma50_series.notna().any():
        fig.add_trace(go.Scatter(x=data.index, y=sma50_series, mode="lines", name="50-period average"))
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=25, b=10),
        xaxis_title="Date",
        yaxis_title="Price (USD)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Trend indicator")
    st.markdown(f"## {signal_color} {signal}")
    st.write(signal_desc)
    st.caption("This label is produced by a simple rule-based score—not an AI model or a validated probability forecast.")
    st.markdown("**What the indicators say**")
    for reason in reasons:
        st.write(f"• {reason}")
    if sma50 is not None:
        st.write(f"50-period average: **${sma50:,.2f}**")
    if rsi_now is not None:
        if rsi_now < 30:
            st.info("RSI below 30 can indicate unusually weak recent momentum. It does not mean a rebound is guaranteed.")
        elif rsi_now > 70:
            st.info("RSI above 70 can indicate unusually strong recent momentum. It does not mean a drop is guaranteed.")

st.divider()
st.subheader("Compare popular stocks")
st.caption("This table compares recent price changes. Select a symbol in the sidebar to see its chart and trend indicators.")
compare_symbols = st.multiselect("Stocks to compare", DEFAULT_WATCHLIST, default=["MSFT", "NVDA", "AAPL", "TSLA"])
rows = []
if compare_symbols:
    with st.spinner("Loading comparison data..."):
        for symbol in compare_symbols:
            try:
                hist = yf.download(symbol, period="1mo", interval="1d", auto_adjust=True, progress=False, threads=False)
                if isinstance(hist.columns, pd.MultiIndex):
                    hist.columns = hist.columns.get_level_values(0)
                vals = hist["Close"].dropna() if not hist.empty else pd.Series(dtype=float)
                if len(vals) >= 2:
                    rows.append({
                        "Ticker": symbol,
                        "Latest close": round(float(vals.iloc[-1]), 2),
                        "Last data-point change (%)": round((float(vals.iloc[-1]) / float(vals.iloc[-2]) - 1) * 100, 2),
                        "1-month change (%)": round((float(vals.iloc[-1]) / float(vals.iloc[0]) - 1) * 100, 2),
                    })
            except Exception:
                continue
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Comparison data was unavailable. Try refreshing later.")

with st.expander("How to read this dashboard"):
    st.markdown("""
    - **Adjusted close:** historical closing price adjusted for events such as splits and dividends.
    - **Moving average:** average price over a number of recent data points; it helps summarize trend, but reacts slowly.
    - **RSI:** a momentum indicator from 0 to 100. Low or high readings can persist and are not automatic buy/sell signals.
    - **UPWARD / DOWNWARD / MIXED:** a basic score combining a few indicators. It is not a guaranteed forecast and has not been proven to make money.
    - **Data timing:** quotes can be delayed, and data providers can have outages. Verify current quotes and order details in your brokerage app.
    """)

st.warning("Risk reminder: stocks can move suddenly because of news, earnings, and broader market conditions. This dashboard is for learning only, not financial advice. Never invest money you need for essentials, and do not rely on one signal to make a decision.")
st.caption(f"Dashboard rendered {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} on your computer.")
