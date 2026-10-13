
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
import pandas_market_calendars as mcal

from datetime import date, timedelta


# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="Stock Trend Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Stock Trend Dashboard")
st.caption(
    "Stock charts, technical indicators, trend signals, "
    "watchlist, and US market opening/closing countdown."
)

st.markdown(
    """
    <style>
    .signal-card {
        padding: 22px;
        border-radius: 14px;
        color: white;
        text-align: center;
        margin: 8px 0 18px 0;
    }
    .signal-card h2 {
        margin: 0;
        font-size: 30px;
    }
    .signal-card p {
        margin: 8px 0 0 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ==================================================
# MARKET OPEN/CLOSE COUNTDOWN
# ==================================================

@st.fragment(run_every="1s")
def show_market_clock():
    now = pd.Timestamp.now(tz="UTC")
    eastern_now = pd.Timestamp.now(tz="America/New_York")

    calendar = mcal.get_calendar("NYSE")

    schedule = calendar.schedule(
        start_date=eastern_now.date(),
        end_date=(eastern_now + pd.Timedelta(days=14)).date(),
    )

    current_session = None
    next_session = None

    for _, session in schedule.iterrows():
        market_open = session["market_open"]
        market_close = session["market_close"]

        if market_open <= now < market_close:
            current_session = session
            break

        if market_open > now and next_session is None:
            next_session = session

    st.subheader("🕒 US Stock Market Hours")

    if current_session is not None:
        opening = current_session["market_open"]
        closing = current_session["market_close"]

        seconds_left = max(
            0, int((closing - now).total_seconds())
        )
        hours, remainder = divmod(seconds_left, 3600)
        minutes, seconds = divmod(remainder, 60)

        col1, col2 = st.columns(2)

        st.success("🟢 MARKET IS OPEN")

        with col1:
            st.metric(
                "Today's opening time",
                opening.tz_convert(
                    "America/New_York"
                ).strftime("%I:%M %p ET"),
            )

        with col2:
            st.metric(
                "Market closes in",
                f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            )

        st.caption(
            "Scheduled closing: "
            + closing.tz_convert(
                "America/New_York"
            ).strftime("%I:%M %p ET")
        )

    elif next_session is not None:
        opening = next_session["market_open"]
        closing = next_session["market_close"]

        seconds_left = max(
            0, int((opening - now).total_seconds())
        )
        days, remainder = divmod(seconds_left, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.warning("🔴 MARKET IS CLOSED")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Market opens in",
                f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}",
            )

        with col2:
            st.metric(
                "Next closing time",
                closing.tz_convert(
                    "America/New_York"
                ).strftime("%b %d · %I:%M %p ET"),
            )

        st.caption(
            "Next opening: "
            + opening.tz_convert(
                "America/New_York"
            ).strftime("%A, %B %d at %I:%M %p ET")
        )

    else:
        st.info("The next market session could not be determined.")

    st.caption(
        "Uses the scheduled NYSE calendar, including holidays "
        "and early closes. Times are Eastern Time."
    )


show_market_clock()

st.divider()


# ==================================================
# SIDEBAR SETTINGS
# ==================================================

st.sidebar.header("⚙️ Dashboard Settings")

ticker = st.sidebar.text_input(
    "Stock ticker",
    value="MSFT",
    help="Examples: MSFT, AAPL, NVDA, TSLA, AMZN",
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1mo", "3mo", "6mo", "1y", "2y", "5y"],
    index=3,
)

interval = st.sidebar.selectbox(
    "Chart interval",
    ["1d", "1h", "30m", "15m"],
    index=0,
    help="Intraday history may be limited by the data provider.",
)

auto_refresh = st.sidebar.checkbox(
    "Automatically refresh stock data",
    value=False,
)

st.sidebar.caption(
    "Market countdown refreshes every second. "
    "Stock prices refresh when you reload or use auto-refresh."
)

refresh_clicked = st.sidebar.button(
    "🔄 Refresh stock data",
    use_container_width=True,
)


# ==================================================
# WATCHLIST
# ==================================================

st.sidebar.divider()
st.sidebar.subheader("⭐ Watchlist")

watchlist_text = st.sidebar.text_area(
    "Tickers separated by commas",
    value="MSFT, AAPL, NVDA, TSLA, AMZN",
    help="Example: MSFT, AAPL, NVDA",
)

watchlist = list(
    dict.fromkeys(
        item.strip().upper()
        for item in watchlist_text.split(",")
        if item.strip()
    )
)


# ==================================================
# STOCK DATA FUNCTIONS
# ==================================================

@st.cache_data(ttl=60)
def load_stock_data(symbol, selected_period, selected_interval):
    data = yf.download(
        symbol,
        period=selected_period,
        interval=selected_interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if data is None or data.empty:
        return pd.DataFrame()

    # Handle newer yfinance versions that may return
    # multi-level columns for a single ticker.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.loc[:, ~data.columns.duplicated()]
    data = data.dropna(subset=["Close"]).copy()

    if data.empty:
        return pd.DataFrame()

    data["SMA20"] = data["Close"].rolling(20).mean()
    data["SMA50"] = data["Close"].rolling(50).mean()

    change = data["Close"].diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.rolling(14).mean()
    avg_loss = losses.rolling(14).mean()

    relative_strength = avg_gain / avg_loss.replace(0, float("nan"))
    data["RSI"] = 100 - (100 / (1 + relative_strength))

    # Handle periods with no losses.
    data.loc[
        (avg_loss == 0) & (avg_gain > 0), "RSI"
    ] = 100

    data.loc[
        (avg_loss == 0) & (avg_gain == 0), "RSI"
    ] = 50

    return data


@st.cache_data(ttl=60)
def load_watchlist_data(symbols):
    results = []

    for symbol in symbols:
        try:
            history = yf.download(
                symbol,
                period="5d",
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False,
            )

            if history is None or history.empty:
                continue

            if isinstance(history.columns, pd.MultiIndex):
                history.columns = history.columns.get_level_values(0)

            history = history.loc[:, ~history.columns.duplicated()]
            closes = history["Close"].dropna()

            if len(closes) == 0:
                continue

            latest = float(closes.iloc[-1])

            if len(closes) >= 2:
                previous = float(closes.iloc[-2])
                change_pct = (
                    (latest - previous) / previous * 100
                    if previous != 0
                    else 0
                )
            else:
                change_pct = 0

            results.append({
                "Ticker": symbol,
                "Latest Close": latest,
                "Daily Change (%)": change_pct,
            })

        except Exception:
            continue

    return pd.DataFrame(results)


def detect_candle_pattern(data):
    if len(data) < 2:
        return "Not enough candle data"

    last = data.iloc[-1]

    open_price = float(last["Open"])
    close_price = float(last["Close"])
    high_price = float(last["High"])
    low_price = float(last["Low"])

    body = abs(close_price - open_price)
    full_range = high_price - low_price

    if full_range <= 0:
        return "No clear pattern"

    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price

    if body / full_range < 0.1:
        return "Doji — indecision"

    if lower_shadow > body * 2 and upper_shadow < body:
        return "Hammer-like candle"

    if upper_shadow > body * 2 and lower_shadow < body:
        return "Shooting-star-like candle"

    if close_price > open_price:
        return "Bullish candle"

    return "Bearish candle"


def analyze_stock(data):
    if data.empty:
        return "HOLD", 0, "No data available"

    latest = data.iloc[-1]
    price = float(latest["Close"])
    sma20 = latest["SMA20"]
    sma50 = latest["SMA50"]
    rsi = latest["RSI"]

    score = 0
    reasons = []

    if pd.notna(sma20):
        if price > float(sma20):
            score += 1
            reasons.append("Price is above SMA20")
        else:
            score -= 1
            reasons.append("Price is below SMA20")

    if pd.notna(sma20) and pd.notna(sma50):
        if float(sma20) > float(sma50):
            score += 1
            reasons.append("SMA20 is above SMA50")
        else:
            score -= 1
            reasons.append("SMA20 is below SMA50")

    if pd.notna(rsi):
        rsi_value = float(rsi)

        if rsi_value < 30:
            score += 1
            reasons.append("RSI is below 30")
        elif rsi_value > 70:
            score -= 1
            reasons.append("RSI is above 70")
        else:
            reasons.append("RSI is between 30 and 70")

    rsi_value = float(rsi) if pd.notna(rsi) else None

    if score >= 2 and (rsi_value is None or rsi_value < 70):
        signal = "BUY"
    elif score <= -1 or (
        rsi_value is not None and rsi_value >= 75
    ):
        signal = "SELL"
    else:
        signal = "HOLD"

    explanation = " • ".join(reasons) if reasons else "Not enough indicator data"

    return signal, score, explanation


# ==================================================
# MAIN STOCK DASHBOARD
# ==================================================

@st.fragment(run_every="60s" if auto_refresh else None)
def show_dashboard():
    if not ticker:
        st.warning("Enter a stock ticker in the sidebar.")
        return

    if refresh_clicked:
        st.cache_data.clear()

    with st.spinner(f"Loading {ticker} stock data..."):
        try:
            data = load_stock_data(ticker, period, interval)
        except Exception as error:
            st.error(f"Could not load stock data: {error}")
            return

    if data.empty:
        st.error(
            f"No stock data found for {ticker}. "
            "Check the ticker and try again."
        )
        return

    latest = data.iloc[-1]
    current_price = float(latest["Close"])

    if len(data) >= 2:
        previous_close = float(data.iloc[-2]["Close"])
        price_change = current_price - previous_close
        change_pct = (
            price_change / previous_close * 100
            if previous_close != 0
            else 0
        )
    else:
        price_change = 0
        change_pct = 0

    signal, score, explanation = analyze_stock(data)

    # Top metrics
    st.header(f"{ticker} Stock Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Latest price",
        f"${current_price:,.2f}",
        f"{price_change:+.2f} ({change_pct:+.2f}%)",
    )

    col2.metric(
        "SMA20",
        f"${float(latest['SMA20']):,.2f}"
        if pd.notna(latest["SMA20"])
        else "Not available",
    )

    col3.metric(
        "SMA50",
        f"${float(latest['SMA50']):,.2f}"
        if pd.notna(latest["SMA50"])
        else "Not available",
    )

    col4.metric(
        "RSI (14)",
        f"{float(latest['RSI']):.1f}"
        if pd.notna(latest["RSI"])
        else "Not available",
    )

    # Signal card
    if signal == "BUY":
        card_color = "linear-gradient(135deg, #087f5b, #20c997)"
        signal_icon = "🟢"
    elif signal == "SELL":
        card_color = "linear-gradient(135deg, #a61e4d, #f03e3e)"
        signal_icon = "🔴"
    else:
        card_color = "linear-gradient(135deg, #495057, #868e96)"
        signal_icon = "🟡"

    st.markdown(
        f"""
        <div class="signal-card" style="background: {card_color};">
            <h2>{signal_icon} {signal} SIGNAL</h2>
            <p>Technical score: {score}</p>
            <p>{explanation}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "This signal is based on simple technical rules. "
        "It is not a prediction or a guarantee of future prices."
    )

    # Price chart
    st.subheader("📊 Candlestick Chart")

    chart = go.Figure()

    chart.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name=ticker,
        )
    )

    chart.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA20"],
            mode="lines",
            name="SMA20",
        )
    )

    chart.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA50"],
            mode="lines",
            name="SMA50",
        )
    )

    chart.update_layout(
        height=550,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h"),
    )

    st.plotly_chart(chart, use_container_width=True)

    # RSI chart
    st.subheader("📉 Relative Strength Index (RSI)")

    rsi_chart = go.Figure()

    rsi_chart.add_trace(
        go.Scatter(
            x=data.index,
            y=data["RSI"],
            mode="lines",
            name="RSI",
        )
    )

    rsi_chart.add_hline(
        y=70,
        line_dash="dash",
        annotation_text="Potentially overbought (70)",
    )

    rsi_chart.add_hline(
        y=30,
        line_dash="dash",
        annotation_text="Potentially oversold (30)",
    )

    rsi_chart.update_layout(
        height=300,
        template="plotly_dark",
        yaxis=dict(range=[0, 100]),
        margin=dict(l=10, r=10, t=30, b=10),
    )

    st.plotly_chart(rsi_chart, use_container_width=True)

    # Latest candle pattern
    st.subheader("🕯️ Latest Candle Observation")
    st.write(detect_candle_pattern(data))

    # Recent price data
    with st.expander("View recent stock data"):
        display_data = data[
            ["Open", "High", "Low", "Close", "Volume", "SMA20", "SMA50", "RSI"]
        ].tail(20).sort_index(ascending=False)

        st.dataframe(
            display_data,
            use_container_width=True,
        )

    # Watchlist
    st.divider()
    st.subheader("⭐ Watchlist")

    if watchlist:
        with st.spinner("Loading watchlist..."):
            try:
                watchlist_data = load_watchlist_data(tuple(watchlist))
                if not watchlist_data.empty:
                    st.dataframe(
                        watchlist_data.style.format({
                            "Latest Close": "${:,.2f}",
                            "Daily Change (%)": "{:+.2f}%",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No watchlist prices were returned.")
            except Exception as error:
                st.warning(f"Could not load the watchlist: {error}")
    else:
        st.info("Add tickers in the sidebar to build your watchlist.")

    st.caption(
        "Data is supplied by Yahoo Finance and may be delayed. "
        "Technical indicators can be wrong and are not financial advice."
    )


show_dashboard()
