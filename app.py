
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ================= PAGE SETTINGS =================
st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Stock Signal Dashboard")
st.caption("Candlestick charts • Stock signals • Auto-refresh")

# ================= SIDEBAR =================
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
    "Candlestick interval",
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

if not ticker:
    st.warning("Enter a stock ticker in the sidebar.")
    st.stop()


# ================= STOCK DATA =================
@st.cache_data(ttl=60)
def get_stock_data(symbol, history, chart_interval):
    df = yf.download(
        symbol,
        period=history,
        interval=chart_interval,
        auto_adjust=True,
        progress=False
    )

    if df.empty:
        return pd.DataFrame()

    # Handle different yfinance column formats
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.loc[:, ~df.columns.duplicated()]
    return df.dropna(subset=["Close"])


# ================= MAIN DASHBOARD =================
@st.fragment(run_every="60s")
def show_dashboard():

    try:
        data = get_stock_data(ticker, period, interval)
    except Exception as e:
        st.error(f"Could not retrieve stock data: {e}")
        return

    if data.empty or len(data) < 2:
        st.error(
            "No stock data found. Check the ticker or select another interval."
        )
        return

    required_columns = ["Open", "High", "Low", "Close"]

    if not all(column in data.columns for column in required_columns):
        st.error("The downloaded data is missing candle price information.")
        return

    # ================= INDICATORS =================
    close = data["Close"].squeeze()

    data["SMA20"] = close.rolling(20).mean()
    data["SMA50"] = close.rolling(50).mean()

    price_change = close.diff()
    gains = price_change.clip(lower=0)
    losses = -price_change.clip(upper=0)

    avg_gain = gains.rolling(14).mean()
    avg_loss = losses.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    data["RSI"] = (
        100 - (100 / (1 + rs))
    ).fillna(50)

    price = float(close.iloc[-1])
    previous_price = float(close.iloc[-2])

    percent_change = (
        (price / previous_price - 1) * 100
        if previous_price else 0
    )

    rsi = float(data["RSI"].iloc[-1])
    sma20 = data["SMA20"].iloc[-1]
    sma50 = data["SMA50"].iloc[-1]

    # ================= BUY / SELL / HOLD RULES =================
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
            reasons.append("SMA 20 is above SMA 50.")
        else:
            score -= 1
            reasons.append("SMA 20 is below SMA 50.")

    else:
        reasons.append(
            "More historical data is needed for moving averages."
        )

    if rsi < 30:
        score += 1
        reasons.append("RSI is below 30, often considered oversold.")
    elif rsi > 70:
        score -= 1
        reasons.append("RSI is above 70, often considered overbought.")
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

    # ================= BLACK SIGNAL BOX =================
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
            ">CURRENT STOCK SIGNAL</div>

            <div style="
                color:{signal_color};
                font-size:48px;
                font-weight:900;
                margin:12px 0;
            ">{signal}</div>

            <div style="color:#ffffff;font-size:18px;">
                {ticker} · ${price:,.2f}
            </div>

            <div style="color:#999999;font-size:12px;margin-top:10px;">
                Updated {datetime.now().strftime("%I:%M:%S %p")}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ================= PRICE METRICS =================
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Latest available price",
        f"${price:,.2f}",
        f"{percent_change:+.2f}%"
    )

    c2.metric("RSI (14)", f"{rsi:.1f}")

    c3.metric(
        "SMA 20",
        f"${float(sma20):,.2f}" if pd.notna(sma20) else "N/A"
    )

    c4.metric(
        "SMA 50",
        f"${float(sma50):,.2f}" if pd.notna(sma50) else "N/A"
    )

    # ================= CANDLESTICK CHART =================
    st.subheader(f"🕯️ {ticker} Candlestick Chart")

    fig = go.Figure()

    # Green candle = close above open
    # Red candle = close below open
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Candles",
            increasing_line_color="#00e676",
            decreasing_line_color="#ff5252"
        )
    )

    # SMA 20
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA20"],
            mode="lines",
            name="SMA 20",
            line=dict(color="#ffd740", width=2)
        )
    )

    # SMA 50
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA50"],
            mode="lines",
            name="SMA 50",
            line=dict(color="#40c4ff", width=2)
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=600,
        xaxis_title="Date",
        yaxis_title="Stock Price ($)",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend_title="Indicators",
        margin=dict(l=10, r=10, t=30, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ================= SIGNAL EXPLANATION =================
    with st.expander("Why did the app choose this signal?"):
        st.write(f"**Signal:** {signal}")
        st.write(f"**Indicator score:** {score}")

        for reason in reasons:
            st.write(f"- {reason}")

    # ================= WATCHLIST =================
    st.subheader("👀 Stock Watchlist")

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

            watch_close = watch_data["Close"].squeeze()

            latest = float(watch_close.iloc[-1])
            previous = float(watch_close.iloc[-2])

            daily_change = (
                (latest / previous - 1) * 100
                if previous else 0
            )

            rows.append({
                "Ticker": symbol,
                "Price": f"${latest:,.2f}",
                "Daily Change": f"{daily_change:+.2f}%"
            })

        except Exception:
            rows.append({
                "Ticker": symbol,
                "Price": "Unavailable",
                "Daily Change": "N/A"
            })

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True
        )

    # ================= DISCLAIMER =================
    st.caption(
        "Signals use simple technical rules and are not guaranteed predictions "
        "or personalized financial advice."
    )

    st.caption(
        "Auto-refresh runs every 60 seconds while the app is active. "
        "It does not guarantee continuous 24/7 monitoring. "
        "Market data may be delayed or unavailable."
    )


show_dashboard()
