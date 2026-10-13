
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==================================================
# PAGE SETTINGS
# ==================================================

st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide",
)

st.title("📈 Stock Signal Dashboard")
st.caption("Candlestick charts • Technical signals • Watchlist")

# ==================================================
# SIDEBAR
# ==================================================

st.sidebar.header("Stock Settings")

ticker = st.sidebar.text_input(
    "Stock ticker", value="MSFT"
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
    "Refresh every 60 seconds", value=True
)

if st.sidebar.button("🔄 Refresh data now"):
    st.cache_data.clear()
    st.rerun()

if not ticker:
    st.warning("Enter a stock ticker to begin.")
    st.stop()

# ==================================================
# LIVE STOCK MARKET CLOCK
# ==================================================

@st.fragment(run_every="1s")
def show_market_clock():
    now = datetime.now(ZoneInfo("America/New_York"))

    market_open_time = now.replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    market_close_time = now.replace(
        hour=16, minute=0, second=0, microsecond=0
    )

    weekday = now.weekday() < 5
    is_open = (
        weekday
        and market_open_time <= now < market_close_time
    )

    st.subheader("🕒 US Stock Market Clock")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Current Eastern Time",
        now.strftime("%I:%M:%S %p"),
    )
    col2.metric("Market Opens", "9:30 AM")
    col3.metric("Market Closes", "4:00 PM")

    if is_open:
        st.success("🟢 MARKET OPEN")

        remaining = market_close_time - now
        seconds_left = max(0, int(remaining.total_seconds()))
        hours, remainder = divmod(seconds_left, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.write(
            f"Time until close: {hours}h {minutes}m {seconds}s"
        )

    else:
        st.error("🔴 MARKET CLOSED")

        if weekday and now < market_open_time:
            st.write("The regular market opens today at 9:30 AM ET.")
        elif weekday and now >= market_close_time:
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)

            st.write(
                f"Next weekday opening: "
                f"{next_day.strftime('%A')} at 9:30 AM ET."
            )
        else:
            next_day = now + timedelta(days=1)
            while next_day.weekday() >= 5:
                next_day += timedelta(days=1)

            st.write(
                f"Next weekday opening: "
                f"{next_day.strftime('%A')} at 9:30 AM ET."
            )

    st.caption(
        "Regular NYSE/Nasdaq hours: Monday–Friday, "
        "9:30 AM–4:00 PM Eastern. Holidays and special "
        "early closures are not checked by this clock."
    )

show_market_clock()

st.divider()

# ==================================================
# STOCK DATA
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

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.loc[:, ~df.columns.duplicated()].copy()

    required = ["Open", "High", "Low", "Close"]

    if not all(col in df.columns for col in required):
        return pd.DataFrame()

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

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

    avg_gain = gains.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    avg_loss = losses.ewm(
        alpha=1 / 14,
        min_periods=14,
        adjust=False,
    ).mean()

    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    rsi.loc[(avg_loss == 0) & (avg_gain > 0)] = 100
    rsi.loc[(avg_gain == 0) & (avg_loss > 0)] = 0
    rsi.loc[(avg_gain == 0) & (avg_loss == 0)] = 50

    df["RSI"] = rsi
    return df

# ==================================================
# BUY / SELL / HOLD SIGNAL
# ==================================================

def calculate_signal(df):
    if len(df) < 2:
        return "INSUFFICIENT DATA", 0, 0, [
            "Not enough price candles."
        ]

    last = df.iloc[-1]

    price = float(last["Close"])
    rsi = last["RSI"]
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]

    score = 0
    checks = 0
    reasons = []

    if pd.notna(sma20):
        checks += 1

        if price > float(sma20):
            score += 1
            reasons.append(
                "Bullish: price is above its 20-period average."
            )
        elif price < float(sma20):
            score -= 1
            reasons.append(
                "Bearish: price is below its 20-period average."
            )
        else:
            reasons.append("Price equals SMA20.")
    else:
        reasons.append("SMA20 is unavailable.")

    if pd.notna(sma20) and pd.notna(sma50):
        checks += 1

        if float(sma20) > float(sma50):
            score += 1
            reasons.append("Bullish: SMA20 is above SMA50.")
        elif float(sma20) < float(sma50):
            score -= 1
            reasons.append("Bearish: SMA20 is below SMA50.")
        else:
            reasons.append("SMA20 and SMA50 are equal.")
    else:
        reasons.append("Moving averages need more data.")

    if pd.notna(rsi):
        rsi = float(rsi)
        checks += 1

        if rsi < 30:
            score += 1
            reasons.append(
                f"RSI is {rsi:.1f}: commonly considered oversold."
            )
        elif rsi > 70:
            score -= 1
            reasons.append(
                f"RSI is {rsi:.1f}: commonly considered overbought."
            )
        else:
            reasons.append(f"RSI is {rsi:.1f}, within 30–70.")
    else:
        reasons.append("RSI is unavailable.")

    if checks < 2:
        signal = "INSUFFICIENT DATA"
    elif score >= 2:
        signal = "BUY"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, score, checks, reasons

# ==================================================
# CANDLESTICK PATTERNS
# ==================================================

def detect_patterns(df):
    if len(df) < 2:
        return ["Not enough candles to check patterns."]

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

    if (
        pc < po and c > o
        and o <= pc and c >= po
        and body >= previous_body
    ):
        patterns.append("Possible bullish engulfing pattern.")

    if (
        pc > po and c < o
        and o >= pc and c <= po
        and body >= previous_body
    ):
        patterns.append("Possible bearish engulfing pattern.")

    if (
        lower_wick >= 2 * max(body, 1e-9)
        and upper_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append("Hammer-like candle with a long lower wick.")

    if (
        upper_wick >= 2 * max(body, 1e-9)
        and lower_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append(
            "Shooting-star-like candle with a long upper wick."
        )

    if not patterns:
        patterns.append(
            "No selected pattern detected on the latest candle."
        )

    return patterns

# ==================================================
# MAIN DASHBOARD
# ==================================================

@st.fragment(run_every="60s" if auto_refresh else None)
def show_dashboard():
    try:
        raw = get_stock_data(ticker, period, interval)
    except Exception as error:
        st.error(f"Could not download stock data: {error}")
        return

    if raw.empty or len(raw) < 2:
        st.error(
            "No usable stock data was found. Check the ticker, "
            "internet connection, or selected interval."
        )
        return

    data = add_indicators(raw)

    signal, score, checks, reasons = calculate_signal(data)
    patterns = detect_patterns(data)

    last = data.iloc[-1]
    price = float(last["Close"])
    previous_price = float(data["Close"].iloc[-2])
    rsi = last["RSI"]

    percent_change = (
        (price / previous_price - 1) * 100
        if previous_price != 0 else 0
    )

    # SIGNAL DISPLAY

    colors = {
        "BUY": "#00e676",
        "SELL": "#ff5252",
        "HOLD": "#ffd740",
        "INSUFFICIENT DATA": "#ffffff",
    }

    signal_color = colors.get(signal, "#ffffff")

    st.markdown(
        f"""
        <style>
        .signal-card {{
            background: linear-gradient(135deg, #17212b, #243447);
            border: 2px solid {signal_color};
            border-radius: 16px;
            padding: 24px 16px;
            text-align: center;
            margin: 12px 0 24px 0;
        }}
        .signal-label {{
            color: #e0e6ed;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 3px;
        }}
        .signal-value {{
            color: {signal_color};
            font-size: 48px;
            font-weight: 900;
            line-height: 1.3;
            margin: 12px 0;
            overflow-wrap: anywhere;
        }}
        .signal-price {{
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
        }}
        .signal-date {{
            color: #d0d7de;
            font-size: 13px;
            margin-top: 12px;
        }}
        </style>
        <div class="signal-card">
            <div class="signal-label">STOCK SIGNAL</div>
            <div class="signal-value">{signal}</div>
            <div class="signal-price">{ticker} · ${price:,.2f}</div>
            <div class="signal-date">
                Latest available candle · {data.index[-1]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # METRICS

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Latest Price",
        f"${price:,.2f}",
        f"{percent_change:+.2f}%",
    )

    col2.metric(
        "RSI (14)",
        f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",
    )

    col3.metric(
        "SMA 20",
        f"${float(last['SMA20']):,.2f}"
        if pd.notna(last["SMA20"]) else "N/A",
    )

    col4.metric(
        "SMA 50",
        f"${float(last['SMA50']):,.2f}"
        if pd.notna(last["SMA50"]) else "N/A",
    )

    # CANDLESTICK CHART

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
            name="SMA 20",
            mode="lines",
            line=dict(color="#ffd740", width=2),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["SMA50"],
            name="SMA 50",
            mode="lines",
            line=dict(color="#40c4ff", width=2),
        )
    )

    fig.update_layout(
        template="plotly_dark",
        height=550,
        xaxis_title="Date",
        yaxis_title="Adjusted stock price ($)",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # SIGNAL EXPLANATION

    st.subheader("Why the dashboard chose this signal")

    left, right = st.columns(2)

    with left:
        st.write(f"**Signal:** {signal}")
        st.write(f"**Technical score:** {score}")
        st.write(f"**Valid indicator checks:** {checks} of 3")

        for reason in reasons:
            st.write("• " + reason)

    with right:
        st.write("**Candlestick pattern checks**")

        for pattern in patterns:
            st.write("• " + pattern)

    # WATCHLIST

    st.subheader("⭐ Watchlist")

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

            close = watch_data["Close"].astype(float)
            current = float(close.iloc[-1])
            previous = float(close.iloc[-2])

            daily_change = (
                (current / previous - 1) * 100
                if previous != 0 else 0
            )

            rows.append({
                "Ticker": symbol,
                "Price": f"${current:,.2f}",
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
        st.info("Choose stocks in the sidebar to show your watchlist.")

    st.caption(
        "Yahoo Finance data may be delayed or unavailable. "
        "Technical signals can be wrong and do not guarantee future returns."
    )


show_dashboard()

