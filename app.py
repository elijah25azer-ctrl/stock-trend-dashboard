
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Stock Signal Dashboard")
st.caption("Stock signals • Automatic refresh every 60 seconds while active")

# ---------------- SETTINGS ----------------
st.sidebar.header("Settings")

ticker = st.sidebar.text_input(
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

if not ticker:
    st.warning("Enter a stock ticker in the sidebar.")
    st.stop()


# ---------------- STOCK DATA ----------------
@st.cache_data(ttl=60)
def get_stock_data(symbol, history, interval_value):
    df = yf.download(
        symbol,
        period=history,
        interval=interval_value,
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        return pd.DataFrame()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.loc[:, ~df.columns.duplicated()]
    return df.dropna(subset=["Close"])


# ---------------- DASHBOARD ----------------
@st.fragment(run_every="60s")
def show_dashboard():
    try:
        data = get_stock_data(ticker, period, interval)
    except Exception as e:
        st.error(f"Could not download stock data: {e}")
        return

    if data.empty or len(data) < 2:
        st.error(
            "No stock data found. Check the ticker and try another interval."
        )
        return

    close = data["Close"].squeeze()
    data["SMA20"] = close.rolling(20).mean()
    data["SMA50"] = close.rolling(50).mean()

    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.rolling(14).mean()
    avg_loss = losses.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    data["RSI"] = (100 - (100 / (1 + rs))).fillna(50)

    price = float(close.iloc[-1])
    previous = float(close.iloc[-2])
    percent_change = (
        (price / previous - 1) * 100 if previous else 0
    )

    rsi = float(data["RSI"].iloc[-1])
    sma20 = data["SMA20"].iloc[-1]
    sma50 = data["SMA50"].iloc[-1]

    # -------- SIGNAL CALCULATION --------
    score = 0
    reasons = []

    if pd.notna(sma20) and pd.notna(sma50):
        if price > float(sma20):
            score += 1
            reasons.append("Price is above its 20-period average.")
        else:
            score -= 1
            reasons.append("Price is below its 20-period average.")

        if float(sma20) > float(sma50):
            score += 1
            reasons.append("20-period average is above the 50-period average.")
        else:
            score -= 1
            reasons.append("20-period average is below the 50-period average.")
    else:
        reasons.append("More historical data is needed for moving averages.")

    if rsi < 30:
        score += 1
        reasons.append("RSI is below 30.")
    elif rsi > 70:
        score -= 1
        reasons.append("RSI is above 70.")
    else:
        reasons.append("RSI is between 30 and 70.")

    if score >= 2 and rsi < 70:
        signal = "BUY"
        signal_color = "#00e676"
    elif score <= -1 or rsi >= 75:
        signal = "SELL"
        signal_color = "#ff5252"
    else:
        signal = "HOLD"
        signal_color = "#ffd740"

    # -------- BLACK SIGNAL BOX --------
    st.markdown(
        f"""
        <div style="
            background:#000000;
            border:2px solid #333333;
            border-radius:10px;
            padding:28px 15px;
            text-align:center;
            margin:10px 0 24px 0;
        ">
            <div style="
                color:#aaaaaa;
                font-size:14px;
                letter-spacing:4px;
            ">STOCK SIGNAL</div>
            <div style="
                color:{signal_color};
                font-size:48px;
                font-weight:900;
                margin:12px 0;
            ">{signal}</div>
            <div style="color:white;font-size:18px;">
                {ticker} · ${price:,.2f}
            </div>
            <div style="color:#999999;font-size:12px;margin-top:10px;">
                Updated {datetime.now().strftime("%I:%M:%S %p")}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # -------- METRICS --------
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Latest price", f"${price:,.2f}", f"{percent_change:+.2f}%")
    c2.metric("RSI (14)", f"{rsi:.1f}")
    c3.metric(
        "SMA 20",
        f"${float(sma20):,.2f}" if pd.notna(sma20) else "N/A"
    )
    c4.metric(
        "SMA 50",
        f"${float(sma50):,.2f}" if pd.notna(sma50) else "N/A"
    )

    # -------- CHART --------
    st.subheader(f"{ticker} Price Chart")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data.index, y=close, mode="lines", name="Price"
    ))
    fig.add_trace(go.Scatter(
        x=data.index, y=data["SMA20"], mode="lines", name="SMA 20"
    ))
    fig.add_trace(go.Scatter(
        x=data.index, y=data["SMA50"], mode="lines", name="SMA 50"
    ))

    fig.update_layout(
        template="plotly_dark",
        height=480,
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Price"
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Why did the app choose this signal?"):
        st.write(f"Signal: **{signal}**")
        st.write(f"Indicator score: **{score}**")
        for reason in reasons:
            st.write(f"- {reason}")

    # -------- WATCHLIST --------
    st.subheader("👀 Watchlist")

    rows = []

    for symbol in watchlist:
        try:
            watch_data = get_stock_data(symbol, "1mo", "1d")

            if watch_data.empty or len(watch_data) < 2:
                rows.append({
                    "Ticker": symbol,
                    "Price": "Unavailable",
                    "Daily change": "N/A"
                })
                continue

            watch_close = watch_data["Close"].squeeze()
            latest = float(watch_close.iloc[-1])
            prior = float(watch_close.iloc[-2])
            daily = (latest / prior - 1) * 100 if prior else 0

            rows.append({
                "Ticker": symbol,
                "Price": f"${latest:,.2f}",
                "Daily change": f"{daily:+.2f}%"
            })

        except Exception:
            rows.append({
                "Ticker": symbol,
                "Price": "Unavailable",
                "Daily change": "N/A"
            })

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    st.caption(
        "Signals are based on simple technical rules, not guaranteed predictions."
    )


show_dashboard()
