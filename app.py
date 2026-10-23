import html
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    [data-testid="stAppDeployButton"] {display: none !important;}
    [data-testid="stToolbar"] {visibility: hidden !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 Stock Signal Dashboard")
st.caption(
    "Stock prices | Candlesticks | Watchlist | Short-term and "
    "long-term outlooks | News | Earnings"
)

ET = ZoneInfo("America/New_York")

# =========================================================
# SMALL HELPERS (COLORS / FORMATTING)
# =========================================================

UP_COLOR = "#238a23"    # green
DOWN_COLOR = "#d6404f"  # red


def format_change(change, pct):
    """Format a price change so the sign comes FIRST, e.g. '-$2.79 (-0.74%)'.

    Streamlit colors a metric's delta red only when the text starts with a
    minus sign. The old format '$-2.79' started with '$', so down moves were
    shown in green.
    """
    sign = "+" if change >= 0 else "-"
    return f"{sign}${abs(change):,.2f} ({pct:+.2f}%)"


def color_change(value):
    """Cell color for tables: red when negative, green when positive."""
    text = str(value).strip()

    if text.startswith("-"):
        return f"color: {DOWN_COLOR}; font-weight: 600;"
    if text.startswith("+"):
        return f"color: {UP_COLOR}; font-weight: 600;"

    return ""

# =========================================================
# STOCK OPTIONS
# =========================================================

STOCK_OPTIONS = sorted(set("""
AAPL MSFT NVDA TSLA AMZN GOOGL GOOG META AMD INTC PLTR NFLX
AVGO ORCL CRM JPM V MA WMT COST KO PEP DIS UBER SHOP COIN
HOOD SOFI MSTR SMCI ARM MU QCOM ADBE CSCO IBM TSM LLY NVO
XOM CVX BA F GM SPY QQQ DIA IWM VOO VTI SCHD JEPI JEPQ
ASML ANET PANW CRWD NOW SNOW NET DDOG MDB RBLX U RIVN LCID
NIO XPEV LI BABA BIDU PDD JD SE PYPL XYZ AFRM UPST NU MELI
AMAT LRCX KLAC MRVL TXN ADI ON NXPI SNPS CDNS INTU ACN
WDAY TEAM ZM DOCU TWLO PATH IONQ RGTI QUBT ASTS RKLB LUNR
LMT RTX NOC GD CAT DE CMI HON GE ETN UNH JNJ ABBV MRK PFE
AMGN GILD REGN ISRG BSX TGT HD LOW MCD SBUX CMG YUM NKE
LULU TJX ROST CAVA CELH MNST PM MO CL PG EL MDLZ GIS
BAC WFC C GS MS BLK SCHW CBOE ICE CME AXP BRK-B
CVNA ABNB BKNG EXPE DASH LYFT UPS FDX DAL UAL AAL LUV
CCL RCL MAR HLT T VZ TMUS CMCSA PARA WBD FOXA
PLD AMT EQIX REAL VICI SPG COP SLB OXY EOG MPC PSX KMI WMB
RSP IVV SPLG VUG VTV ARKK ARKG XLF XLK XLE XLV XLI XLY
XLP XLU XLRE SMH SOXX TQQQ SQQQ IBIT FBTC ETHA GLD SLV
USO UNG TLT HYG LQD
""".split()))

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("Stock Settings")

ticker = st.sidebar.text_input(
    "Main chart ticker",
    value="MSFT",
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
    index=4,
)

interval = st.sidebar.selectbox(
    "Candle interval",
    ["1d", "1h", "30m", "15m", "5m", "1m"],
    index=0,
)

watchlist = st.sidebar.multiselect(
    "Watchlist",
    options=STOCK_OPTIONS,
    default=["MSFT", "AAPL", "NVDA", "TSLA", "AMZN", "DIS"],
)

custom_tickers = st.sidebar.text_input(
    "Add extra tickers",
    placeholder="Example: AMD, PLTR",
)

if custom_tickers.strip():
    for symbol in custom_tickers.upper().replace(" ", "").split(","):
        if symbol and symbol not in watchlist:
            watchlist.append(symbol)

auto_refresh = st.sidebar.toggle(
    "Auto-refresh data",
    value=False,
    help="Refresh the dashboard every 60 seconds when supported.",
)

show_sma = st.sidebar.toggle(
    "Show SMA 20 / 50 lines",
    value=True,
)

if st.sidebar.button("🔄 Refresh all data"):
    st.cache_data.clear()
    st.rerun()

if not ticker:
    st.warning("Enter a stock ticker.")
    st.stop()

# =========================================================
# AUTO-REFRESH
# =========================================================

# Streamlit versions supporting fragments can rerun this dashboard
# periodically. The fallback leaves manual refresh available.
if auto_refresh:
    try:
        st.fragment(run_every="60s")
    except Exception:
        pass

# =========================================================
# MARKET CLOCK
# =========================================================

now = datetime.now(ET)

st.subheader("🕒 US Stock Market Clock")

c1, c2, c3 = st.columns(3)
c1.metric("Eastern Time", now.strftime("%I:%M:%S %p"))
c2.metric("Market Opens", "9:30 AM")
c3.metric("Market Closes", "4:00 PM")

regular_hours = (
    now.weekday() < 5
    and (9, 30) <= (now.hour, now.minute) < (16, 0)
)

if regular_hours:
    st.success("🟢 Regular trading hours")
else:
    st.info(
        "🔴 Outside regular trading hours. "
        "Prices may reflect the latest available close."
    )

st.caption(
    "Regular hours are Monday–Friday, 9:30 AM–4:00 PM ET. "
    "This clock does not check exchange holidays or early closes."
)

st.divider()

# =========================================================
# PRICE DATA
# =========================================================

@st.cache_data(ttl=15)
def get_stock_data(symbol, history, candle_interval):
    try:
        df = yf.download(
            symbol,
            period=history,
            interval=candle_interval,
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=15,
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

        return df.dropna(subset=required).sort_index()

    except Exception:
        return pd.DataFrame()

# =========================================================
# QUOTES AND DAILY CHANGE
# =========================================================

@st.cache_data(ttl=20)
def get_quote(symbol):
    try:
        now_et = datetime.now(ET)
        daily = get_stock_data(symbol, "10d", "1d")

        if daily.empty or len(daily) < 2:
            return None

        daily = daily.sort_index().copy()

        def trading_date(timestamp):
            timestamp = pd.Timestamp(timestamp)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert(ET)
            return timestamp.date()

        daily_dates = [trading_date(ts) for ts in daily.index]
        market_open = (
            now_et.weekday() < 5
            and (now_et.hour, now_et.minute) >= (9, 30)
            and (now_et.hour, now_et.minute) < (16, 0)
        )

        price = None
        previous_close = None
        quote_time = ""
        status = ""

        # 1) During regular hours, try the newest 1-minute candle.
        if market_open:
            previous_rows = daily.loc[
                [day < now_et.date() for day in daily_dates]
            ]
            intraday = get_stock_data(symbol, "1d", "1m")

            if not previous_rows.empty and not intraday.empty:
                today_rows = intraday.loc[
                    [
                        trading_date(ts) == now_et.date()
                        for ts in intraday.index
                    ]
                ]

                if not today_rows.empty:
                    candidate = float(today_rows["Close"].iloc[-1])

                    latest_timestamp = pd.Timestamp(today_rows.index[-1])
                    if latest_timestamp.tzinfo is None:
                        latest_timestamp = latest_timestamp.tz_localize(ET)
                    else:
                        latest_timestamp = latest_timestamp.tz_convert(ET)

                    age_seconds = (
                        now_et - latest_timestamp.to_pydatetime()
                    ).total_seconds()

                    if candidate > 0 and -60 <= age_seconds <= 15 * 60:
                        price = candidate
                        previous_close = float(
                            previous_rows["Close"].iloc[-1]
                        )
                        quote_time = latest_timestamp.strftime(
                            "%Y-%m-%d %I:%M:%S %p ET"
                        )
                        status = "Intraday quote (may be delayed)"

        # 2) Fallback (and the normal path outside regular hours):
        #    the latest daily candle versus the one before it.
        #    This also covers exchange holidays, where no 1-minute
        #    data exists, so the card never gets stuck on "N/A".
        if price is None:
            price = float(daily["Close"].iloc[-1])
            previous_close = float(daily["Close"].iloc[-2])
            quote_time = f"Close of {daily_dates[-1]}"
            status = (
                "Latest daily price"
                if market_open else "Latest daily close"
            )

        if (
            not pd.notna(price)
            or not pd.notna(previous_close)
            or price <= 0
            or previous_close <= 0
        ):
            return None

        change = price - previous_close
        change_pct = (change / previous_close) * 100

        return {
            "price": price,
            "previous_close": previous_close,
            "change": change,
            "change_pct": change_pct,
            "time": quote_time,
            "status": status,
        }

    except Exception:
        return None

# =========================================================
# TECHNICAL INDICATORS
# =========================================================

def add_indicators(df):
    df = df.copy()

    if df.empty or "Close" not in df.columns:
        return df

    close = df["Close"].astype(float)

    df["SMA5"] = close.rolling(5).mean()
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
    df["RSI"] = 100 - (100 / (1 + rs))

    df.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100
    df.loc[(avg_gain == 0) & (avg_loss > 0), "RSI"] = 0
    df.loc[(avg_gain == 0) & (avg_loss == 0), "RSI"] = 50

    return df

# =========================================================
# LONG-TERM OUTLOOK
# =========================================================

def calculate_signal(df):
    if df is None or df.empty or len(df) < 50:
        return "INSUFFICIENT DATA", 0, 0, [
            "At least 50 daily candles are required."
        ]

    last = df.iloc[-1]

    price = float(last["Close"])
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]
    rsi = last["RSI"]

    reasons = []
    bullish = 0
    bearish = 0
    checks = 0

    if pd.notna(sma20) and pd.notna(sma50):
        sma20 = float(sma20)
        sma50 = float(sma50)
        checks += 1

        if price > sma20 and sma20 > sma50:
            bullish += 1
            reasons.append(
                "Long-term trend is bullish: price is above SMA20 "
                "and SMA20 is above SMA50."
            )
        elif price < sma20 and sma20 < sma50:
            bearish += 1
            reasons.append(
                "Long-term trend is bearish: price is below SMA20 "
                "and SMA20 is below SMA50."
            )
        else:
            reasons.append(
                "Long-term moving averages show a mixed trend."
            )
    else:
        reasons.append("Long-term moving averages are unavailable.")

    if pd.notna(rsi):
        rsi = float(rsi)
        checks += 1

        if rsi >= 50:
            bullish += 1
            reasons.append(
                f"Daily RSI is {rsi:.1f}: momentum is positive."
            )
        elif rsi <= 40:
            bearish += 1
            reasons.append(
                f"Daily RSI is {rsi:.1f}: momentum is weak."
            )
        else:
            reasons.append(
                f"Daily RSI is {rsi:.1f}: momentum is inconclusive."
            )
    else:
        reasons.append("Daily RSI is unavailable.")

    if checks < 2:
        signal = "INSUFFICIENT DATA"
    elif bullish == 2:
        signal = "BUY"
    elif bearish == 2:
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, bullish - bearish, checks, reasons

# =========================================================
# SHORT-TERM OUTLOOK
# =========================================================

def calculate_short_term_signal(
    df,
    current_price=None,
    daily_change_pct=None,
):
    if df is None or df.empty or len(df) < 20:
        return "INSUFFICIENT DATA", [
            "At least 20 daily candles are required."
        ]

    data = add_indicators(df)
    close = data["Close"].astype(float).dropna()

    if len(close) < 20:
        return "INSUFFICIENT DATA", [
            "Not enough daily price history."
        ]

    price = (
        float(current_price)
        if current_price is not None
        else float(close.iloc[-1])
    )

    sma5 = data["SMA5"].iloc[-1]
    rsi_value = data["RSI"].iloc[-1]
    previous_price = float(close.iloc[-6])

    momentum = (
        (price / previous_price - 1) * 100
        if previous_price > 0 else 0
    )

    if daily_change_pct is not None and daily_change_pct <= -3:
        return "HOLD", [
            f"Daily change is {daily_change_pct:.2f}%.",
            "Short-term BUY blocked because of a sharp daily drop.",
            "Wait for clearer price direction; recovery is not guaranteed.",
        ]

    if pd.isna(sma5) or pd.isna(rsi_value):
        return "INSUFFICIENT DATA", [
            "Short-term moving average or RSI is unavailable."
        ]

    sma5 = float(sma5)
    rsi_value = float(rsi_value)

    if price > sma5 and momentum > 0 and rsi_value >= 50:
        signal = "BUY"
        reasons = [
            "Price is above the 5-day moving average.",
            f"Recent momentum is positive: {momentum:+.2f}%.",
            f"RSI is {rsi_value:.1f}, supporting momentum.",
        ]
    elif price < sma5 and momentum < 0 and rsi_value <= 45:
        signal = "SELL"
        reasons = [
            "Price is below the 5-day moving average.",
            f"Recent momentum is negative: {momentum:+.2f}%.",
            f"RSI is {rsi_value:.1f}, showing weak momentum.",
        ]
    else:
        signal = "HOLD"
        reasons = [
            f"Recent momentum is {momentum:+.2f}%.",
            "Short-term indicators do not fully agree.",
        ]

    return signal, reasons

# =========================================================
# CANDLESTICK PATTERNS
# =========================================================

def detect_patterns(df):
    if df is None or len(df) < 2:
        return ["Not enough candles."]

    current = df.iloc[-1]
    previous = df.iloc[-2]

    o = float(current["Open"])
    h = float(current["High"])
    low = float(current["Low"])
    c = float(current["Close"])

    po = float(previous["Open"])
    pc = float(previous["Close"])

    body = abs(c - o)
    previous_body = abs(pc - po)
    candle_range = max(h - low, 1e-9)

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - low

    patterns = []

    if (
        pc < po and c > o
        and o <= pc and c >= po
        and body >= previous_body
    ):
        patterns.append("Possible bullish engulfing.")

    if (
        pc > po and c < o
        and o >= pc and c <= po
        and body >= previous_body
    ):
        patterns.append("Possible bearish engulfing.")

    if (
        lower_wick >= 2 * max(body, 1e-9)
        and upper_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append("Hammer-like candle.")

    if (
        upper_wick >= 2 * max(body, 1e-9)
        and lower_wick <= max(body * 0.6, candle_range * 0.08)
        and body / candle_range <= 0.4
    ):
        patterns.append("Shooting-star-like candle.")

    return patterns or ["No selected pattern detected."]

# =========================================================
# QUICK STOCK PRICES
# =========================================================

st.subheader("📌 Quick Stock Prices")

DEFAULT_QUICK_STOCKS = ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN", "DIS"]
QUICK_SLOTS = 6


def parse_stock_list(text):
    """Turn 'MSFT, aapl,TSLA' into ['MSFT', 'AAPL', 'TSLA'] (no duplicates)."""
    result = []
    for item in (text or "").upper().replace(" ", "").split(","):
        if item and item not in result:
            result.append(item)
    return result[:QUICK_SLOTS]


# Your 6 quick stocks are saved in the page address (?stocks=...), so they
# survive a browser refresh and can be bookmarked.
if "quick_stocks" not in st.session_state:
    saved = parse_stock_list(st.query_params.get("stocks", ""))
    filler = [d for d in DEFAULT_QUICK_STOCKS if d not in saved]
    st.session_state["quick_stocks"] = (saved + filler)[:QUICK_SLOTS]

quick_stocks = st.session_state["quick_stocks"]
top_cols = st.columns(len(quick_stocks))

for i, (col, symbol) in enumerate(zip(top_cols, quick_stocks)):
    with col:
        quote = get_quote(symbol)
        st.markdown(f"**{symbol}**")

        if quote is None:
            st.metric("Price", "N/A")
            st.caption("Quote unavailable or delayed.")
        else:
            st.metric(
                label="Price",
                value=f"${quote['price']:,.2f}",
                # Sign first ("-$2.79") so down moves show RED, up moves GREEN.
                delta=format_change(quote["change"], quote["change_pct"]),
                delta_color="normal",
            )
            st.caption(quote["status"])
            st.caption(f"Updated: {quote['time']}")

        # Click to change this card to ANY stock ticker
        with st.popover("✏️ Edit", use_container_width=True):
            new_symbol = st.text_input(
                "Any stock ticker",
                key=f"quick_input_{i}_{symbol}",
                placeholder="Example: AMD",
            )

            if st.button("Apply", key=f"quick_apply_{i}_{symbol}"):
                sym = new_symbol.strip().upper()

                if not sym:
                    st.warning("Type a ticker first.")
                elif sym in quick_stocks:
                    st.warning(f"{sym} is already shown.")
                elif get_quote(sym) is None:
                    st.error(f"No data found for {sym}. Check the ticker.")
                else:
                    st.session_state["quick_stocks"][i] = sym
                    st.query_params["stocks"] = ",".join(
                        st.session_state["quick_stocks"]
                    )
                    st.rerun()

if st.button("↩️ Reset quick stocks to default"):
    st.session_state["quick_stocks"] = list(DEFAULT_QUICK_STOCKS)
    st.query_params.clear()
    st.rerun()

st.caption(
    "During regular trading hours, quotes use Yahoo Finance 1-minute candles. "
    "Outside those hours, the dashboard shows the latest daily close. "
    "Green means up from the previous close; red means down. "
    "Yahoo Finance data may be delayed, incomplete, or unavailable."
)

st.divider()

# =========================================================
# WATCHLIST
# =========================================================

st.subheader("⭐ Watchlist")

if not watchlist:
    st.info("Select stocks in the sidebar to populate your watchlist.")
else:
    rows = []
    progress = st.progress(0)
    status = st.empty()

    for i, symbol in enumerate(watchlist):
        status.caption(f"Loading {symbol} ({i + 1}/{len(watchlist)})")

        try:
            daily = get_stock_data(symbol, "1y", "1d")
            quote = get_quote(symbol)

            if daily.empty or len(daily) < 50:
                rows.append({
                    "Ticker": symbol,
                    "Price": "N/A",
                    "Change ($)": "N/A",
                    "Change (%)": "N/A",
                    "Short-Term": "INSUFFICIENT DATA",
                    "Long-Term": "INSUFFICIENT DATA",
                    "RSI": "N/A",
                })
            else:
                data = add_indicators(daily)
                long_signal, _, _, _ = calculate_signal(data)

                if quote is not None:
                    price = float(quote["price"])
                    previous = float(quote["previous_close"])
                    change = price - previous
                    change_pct = (
                        change / previous * 100 if previous > 0 else 0
                    )

                    price_text = f"${price:,.2f}"
                    # Sign first so the table can color it red / green.
                    sign = "+" if change >= 0 else "-"
                    change_text = f"{sign}${abs(change):,.2f}"
                    pct_text = f"{change_pct:+.2f}%"

                    short_signal, _ = calculate_short_term_signal(
                        data,
                        current_price=price,
                        daily_change_pct=change_pct,
                    )
                else:
                    price = float(daily["Close"].iloc[-1])
                    price_text = f"${price:,.2f}"
                    change_text = "N/A"
                    pct_text = "N/A"

                    short_signal, _ = calculate_short_term_signal(data)

                rsi = data["RSI"].iloc[-1]

                rows.append({
                    "Ticker": symbol,
                    "Price": price_text,
                    "Change ($)": change_text,
                    "Change (%)": pct_text,
                    "Short-Term": short_signal,
                    "Long-Term": long_signal,
                    "RSI": f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",
                })

        except Exception:
            rows.append({
                "Ticker": symbol,
                "Price": "N/A",
                "Change ($)": "N/A",
                "Change (%)": "N/A",
                "Short-Term": "NO DATA",
                "Long-Term": "NO DATA",
                "RSI": "N/A",
            })

        progress.progress((i + 1) / len(watchlist))

    progress.empty()
    status.empty()

    table = pd.DataFrame(rows)
    styled_table = table.style

    # pandas 2.1+ uses .map; older versions use .applymap
    if hasattr(styled_table, "map"):
        styled_table = styled_table.map(
            color_change, subset=["Change ($)", "Change (%)"]
        )
    else:
        styled_table = styled_table.applymap(
            color_change, subset=["Change ($)", "Change (%)"]
        )

    st.dataframe(
        styled_table,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Short-Term uses recent momentum and the 5-day average. "
        "Long-Term uses the 20-day and 50-day averages with RSI. "
        "A long-term BUY does not mean the stock will rise today."
    )

st.divider()

# =========================================================
# MAIN STOCK CHART
# =========================================================

st.subheader(f"📊 Main Stock: {ticker}")

raw = get_stock_data(ticker, period, interval)

if raw.empty or len(raw) < 2:
    st.error(
        "No usable price data was returned. Check the ticker, "
        "internet connection, or candle interval."
    )
else:
    chart_data = add_indicators(raw)

    # Signals always use daily history, regardless of chart interval.
    daily_signal_raw = get_stock_data(ticker, "1y", "1d")
    signal_data = add_indicators(daily_signal_raw)

    long_signal, score, checks, long_reasons = calculate_signal(
        signal_data
    )

    quote = get_quote(ticker)

    if quote is not None:
        displayed_price = float(quote["price"])
        displayed_previous = float(quote["previous_close"])

        displayed_change = (
            (displayed_price / displayed_previous - 1) * 100
            if displayed_previous > 0 else 0
        )

        short_signal, short_reasons = calculate_short_term_signal(
            signal_data,
            current_price=displayed_price,
            daily_change_pct=displayed_change,
        )
    else:
        displayed_price = float(chart_data["Close"].iloc[-1])
        displayed_change = None

        short_signal, short_reasons = calculate_short_term_signal(
            signal_data
        )

    patterns = detect_patterns(chart_data)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Latest Available Price",
        f"${displayed_price:,.2f}",
        (
            f"{displayed_change:+.2f}%"
            if displayed_change is not None else None
        ),
    )

    c2.metric("Short-Term Outlook", short_signal)
    c3.metric("Long-Term Outlook", long_signal)

    rsi = (
        signal_data["RSI"].iloc[-1]
        if not signal_data.empty else float("nan")
    )
    c4.metric(
        "Daily RSI (14)",
        f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",
    )

    sma20 = (
        signal_data["SMA20"].iloc[-1]
        if not signal_data.empty else float("nan")
    )
    c5.metric(
        "Daily SMA 20",
        f"${float(sma20):,.2f}" if pd.notna(sma20) else "N/A",
    )

    st.caption(
        f"Chart candle: {chart_data.index[-1]} | "
        "Outlooks use daily data, even when the chart uses intraday candles."
    )

    has_volume = (
        "Volume" in chart_data.columns
        and chart_data["Volume"].notna().any()
    )

    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.82, 0.18] if has_volume else [1.0],
    )

    fig.add_trace(
        go.Candlestick(
            x=chart_data.index,
            open=chart_data["Open"],
            high=chart_data["High"],
            low=chart_data["Low"],
            close=chart_data["Close"],
            name="Price",
            increasing=dict(
                line=dict(color=UP_COLOR),
                fillcolor=UP_COLOR,
            ),
            decreasing=dict(
                line=dict(color=DOWN_COLOR),
                fillcolor=DOWN_COLOR,
            ),
        ),
        row=1,
        col=1,
    )

    if show_sma:
        fig.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=chart_data["SMA20"],
                name="SMA 20",
                line=dict(color="#f5a623", width=1.5),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=chart_data["SMA50"],
                name="SMA 50",
                line=dict(color="#4a90e2", width=1.5),
            ),
            row=1,
            col=1,
        )

    if has_volume:
        volume_colors = [
            UP_COLOR if close >= open_price else DOWN_COLOR
            for open_price, close in zip(
                chart_data["Open"], chart_data["Close"]
            )
        ]

        fig.add_trace(
            go.Bar(
                x=chart_data.index,
                y=chart_data["Volume"],
                name="Volume",
                marker_color=volume_colors,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        fig.update_yaxes(visible=False, row=2, col=1)

    breaks = [dict(bounds=["sat", "mon"])]

    if interval != "1d":
        breaks.append(dict(bounds=[16, 9.5], pattern="hour"))

    fig.update_xaxes(
        rangebreaks=breaks,
        showgrid=False,
        rangeslider_visible=False,
    )

    fig.update_yaxes(
        side="right",
        showgrid=True,
        gridcolor="#eeeeee",
        tickformat=",.2f",
        row=1,
        col=1,
    )

    fig.update_layout(
        template="plotly_white",
        height=550,
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📉 Short-Term Outlook Details")
    for reason in short_reasons:
        st.write(f"• {reason}")

    st.subheader("📈 Long-Term Outlook Details")

    st.write(
        f"Technical score: {score} | "
        f"Valid checks: {checks} of 2"
    )

    for reason in long_reasons:
        st.write(f"• {reason}")

    st.caption(
        "BUY, HOLD, and SELL are simplified technical classifications. "
        "They do not guarantee future price movements."
    )

    st.subheader("Candlestick Pattern Checks")
    for pattern in patterns:
        st.write(f"• {pattern}")

    st.subheader("RSI (14) Chart")

    rsi_fig = go.Figure()

    if not signal_data.empty:
        rsi_fig.add_trace(
            go.Scatter(
                x=signal_data.index,
                y=signal_data["RSI"],
                name="Daily RSI",
            )
        )

    rsi_fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="red",
    )
    rsi_fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="green",
    )

    rsi_fig.update_layout(
        template="plotly_white",
        height=280,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(range=[0, 100], side="right"),
    )

    st.plotly_chart(rsi_fig, use_container_width=True)

st.divider()

# =========================================================
# NEWS CENTER
# =========================================================

@st.cache_data(ttl=900)
def get_stock_news(symbol):
    try:
        items = yf.Ticker(symbol).news or []
        results = []

        for item in items:
            content = item.get("content", item)

            title = content.get("title", "Untitled news")
            summary = content.get("summary", "")
            publisher = content.get("publisher", "")

            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName", publisher)

            link = content.get("link", "")

            if not link:
                canonical = content.get("canonicalUrl", {})
                if isinstance(canonical, dict):
                    link = canonical.get("url", "")

            if not link:
                click_url = content.get("clickThroughUrl", {})
                if isinstance(click_url, dict):
                    link = click_url.get("url", "")

            published = (
                content.get("pubDate")
                or content.get("displayTime")
                or "Date unavailable"
            )

            results.append({
                "title": title,
                "summary": summary,
                "publisher": publisher or "Publisher unavailable",
                "published": str(published),
                "link": link,
            })

        return results

    except Exception:
        return []

st.header("📰 News & Earnings Center")

news_tab, earnings_tab = st.tabs([
    "📰 Stock News",
    "💰 Earnings & Financials",
])

with news_tab:
    st.subheader(f"Latest News — {ticker}")

    if st.button("🔄 Refresh news"):
        get_stock_news.clear()
        st.rerun()

    articles = get_stock_news(ticker)

    if not articles:
        st.info(
            "No news was returned. Try refreshing or check a "
            "financial news website."
        )

    for article in articles:
        with st.container(border=True):
            st.markdown(f"**{article['title']}**")
            st.caption(
                f"{article['publisher']} • {article['published']}"
            )

            if article["summary"]:
                st.write(article["summary"])

            link = article["link"]

            if link and urlparse(link).scheme in ("https", "http"):
                st.markdown(f"[Read full article]({link})")

# =========================================================
# EARNINGS AND FINANCIAL RESULTS
# =========================================================

@st.cache_data(ttl=3600)
def get_earnings_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        income = stock.quarterly_income_stmt

        financial_rows = []

        if income is not None and not income.empty:
            available = {
                str(index).lower(): index
                for index in income.index
            }

            def find_row(*names):
                for name in names:
                    if name.lower() in available:
                        return available[name.lower()]
                return None

            revenue_row = find_row("Total Revenue", "Operating Revenue")
            net_income_row = find_row(
                "Net Income",
                "Net Income Common Stockholders",
            )
            eps_row = find_row("Diluted EPS", "Basic EPS")
            operating_row = find_row("Operating Income")

            for date in income.columns:
                def value_for(row):
                    if row is None:
                        return None

                    value = income.loc[row, date]
                    return float(value) if pd.notna(value) else None

                financial_rows.append({
                    "Quarter End": str(pd.Timestamp(date).date()),
                    "Revenue ($)": value_for(revenue_row),
                    "Net Income ($)": value_for(net_income_row),
                    "Operating Income ($)": value_for(operating_row),
                    "EPS ($/share)": value_for(eps_row),
                })

        financials = pd.DataFrame(financial_rows)
        earnings_rows = []

        try:
            earnings = stock.get_earnings_dates(limit=12)

            if earnings is not None and not earnings.empty:
                for date, row in earnings.iterrows():
                    estimate = row.get("EPS Estimate")
                    actual = row.get("Reported EPS")
                    surprise = row.get("Surprise(%)")

                    earnings_rows.append({
                        "Earnings Date": str(date),
                        "EPS Estimate ($)": (
                            float(estimate) if pd.notna(estimate) else None
                        ),
                        "Reported EPS ($)": (
                            float(actual) if pd.notna(actual) else None
                        ),
                        "Surprise (%)": (
                            float(surprise) if pd.notna(surprise) else None
                        ),
                    })

        except Exception:
            pass

        return financials, pd.DataFrame(earnings_rows)

    except Exception:
        return pd.DataFrame(), pd.DataFrame()

with earnings_tab:
    st.subheader(f"{ticker} — Earnings & Financial Results")

    if st.button("🔄 Refresh earnings"):
        get_earnings_data.clear()
        st.rerun()

    financials, earnings = get_earnings_data(ticker)

    st.markdown("### Latest Quarterly Financial Results")

    if financials.empty:
        st.info(
            "Quarterly financial statements aren't available "
            "for this ticker right now."
        )
    else:
        latest = financials.iloc[0]

        def money(value):
            if value is None or pd.isna(value):
                return "N/A"
            return f"${value:,.0f}"

        def eps_money(value):
            if value is None or pd.isna(value):
                return "N/A"
            return f"${value:,.2f}"

        st.caption(f"Quarter ending: {latest['Quarter End']}")

        c1, c2 = st.columns(2)
        c1.metric("Revenue", money(latest["Revenue ($)"]))
        c2.metric("Net Income", money(latest["Net Income ($)"]))

        c3, c4 = st.columns(2)
        c3.metric(
            "Operating Income",
            money(latest["Operating Income ($)"]),
        )
        c4.metric("EPS", eps_money(latest["EPS ($/share)"]))

        st.markdown("### Previous Quarterly Results")
        st.dataframe(
            financials,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### 📊 Earnings: Estimate vs. Actual")

    if earnings.empty:
        st.info(
            "EPS estimates and reported earnings history aren't "
            "available right now."
        )
    else:
        st.dataframe(
            earnings,
            use_container_width=True,
            hide_index=True,
        )

# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Educational tool, not financial advice. Short-term and long-term "
    "outlooks are based on technical indicators, not guaranteed "
    "predictions. Yahoo Finance data may be delayed, incomplete, or "
    "stale. Verify prices and company information before making "
    "financial decisions."
)

if auto_refresh:
    st.caption(
        "Auto-refresh is enabled where supported by your Streamlit version. "
        "If it does not refresh automatically, use Refresh all data."
    )
