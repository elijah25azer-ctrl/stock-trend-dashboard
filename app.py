
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# --------------------------------------------------
# PAGE SETTINGS
# --------------------------------------------------

st.set_page_config(
    page_title="AI Stock Signal Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 AI Stock Signal Dashboard")
st.caption(
    "Stock prices and technical indicators for educational purposes. "
    "Signals are not guarantees of future performance."
)

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.header("Dashboard Settings")

ticker = st.sidebar.text_input(
    "Stock ticker",
    value="MSFT",
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1mo", "3mo", "6mo", "1y", "2y"],
    index=1,
)

interval = st.sidebar.selectbox(
    "Chart interval",
    ["1d", "1h", "30m", "15m"],
    index=0,
)

watchlist_text = st.sidebar.text_input(
    "Watchlist (comma-separated)",
    value="MSFT, GOOGL, AAPL, NVDA",
)

auto_refresh = st.sidebar.toggle(
    "Refresh every 60 seconds",
    value=False,
)

if st.sidebar.button("🔄 Refresh now", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Yahoo Finance limits intraday history.
if interval in ["1h", "30m", "15m"] and period in ["1y", "2y"]:
    st.sidebar.warning(
        "Intraday data has limited history. "
        "The app will use the selected period, but Yahoo Finance "
        "may return less data than requested."
    )

# --------------------------------------------------
# DOWNLOAD STOCK DATA
# --------------------------------------------------

@st.cache_data(ttl=60)
def download_stock_data(symbol, selected_period, selected_interval):
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

    # Handle Yahoo Finance MultiIndex columns.
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.loc[:, ~data.columns.duplicated()]
    data = data.copy()

    required_columns = ["Open", "High", "Low", "Close", "Volume"]

    for column in required_columns:
        if column not in data.columns:
            return pd.DataFrame()

    for column in required_columns:
        data[column] = pd.to_numeric(
            data[column], errors="coerce"
        )

    data = data.dropna(subset=["Open", "High", "Low", "Close"])

    return data


# --------------------------------------------------
# TECHNICAL INDICATORS
# --------------------------------------------------

def calculate_indicators(data):
    data = data.copy()

    data["SMA20"] = data["Close"].rolling(
        window=20, min_periods=20
    ).mean()

    data["SMA50"] = data["Close"].rolling(
        window=50, min_periods=50
    ).mean()

    delta = data["Close"].diff()

    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    relative_strength = average_gain / average_loss

    data["RSI"] = 100 - (
        100 / (1 + relative_strength)
    )

    # Handle prices that have not changed during the RSI period.
    no_movement = (average_gain == 0) & (average_loss == 0)
    data.loc[no_movement, "RSI"] = 50

    only_gains = (average_gain > 0) & (average_loss == 0)
    data.loc[only_gains, "RSI"] = 100

    only_losses = (average_gain == 0) & (average_loss > 0)
    data.loc[only_losses, "RSI"] = 0

    return data


# --------------------------------------------------
# SIGNAL RULES
# --------------------------------------------------

def get_signal(data):
    if data.empty or len(data) < 50:
        return "INSUFFICIENT DATA", [
            "At least 50 price candles are needed."
        ]

    last = data.iloc[-1]
    previous = data.iloc[-2]

    close = last["Close"]
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]
    rsi = last["RSI"]

    if pd.isna(sma20) or pd.isna(sma50) or pd.isna(rsi):
        return "INSUFFICIENT DATA", [
            "Some technical indicators are unavailable."
        ]

    reasons = []

    bullish = 0
    bearish = 0

    if close > sma20:
        bullish += 1
        reasons.append("Price is above the 20-period average.")
    else:
        bearish += 1
        reasons.append("Price is below the 20-period average.")

    if sma20 > sma50:
        bullish += 1
        reasons.append("The 20-period average is above the 50-period average.")
    else:
        bearish += 1
        reasons.append("The 20-period average is below the 50-period average.")

    if 50 <= rsi <= 70:
        bullish += 1
        reasons.append(f"RSI is {rsi:.1f}, showing positive momentum.")
    elif rsi < 30:
        bullish += 1
        reasons.append(f"RSI is {rsi:.1f}; the stock may be oversold.")
    elif rsi > 70:
        bearish += 1
        reasons.append(f"RSI is {rsi:.1f}; the stock may be overbought.")
    else:
        reasons.append(f"RSI is {rsi:.1f}, below the positive-momentum range.")

    if close > sma20 and sma20 > sma50 and 50 <= rsi <= 70:
        signal = "BUY"
    elif close < sma20 and sma20 < sma50 and (rsi < 50 or rsi > 70):
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, reasons


# --------------------------------------------------
# CANDLESTICK PATTERNS
# --------------------------------------------------

def detect_patterns(data):
    patterns = []

    if len(data) < 2:
        return ["Not enough candles to check patterns."]

    last = data.iloc[-1]
    previous = data.iloc[-2]

    body = abs(last["Close"] - last["Open"])
    candle_range = last["High"] - last["Low"]

    if candle_range > 0:
        if body <= candle_range * 0.1:
            patterns.append("Doji-like candle: opening and closing prices are close.")

        lower_wick = min(last["Open"], last["Close"]) - last["Low"]
        upper_wick = last["High"] - max(last["Open"], last["Close"])

        if lower_wick >= body * 2 and upper_wick <= body:
            patterns.append("Hammer-like candle: possible bullish reversal pattern.")

        if upper_wick >= body * 2 and lower_wick <= body:
            patterns.append("Shooting-star-like candle: possible bearish reversal pattern.")

    previous_bearish = previous["Close"] < previous["Open"]
    previous_bullish = previous["Close"] > previous["Open"]
    current_bullish = last["Close"] > last["Open"]
    current_bearish = last["Close"] < last["Open"]

    if (
        previous_bearish
        and current_bullish
        and last["Open"] <= previous["Close"]
        and last["Close"] >= previous["Open"]
    ):
        patterns.append("Bullish engulfing-like candle pattern.")

    if (
        previous_bullish
        and current_bearish
        and last["Open"] >= previous["Close"]
        and last["Close"] <= previous["Open"]
    ):
        patterns.append("Bearish engulfing-like candle pattern.")

    if not patterns:
        patterns.append("No basic candlestick pattern detected.")

    return patterns


# --------------------------------------------------
# OPTIONAL AI ANALYST
# --------------------------------------------------

def get_api_key():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if api_key:
        return api_key

    try:
        return st.secrets.get("OPENAI_API_KEY", "").strip()
    except Exception:
        return ""


def analyze_with_ai(symbol, data, signal, reasons, patterns):
    api_key = get_api_key()

    if not api_key:
        return (
            "AI analysis is not configured. Add your OpenAI API key "
            "to the app's environment or Streamlit secrets."
        )

    try:
        from openai import OpenAI

        last = data.iloc[-1]

        rsi_text = (
            f"{float(last['RSI']):.2f}"
            if pd.notna(last["RSI"])
            else "Unavailable"
        )

        prompt = f"""
Analyze this stock's technical indicators for educational purposes.

Ticker: {symbol}
Latest available price: ${float(last['Close']):.2f}
Technical signal: {signal}
SMA20: {last['SMA20']}
SMA50: {last['SMA50']}
RSI: {rsi_text}

Signal reasons:
{chr(10).join(reasons)}

Candlestick observations:
{chr(10).join(patterns)}

Explain the trend, uncertainty, and limitations in plain English.
Do not promise returns or present the signal as a guaranteed prediction.
Do not invent news, prices, or financial information.
This is technical analysis, not personalized financial advice.
"""

        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        return response.output_text

    except Exception as error:
        return (
            "AI analysis could not be completed. Check that the OpenAI "
            "package is installed, your API key is valid, and your API "
            f"account is configured. Error type: {type(error).__name__}"
        )


# --------------------------------------------------
# MAIN DASHBOARD
# --------------------------------------------------

@st.fragment(run_every="60s" if auto_refresh else None)
def show_dashboard():
    if not ticker:
        st.error("Enter a stock ticker in the sidebar.")
        return

    with st.spinner(f"Loading {ticker} stock data..."):
        try:
            data = download_stock_data(ticker, period, interval)
        except Exception as error:
            st.error(
                f"Could not download stock data. Error type: "
                f"{type(error).__name__}"
            )
            return

    if data.empty:
        st.error(
            f"No stock data was returned for {ticker}. "
            "Check the ticker and try again."
        )
        return

    data = calculate_indicators(data)
    signal, reasons = get_signal(data)
    patterns = detect_patterns(data)

    last = data.iloc[-1]
    price = float(last["Close"])

    # ----------------------------------------------
    # SIGNAL DISPLAY
    # ----------------------------------------------

    signal_colors = {
        "BUY": "#00ff66",
        "SELL": "#ff4040",
        "HOLD": "#ffd740",
        "INSUFFICIENT DATA": "#ffffff",
    }

    signal_color = signal_colors.get(signal, "#ffffff")

    st.markdown(
        f"""
        <div style="
            background-color: #101820;
            border: 3px solid {signal_color};
            border-radius: 16px;
            padding: 28px 16px;
            text-align: center;
            margin: 12px 0 24px 0;
            width: 100%;
            box-sizing: border-box;
        ">
            <div style="
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 3px;
            ">TECHNICAL SIGNAL</div>

            <div style="
                color: {signal_color};
                font-size: 60px;
                line-height: 1.2;
                font-weight: 900;
                margin: 14px 0;
                text-shadow: 0 0 8px {signal_color};
            ">{signal}</div>

            <div style="
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
            ">
                {ticker} · ${price:,.2f}
            </div>

            <div style="
                color: #cccccc;
                font-size: 13px;
                margin-top: 12px;
            ">
                Latest available candle · {data.index[-1]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ----------------------------------------------
    # METRICS
    # ----------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Latest Price", f"${price:,.2f}")

    col2.metric(
        "SMA 20",
        f"${last['SMA20']:,.2f}" if pd.notna(last["SMA20"]) else "N/A",
    )

    col3.metric(
        "SMA 50",
        f"${last['SMA50']:,.2f}" if pd.notna(last["SMA50"]) else "N/A",
    )

    col4.metric(
        "RSI",
        f"{last['RSI']:.2f}" if pd.notna(last["RSI"]) else "N/A",
    )

    # ----------------------------------------------
    # CANDLESTICK CHART
    # ----------------------------------------------

    st.subheader(f"{ticker} Price Chart")

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA20"],
            mode="lines",
            name="SMA 20",
            line=dict(width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA50"],
            mode="lines",
            name="SMA 50",
            line=dict(width=2),
        )
    )

    fig.update_layout(
        height=550,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------
    # SIGNAL REASONS
    # ----------------------------------------------

    st.subheader("Why This Signal?")

    for reason in reasons:
        st.write(f"• {reason}")

    st.caption(
        "The signal uses simple technical rules. It does not account for "
        "all company news, earnings, market conditions, or your financial situation."
    )

    # ----------------------------------------------
    # CANDLESTICK OBSERVATIONS
    # ----------------------------------------------

    with st.expander("Candlestick Pattern Checks"):
        for pattern in patterns:
            st.write(f"• {pattern}")

        st.caption(
            "Candlestick patterns are approximate observations and can give false signals."
        )

    # ----------------------------------------------
    # AI ANALYSIS
    # ----------------------------------------------

    st.subheader("🤖 AI Stock Analyst")

    if st.button("Analyze Stock with AI", key=f"ai_{ticker}"):
        with st.spinner("Analyzing technical data..."):
            analysis = analyze_with_ai(
                ticker,
                data,
                signal,
                reasons,
                patterns,
            )

        st.session_state[f"analysis_{ticker}"] = analysis

    saved_analysis = st.session_state.get(f"analysis_{ticker}")

    if saved_analysis:
        st.markdown(saved_analysis)

    # ----------------------------------------------
    # WATCHLIST
    # ----------------------------------------------

    st.subheader("⭐ Watchlist")

    watchlist = list(
        dict.fromkeys(
            item.strip().upper()
            for item in watchlist_text.split(",")
            if item.strip()
        )
    )

    watchlist_rows = []

    for symbol in watchlist:
        try:
            if symbol == ticker:
                watch_data = data
            else:
                watch_data = download_stock_data(symbol, "1mo", "1d")

            if watch_data.empty:
                watchlist_rows.append(
                    {
                        "Ticker": symbol,
                        "Price": "Unavailable",
                        "Daily Change": "N/A",
                    }
                )
                continue

            watch_close = watch_data["Close"].dropna()

            if watch_close.empty:
                raise ValueError("No closing prices")

            current_price = float(watch_close.iloc[-1])

            if len(watch_close) > 1:
                previous_price = float(watch_close.iloc[-2])
                change = (
                    (current_price - previous_price)
                    / previous_price
                    * 100
                    if previous_price != 0
                    else 0
                )
                change_text = f"{change:+.2f}%"
            else:
                change_text = "N/A"

            watchlist_rows.append(
                {
                    "Ticker": symbol,
                    "Price": f"${current_price:,.2f}",
                    "Daily Change": change_text,
                }
            )

        except Exception:
            watchlist_rows.append(
                {
                    "Ticker": symbol,
                    "Price": "Unavailable",
                    "Daily Change": "N/A",
                }
            )

    if watchlist_rows:
        st.dataframe(
            pd.DataFrame(watchlist_rows),
            hide_index=True,
            use_container_width=True,
        )

    st.caption(
        "Prices and chart intervals depend on Yahoo Finance data availability "
       
    st.caption(
        "Prices and chart intervals depend on Yahoo Finance data "
        "availability and may be delayed."
    )


show_dashboard() and may be delayed."
    )


show_dashboard()
