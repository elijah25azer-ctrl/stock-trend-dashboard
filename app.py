
import os
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ==================================================
# PAGE SETTINGS
# ==================================================
st.set_page_config(
    page_title="AI Stock Signal Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 AI Stock Signal Dashboard")
st.caption(
    "Candlestick charts • BUY / SELL / HOLD • "
    "Pattern detection • AI market analysis"
)

# ==================================================
# SIDEBAR SETTINGS
# ==================================================
st.sidebar.header("Stock Settings")

ticker = st.sidebar.text_input(
    "Enter stock ticker",
    value="MSFT",
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1mo", "3mo", "6mo", "1y", "2y"],
    index=2,
)

interval = st.sidebar.selectbox(
    "Candle interval",
    ["1d", "1h", "30m", "15m"],
    index=0,
)

watchlist = st.sidebar.multiselect(
    "Watchlist",
    ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN", "GOOGL", "META"],
    default=["MSFT", "AAPL", "NVDA"],
)

auto_refresh = st.sidebar.toggle(
    "Refresh every 60 seconds",
    value=True,
)

if st.sidebar.button("🔄 Refresh data now"):
    st.cache_data.clear()
    st.rerun()

if not ticker:
    st.warning("Please enter a stock ticker.")
    st.stop()


# ==================================================
# DOWNLOAD STOCK DATA
# ==================================================
@st.cache_data(ttl=55)
def get_stock_data(symbol, history, candle_interval):
    df = yf.download(
        symbol,
        period=history,
        interval=candle_interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    # Handle different Yahoo Finance column formats.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.loc[:, ~df.columns.duplicated()]

    required = ["Open", "High", "Low", "Close"]

    if not all(column in df.columns for column in required):
        return pd.DataFrame()

    for column in required:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )

    return df.dropna(subset=required).copy()


# ==================================================
# TECHNICAL INDICATORS
# ==================================================
def add_indicators(df):
    df = df.copy()

    close = df["Close"].astype(float)

    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()

    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.rolling(14).mean()
    avg_loss = losses.rolling(14).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))

    df["RSI"] = 100 - (100 / (1 + rs))

    # Handle edge cases in RSI.
    df.loc[
        (avg_loss == 0) & (avg_gain > 0),
        "RSI",
    ] = 100

    df["RSI"] = df["RSI"].fillna(50)

    return df


# ==================================================
# CANDLESTICK PATTERN DETECTION
# ==================================================
def detect_patterns(df):
    """Rule-based candle checks, not a trained AI model."""

    if len(df) < 2:
        return ["Not enough candles to detect patterns."]

    current = df.iloc[-1]
    previous = df.iloc[-2]

    o = float(current["Open"])
    h = float(current["High"])
    l = float(current["Low"])
    c = float(current["Close"])

    po = float(previous["Open"])
    pc = float(previous["Close"])

    body = abs(c - o)
    previous_body = abs(pc - po)
    candle_range = max(h - l, 1e-9)

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    patterns = []

    # Bullish engulfing
    if (
        pc < po
        and c > o
        and o <= pc
        and c >= po
        and body >= previous_body
    ):
        patterns.append(
            "Bullish engulfing: possible bullish reversal."
        )

    # Bearish engulfing
    if (
        pc > po
        and c < o
        and o >= pc
        and c <= po
        and body >= previous_body
    ):
        patterns.append(
            "Bearish engulfing: possible bearish reversal."
        )

    # Hammer-like candle
    if (
        lower_wick >= 2 * max(body, 1e-9)
        and upper_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append(
            "Hammer-like candle: long lower wick."
        )

    # Shooting-star-like candle
    if (
        upper_wick >= 2 * max(body, 1e-9)
        and lower_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append(
            "Shooting-star-like candle: long upper wick."
        )

    if not patterns:
        patterns.append(
            "No selected pattern detected on the latest candle."
        )

    return patterns


# ==================================================
# BUY / SELL / HOLD CALCULATION
# ==================================================
def calculate_signal(df):
    last = df.iloc[-1]

    price = float(last["Close"])
    rsi = float(last["RSI"])
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]

    score = 0
    reasons = []

    if pd.notna(sma20):
        if price > float(sma20):
            score += 1
            reasons.append("Price is above SMA20.")
        else:
            score -= 1
            reasons.append("Price is below SMA20.")
    else:
        reasons.append("More data is needed for SMA20.")

    if pd.notna(sma20) and pd.notna(sma50):
        if float(sma20) > float(sma50):
            score += 1
            reasons.append("SMA20 is above SMA50.")
        else:
            score -= 1
            reasons.append("SMA20 is below SMA50.")
    else:
        reasons.append("More data is needed to compare both averages.")

    if rsi < 30:
        score += 1
        reasons.append(
            f"RSI is {rsi:.1f}, in a commonly used oversold zone."
        )
    elif rsi > 70:
        score -= 1
        reasons.append(
            f"RSI is {rsi:.1f}, in a commonly used overbought zone."
        )
    else:
        reasons.append(
            f"RSI is {rsi:.1f}, between 30 and 70."
        )

    if score >= 2 and rsi < 70:
        signal = "BUY"
    elif score <= -1 or rsi >= 75:
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, score, reasons


# ==================================================
# AI MARKET ANALYST
# ==================================================
def analyze_with_ai(symbol, df, signal, reasons, patterns):
    """Uses the OpenAI API to explain the latest chart information."""

    api_key = os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        try:
            api_key = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            api_key = ""

    if not api_key:
        return (
            "AI is not connected yet. Add your OpenAI API key "
            "to Streamlit Secrets or the OPENAI_API_KEY environment "
            "variable. The chart and technical indicators still work."
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        last = df.iloc[-1]

        sma20 = (
            round(float(last["SMA20"]), 2)
            if pd.notna(last["SMA20"])
            else "Unavailable"
        )

        sma50 = (
            round(float(last["SMA50"]), 2)
            if pd.notna(last["SMA50"])
            else "Unavailable"
        )

        prompt = f"""
You are an educational stock chart analyst.

Ticker: {symbol}
Latest available close: ${float(last["Close"]):.2f}
RSI (14): {float(last["RSI"]):.1f}
SMA20: {sma20}
SMA50: {sma50}
Rule-based dashboard signal: {signal}
Indicator observations: {reasons}
Candlestick pattern observations: {patterns}

Explain the chart in plain English using concise bullet points:
1. Does the chart look bullish, bearish, or mixed, and why?
2. What might the indicators mean?
3. What might the candle patterns mean?
4. What risks, uncertainties, and limitations should be considered?
5. What additional information would help someone evaluate the stock?

Do not claim certainty or guarantee returns. Explain that indicators
and candle patterns can fail. Do not present this as personalized
financial advice. The supplied information may be incomplete.
"""

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
        )

        return response.output_text

    except Exception as error:
        return (
            "The AI request failed. Check your API key, API access, "
            f"billing, and internet connection. Details: {error}"
        )


# ==================================================
# MAIN DASHBOARD
# ==================================================
@st.fragment(run_every="60s" if auto_refresh else None)
def show_dashboard():

    try:
        raw = get_stock_data(ticker, period, interval)
    except Exception as error:
        st.error(f"Stock data download failed: {error}")
        return

    if raw.empty or len(raw) < 2:
        st.error(
            "No usable stock data was found. Check the ticker "
            "or select a different interval."
        )
        return

    data = add_indicators(raw)

    signal, score, reasons = calculate_signal(data)
    patterns = detect_patterns(data)

    last = data.iloc[-1]
    price = float(last["Close"])
    previous_price = float(data["Close"].iloc[-2])
    rsi = float(last["RSI"])
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]

    percent_change = (
        (price / previous_price - 1) * 100
        if previous_price else 0
    )

    signal_color = {
        "BUY": "#00e676",
        "SELL": "#ff5252",
        "HOLD": "#ffd740",
    }[signal]

    # ---------------- BLACK SIGNAL BOX ----------------
    st.markdown(
        f"""
        <div style="
            background-color:#000000;
            border:2px solid {signal_color};
            border-radius:12px;
            padding:30px 15px;
            text-align:center;
            margin:10px 0 25px 0;
        ">
            <div style="
                color:#aaaaaa;
                font-size:14px;
                letter-spacing:4px;
            ">RULE-BASED STOCK SIGNAL</div>

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
                Updated {datetime.now().astimezone().strftime("%I:%M:%S %p %Z")}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------------- METRICS ----------------
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Latest available price",
        f"${price:,.2f}",
        f"{percent_change:+.2f}%",
    )

    col2.metric("RSI (14)", f"{rsi:.1f}")

    col3.metric(
        "SMA 20",
        f"${float(sma20):,.2f}" if pd.notna(sma20) else "N/A",
    )

    col4.metric(
        "SMA 50",
        f"${float(sma50):,.2f}" if pd.notna(sma50) else "N/A",
    )

    # ---------------- CANDLESTICK CHART ----------------
    st.subheader(f"🕯️ {ticker} Candlestick Chart")

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price",
            increasing_line_color="#00e676",
            decreasing_line_color="#ff5252",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA20"],
            mode="lines",
            name="SMA 20",
            line=dict(color="#ffd740", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA50"],
            mode="lines",
            name="SMA 50",
            line=dict(color="#40c4ff", width=2),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=600,
        xaxis_title="Date",
        yaxis_title="Stock price ($)",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend_title="Indicators",
        margin=dict(l=10, r=10, t=35, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)

    # ---------------- EXPLANATION ----------------
    left, right = st.columns(2)

    with left:
        st.subheader("Why this signal appeared")
        st.write(f"**Signal:** {signal}")
        st.write(f"**Technical score:** {score}")

        for reason in reasons:
            st.write("• " + reason)

    with right:
        st.subheader("Candlestick pattern checks")

        for pattern in patterns:
            st.write("• " + pattern)

        st.caption(
            "Pattern checks use simple rules and can produce false positives."
        )

    # ---------------- AI ANALYST ----------------
    st.subheader("🤖 AI Market Analyst")
    st.write(
        "Ask the AI to explain the current chart, technical indicators, "
        "candlestick observations, and risks."
    )

    if st.button("Analyze chart with AI", type="primary"):
        with st.spinner("AI is analyzing the chart summary..."):
            st.session_state["ai_result"] = analyze_with_ai(
                ticker,
                data,
                signal,
                reasons,
                patterns,
            )
            st.session_state["ai_ticker"] = ticker

    if (
        st.session_state.get("ai_result")
        and st.session_state.get("ai_ticker") == ticker
    ):
        st.markdown(st.session_state["ai_result"])

    # ---------------- WATCHLIST ----------------
    st.subheader("👀 Stock Watchlist")

    rows = []

    for symbol in watchlist:
        try:
            watch_data = get_stock_data(symbol, "1mo", "1d")

            if watch_data.empty or len(watch_data) < 2:
                rows.append({
                    "Ticker": symbol,
                    "Price": "Unavailable",
                    "Daily change": "N/A",
                })
                continue

            watch_close = watch_data["Close"].astype(float)
            latest = float(watch_close.iloc[-1])
            previous = float(watch_close.iloc[-2])

            daily_change = (
                (latest / previous - 1) * 100
                if previous else 0
            )

            rows.append({
                "Ticker": symbol,
                "Price": f"${latest:,.2f}",
                "Daily change": f"{daily_change:+.2f}%",
            })

        except Exception:
            rows.append({
                "Ticker": symbol,
                "Price": "Unavailable",
                "Daily change": "N/A",
            })

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Select stocks in the sidebar to populate your watchlist.")

    st.caption(
        "Market data may be delayed or unavailable. The BUY/SELL/HOLD "
        "label is rule-based, not a guaranteed prediction. AI explanations "
        "can also be wrong and are not personalized financial advice."
    )

    st.caption(
        "Automatic refresh works only while the app is running and active; "
        "it does not guarantee uninterrupted 24/7 monitoring."
    )


show_dashboard()
