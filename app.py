import html as htmllib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote, urlparse

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

stock_bar_slot = st.container()
st.title("📈 Stock Signal Dashboard")
st.caption("Technical signals | Candlesticks | Watchlist | News | Earnings")

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
BAC WFC C GS MS BLK SCHW CBOE ICE CME AXP DFS BRK-B
CVNA ABNB BKNG EXPE DASH LYFT UPS FDX DAL UAL AAL LUV
CCL RCL MAR HLT T FUBO VZ TMUS CMCSA PARA WBD FOXA
PLD AMT EQIX REAL VICI SPG COP SLB OXY EOG MPC PSX KMI WMB
RSP IVV SPLG VUG VTV ARKK ARKG XLF XLK XLE XLV XLI XLY
XLP XLU XLRE SMH SOXX TQQQ SQQQ IBIT FBTC ETHA GLD SLV
USO UNG TLT HYG LQD
""".split()))

# =========================================================
# SIDEBAR SETTINGS
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

st.sidebar.caption(
    "For an intraday view, choose history 1d with interval 1m or 5m. "
    "Yahoo generally limits 1-minute history to about 7 days."
)

watchlist = st.sidebar.multiselect(
    "Watchlist",
    options=STOCK_OPTIONS,
    default=["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"],
)

custom_tickers = st.sidebar.text_input(
    "Add extra tickers",
    placeholder="Example: AMD, PLTR",
)

for symbol in custom_tickers.upper().replace(" ", "").split(","):
    if symbol and symbol not in watchlist:
        watchlist.append(symbol)

auto_refresh = st.sidebar.toggle("Auto-refresh live data", value=True)
show_sma = st.sidebar.toggle("Show SMA 20 / 50 lines", value=False)

if st.sidebar.button("🔄 Refresh all data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if not ticker:
    st.warning("Enter a stock ticker.")
    st.stop()

# =========================================================
# MARKET CLOCK
# =========================================================

@st.fragment(run_every="1s")
def show_market_clock():
    now = datetime.now(ZoneInfo("America/New_York"))

    opening = now.replace(hour=9, minute=30, second=0, microsecond=0)
    closing = now.replace(hour=16, minute=0, second=0, microsecond=0)

    is_open = now.weekday() < 5 and opening <= now < closing

    st.subheader("🕒 US Stock Market Clock")

    c1, c2, c3 = st.columns(3)
    c1.metric("Eastern Time", now.strftime("%I:%M:%S %p"))
    c2.metric("Market Opens", "9:30 AM")
    c3.metric("Market Closes", "4:00 PM")

    if is_open:
        st.success("🟢 REGULAR MARKET OPEN")

        remaining = max(0, int((closing - now).total_seconds()))
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.write(f"Time until close: {hours}h {minutes}m {seconds}s")
    else:
        st.info("🔴 REGULAR MARKET CLOSED")

        if now.weekday() < 5 and now < opening:
            next_open = now
        else:
            next_open = now + timedelta(days=1)

        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        st.write(
            f"Next weekday opening: {next_open.strftime('%A, %B %d')} "
            "at 9:30 AM ET."
        )

    st.caption(
        "Regular weekday hours only. Exchange holidays and early closures "
        "are not checked."
    )


show_market_clock()
st.divider()

# =========================================================
# STOCK PRICE DATA
# =========================================================

@st.cache_data(ttl=4, show_spinner=False)
def get_stock_data(symbol, history, candle_interval):
    try:
        df = yf.download(
            symbol,
            period=history,
            interval=candle_interval,
            auto_adjust=False,
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

    except Exception:
        return pd.DataFrame()


# =========================================================
# TECHNICAL INDICATORS
# =========================================================

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
    df["RSI"] = 100 - (100 / (1 + rs))

    df.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100
    df.loc[(avg_gain == 0) & (avg_loss > 0), "RSI"] = 0
    df.loc[(avg_gain == 0) & (avg_loss == 0), "RSI"] = 50

    return df


# =========================================================
# BUY / HOLD / SELL SIGNAL
# =========================================================

def calculate_signal(df):
    if len(df) < 2:
        return "INSUFFICIENT DATA", 0, 0, ["Not enough candles."]

    last = df.iloc[-1]
    price = float(last["Close"])
    sma20 = last["SMA20"]
    sma50 = last["SMA50"]
    rsi = last["RSI"]

    score = 0
    checks = 0
    reasons = []

    if pd.notna(sma20):
        checks += 1

        if price > float(sma20):
            score += 1
            reasons.append("Price is above SMA20 (bullish).")
        elif price < float(sma20):
            score -= 1
            reasons.append("Price is below SMA20 (bearish).")
        else:
            reasons.append("Price equals SMA20.")
    else:
        reasons.append("SMA20 needs more candles.")

    if pd.notna(sma20) and pd.notna(sma50):
        checks += 1

        if float(sma20) > float(sma50):
            score += 1
            reasons.append("SMA20 is above SMA50 (bullish).")
        elif float(sma20) < float(sma50):
            score -= 1
            reasons.append("SMA20 is below SMA50 (bearish).")
        else:
            reasons.append("Moving averages are equal.")
    else:
        reasons.append("Moving averages need more data.")

    if pd.notna(rsi):
        checks += 1
        rsi = float(rsi)

        if rsi < 30:
            score += 1
            reasons.append(f"RSI {rsi:.1f}: commonly considered oversold.")
        elif rsi > 70:
            score -= 1
            reasons.append(f"RSI {rsi:.1f}: commonly considered overbought.")
        else:
            reasons.append(f"RSI is {rsi:.1f}, within 30–70.")
    else:
        reasons.append("RSI needs more candles.")

    if checks < 2:
        signal = "INSUFFICIENT DATA"
    elif score >= 2:
        signal = "BUY"
    elif score <= -2:
        signal = "SELL"
    else:
        signal = "HOLD"

    return signal, score, checks, reasons


# =========================================================
# CANDLESTICK PATTERNS
# =========================================================

def detect_patterns(df):
    if len(df) < 2:
        return ["Not enough candles."]

    current = df.iloc[-1]
    previous = df.iloc[-2]

    o, h, low, c = map(
        float,
        [
            current["Open"],
            current["High"],
            current["Low"],
            current["Close"],
        ],
    )

    po = float(previous["Open"])
    pc = float(previous["Close"])

    body = abs(c - o)
    previous_body = abs(pc - po)
    candle_range = max(h - low, 1e-9)

    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - low

    patterns = []

    if (
        pc < po and c > o and o <= pc and c >= po
        and body >= previous_body
    ):
        patterns.append("Possible bullish engulfing.")

    if (
        pc > po and c < o and o >= pc and c <= po
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
# QUOTE FIX: ONE SHARED PRICE SOURCE
# =========================================================

@st.cache_data(ttl=8, show_spinner=False)
def get_quote(symbol):
    """
    Returns:
    latest available intraday price,
    previous regular-session close,
    quote timestamp.

    Yahoo Finance data can be delayed or incomplete.
    """
    try:
        intraday = yf.download(
            symbol,
            period="5d",
            interval="1m",
            prepost=True,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        daily = yf.download(
            symbol,
            period="10d",
            interval="1d",
            prepost=False,
            auto_adjust=False,
            progress=False,
            threads=False,
        )

        def clean_prices(df):
            if df is None or df.empty:
                return pd.DataFrame()

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.loc[:, ~df.columns.duplicated()].copy()

            if "Close" not in df.columns:
                return pd.DataFrame()

            df["Close"] = pd.to_numeric(df["Close"], errors="coerce")

            return df.dropna(subset=["Close"]).sort_index()

        intraday = clean_prices(intraday)
        daily = clean_prices(daily)

        if not intraday.empty:
            latest_time = pd.Timestamp(intraday.index[-1])
            price = float(intraday["Close"].iloc[-1])
            quote_day = latest_time.date()

            previous = None

            for timestamp, close in zip(daily.index, daily["Close"]):
                if pd.Timestamp(timestamp).date() < quote_day:
                    previous = float(close)

            if previous is None and len(daily) >= 2:
                previous = float(daily["Close"].iloc[-2])

            if previous is not None and previous > 0 and price > 0:
                return (
                    price,
                    previous,
                    latest_time.strftime("%I:%M:%S %p"),
                )

        # Fallback if intraday data is unavailable.
        if len(daily) >= 2:
            return (
                float(daily["Close"].iloc[-1]),
                float(daily["Close"].iloc[-2]),
                str(pd.Timestamp(daily.index[-1]).date()),
            )

        return None

    except Exception:
        return None


# =========================================================
# DAILY CLOSES
# =========================================================

@st.cache_data(ttl=600, show_spinner=False)
def get_daily_closes(symbol):
    df = get_stock_data(symbol, "10d", "1d")

    if df.empty:
        return []

    return [
        (pd.Timestamp(date).date(), float(close))
        for date, close in zip(df.index, df["Close"])
    ]


# =========================================================
# STOCK BAR STYLING
# =========================================================

INDEX_BAR_CSS = """
<style>
.idx-wrap {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
    margin: 0 0 6px 0;
}
.idx-card {
    position: relative;
    width: 100%;
    min-width: 0;
    min-height: 76px;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 10px;
    background: #161616;
    border: 1px solid #303030;
    border-radius: 10px;
    overflow: hidden;
}
.idx-logo {
    width: 40px;
    height: 40px;
    min-width: 40px;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 11px;
    flex-shrink: 0;
}
.idx-details {
    min-width: 0;
    flex: 1 1 auto;
    overflow: hidden;
}
.idx-name {
    color: #a7a7a7;
    font-size: 11px;
    line-height: 1.25;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.idx-price {
    color: #ffffff;
    font-size: 15px;
    line-height: 1.35;
    font-weight: 700;
    white-space: nowrap;
}
.idx-chg {
    font-size: 10px;
    line-height: 1.3;
    font-weight: 600;
    overflow-wrap: anywhere;
}
.idx-up { color: #2ecc71; }
.idx-down { color: #ff6b6b; }
.idx-flat { color: #9a9a9a; }
.idx-badge {
    position: absolute;
    top: 5px;
    right: 6px;
    font-size: 9px;
    line-height: 1;
    font-weight: 700;
    padding: 4px 5px;
    border-radius: 5px;
}
.idx-badge.idx-up { background: #12361f; color: #2ecc71; }
.idx-badge.idx-down { background: #3a1616; color: #ff6b6b; }
.idx-badge.idx-flat { background: #262626; color: #9a9a9a; }
@media (max-width: 900px) {
    .idx-card { padding: 8px; gap: 7px; }
    .idx-logo {
        width: 34px;
        height: 34px;
        min-width: 34px;
        font-size: 10px;
    }
    .idx-price { font-size: 13px; }
    .idx-chg { font-size: 9px; }
}
</style>
"""

DEFAULT_TOP_STOCKS = ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"]

KNOWN_NAMES = {
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "AMZN": "Amazon",
}

KNOWN_STYLES = {
    "MSFT": ("#00a4ef", "#ffffff"),
    "AAPL": ("#a2aaad", "#111111"),
    "NVDA": ("#76b900", "#111111"),
    "TSLA": ("#cc0000", "#ffffff"),
    "AMZN": ("#ff9900", "#111111"),
}


def parse_stock_list(text):
    output = []

    for item in (text or "").upper().replace(" ", "").split(","):
        if item and item not in output:
            output.append(item)

    return output[:5]


if "top_stocks" not in st.session_state:
    saved = parse_stock_list(st.query_params.get("stocks", ""))

    if saved:
        filler = [item for item in DEFAULT_TOP_STOCKS if item not in saved]
        st.session_state["top_stocks"] = (saved + filler)[:5]
    else:
        st.session_state["top_stocks"] = list(DEFAULT_TOP_STOCKS)


@st.cache_data(ttl=86400, show_spinner=False)
def get_company_name(symbol):
    if symbol in KNOWN_NAMES:
        return KNOWN_NAMES[symbol]

    try:
        info = yf.Ticker(symbol).info
        return info.get("shortName") or info.get("longName") or symbol
    except Exception:
        return symbol


def logo_colors(symbol):
    if symbol in KNOWN_STYLES:
        return KNOWN_STYLES[symbol]

    hue = (sum(ord(ch) for ch in symbol) * 37) % 360
    return f"hsl({hue},65%,45%)", "#ffffff"


# =========================================================
# LIVE STOCK BAR
# =========================================================

@st.fragment(run_every="10s" if auto_refresh else None)
def show_stock_bar():
    symbols = st.session_state["top_stocks"]
    cols = st.columns(5, gap="small")

    for col, symbol in zip(cols, symbols):
        quote_data = get_quote(symbol)
        bg, fg = logo_colors(symbol)
        company = get_company_name(symbol)[:20]

        if quote_data is None:
            price_text = "N/A"
            change_text = "No quote"
            badge = "–"
            css_class = "idx-flat"
        else:
            price, previous, _ = quote_data
            change = price - previous
            pct = (price / previous - 1) * 100 if previous else 0

            price_text = f"${price:,.2f}"
            change_text = f"{change:+.2f} ({pct:+.2f}%)"

            if change > 0:
                css_class = "idx-up"
                badge = "▲"
            elif change < 0:
                css_class = "idx-down"
                badge = "▼"
            else:
                css_class = "idx-flat"
                badge = "–"

        card = (
            '<div class="idx-wrap"><div class="idx-card">'
            f'<div class="idx-logo" style="background:{bg};color:{fg};">'
            f'{htmllib.escape(symbol[:5])}</div>'
            '<div class="idx-details">'
            f'<div class="idx-name">{htmllib.escape(company)}</div>'
            f'<div class="idx-price">{price_text}</div>'
            f'<div class="idx-chg {css_class}">{change_text}</div>'
            '</div>'
            f'<div class="idx-badge {css_class}">{badge}</div>'
            '</div></div>'
        )

        with col:
            st.markdown(INDEX_BAR_CSS + card, unsafe_allow_html=True)


@st.fragment(run_every="10s" if auto_refresh else None)
def show_bar_status():
    now_et = datetime.now(ZoneInfo("America/New_York"))

    st.caption(
        f"Yahoo Finance quote | Last checked "
        f"{now_et.strftime('%I:%M:%S %p')} ET | "
        "Data may be delayed."
    )


with stock_bar_slot:
    show_stock_bar()

    current_stocks = st.session_state["top_stocks"]
    edit_cols = st.columns(5, gap="small")

    for i, (col, current) in enumerate(zip(edit_cols, current_stocks)):
        with col:
            with st.popover(
                f"✏️ Change {current}",
                use_container_width=True,
            ):
                new_symbol = st.text_input(
                    "New ticker",
                    key=f"new_ticker_{i}_{current}",
                    placeholder="Example: AMD",
                )

                if st.button("Apply", key=f"apply_ticker_{i}_{current}"):
                    symbol = new_symbol.strip().upper()

                    if not symbol:
                        st.warning("Type a ticker first.")
                    elif symbol in current_stocks:
                        st.warning(f"{symbol} is already in the bar.")
                    elif get_quote(symbol) is None:
                        st.error(f"No data found for {symbol}. Check the ticker.")
                    else:
                        st.session_state["top_stocks"][i] = symbol
                        st.query_params["stocks"] = ",".join(
                            st.session_state["top_stocks"]
                        )
                        st.rerun()

    show_bar_status()


# =========================================================
# WATCHLIST — USE THE SAME QUOTE AS THE TOP BAR
# =========================================================

@st.fragment(run_every="60s" if auto_refresh else None)
def show_watchlist():
    st.subheader("⭐ Watchlist")

    if not watchlist:
        st.info("Select stocks in the sidebar.")
        return

    rows = []
    progress = st.progress(0)
    status = st.empty()

    for i, symbol in enumerate(watchlist):
        status.caption(f"Loading {symbol} ({i + 1}/{len(watchlist)})")

        df = get_stock_data(symbol, "3mo", "1d")

        if df.empty or len(df) < 2:
            rows.append({
                "Ticker": symbol,
                "Price": "Unavailable",
                "Daily Change": "N/A",
                "RSI": "N/A",
                "Signal": "NO DATA",
            })
        else:
            data = add_indicators(df)
            signal, _, _, _ = calculate_signal(data)
            quote_data = get_quote(symbol)
            rsi = data["RSI"].iloc[-1]

            if quote_data is not None:
                current, previous, _ = quote_data
                price_text = f"${current:,.2f}"
                pct = (current / previous - 1) * 100 if previous else 0
                change_text = f"{pct:+.2f}%"
            else:
                price_text = "Unavailable"
                change_text = "N/A"

            rows.append({
                "Ticker": symbol,
                "Price": price_text,
                "Daily Change": change_text,
                "RSI": f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",
                "Signal": signal,
            })

        progress.progress((i + 1) / len(watchlist))

    progress.empty()
    status.empty()

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Price and daily change use the shared quote function. "
        "RSI and technical signals use daily candles. "
        "Yahoo Finance data may be delayed."
    )


show_watchlist()
st.divider()

# =========================================================
# MAIN CHART
# =========================================================

@st.fragment(run_every="15s" if auto_refresh else None)
def show_main_chart():
    st.subheader(f"📊 Main Stock: {ticker}")

    raw = get_stock_data(ticker, period, interval)

    if raw.empty or len(raw) < 2:
        st.error(
            "No usable data found. Check the ticker, connection, "
            "or selected candle interval."
        )
        return

    data = add_indicators(raw)
    signal, score, checks, reasons = calculate_signal(data)
    patterns = detect_patterns(data)

    last = data.iloc[-1]
    rsi = last["RSI"]
    quote_data = get_quote(ticker)

    if quote_data is not None:
        price, previous, quote_time = quote_data
        price_label = "Latest Quote"
    else:
        price = float(last["Close"])
        previous = float(data["Close"].iloc[-2])
        quote_time = str(data.index[-1])
        price_label = "Latest Candle Close"

    change_pct = (price / previous - 1) * 100 if previous else 0

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(price_label, f"${price:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("Technical Signal", signal)
    c3.metric(
        "RSI (14)",
        f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",
    )
    c4.metric(
        "SMA 20",
        f"${float(last['SMA20']):,.2f}"
        if pd.notna(last["SMA20"]) else "N/A",
    )

    st.caption(
        f"Quote time: {quote_time} | The candlestick chart uses your "
        "selected candle interval, so its last candle can differ from "
        "the latest quote. Yahoo Finance data may be delayed."
    )

    green = "#238a23"
    red = "#d6404f"
    has_volume = "Volume" in data.columns

    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.82, 0.18] if has_volume else [1.0],
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price",
            increasing=dict(
                line=dict(color=green, width=1),
                fillcolor=green,
            ),
            decreasing=dict(
                line=dict(color=red, width=1),
                fillcolor=red,
            ),
            whiskerwidth=0,
        ),
        row=1,
        col=1,
    )

    if show_sma:
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["SMA20"],
                name="SMA 20",
                line=dict(color="#f5a623", width=1.2),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["SMA50"],
                name="SMA 50",
                line=dict(color="#4a90e2", width=1.2),
            ),
            row=1,
            col=1,
        )

    if has_volume:
        colors = [
            green if close >= op else red
            for op, close in zip(data["Open"], data["Close"])
        ]

        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                name="Volume",
                marker=dict(color=colors),
                opacity=0.55,
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
        showline=True,
        linecolor="#ddd",
    )

    fig.update_yaxes(
        side="right",
        showgrid=True,
        gridcolor="#eee",
        zeroline=False,
        tickformat=",.2f",
        row=1,
        col=1,
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#333"),
        height=550,
        margin=dict(l=20, r=20, t=20, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=0),
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Why this signal was generated")
    st.write(f"Technical score: {score} | Valid checks: {checks} of 3")

    for reason in reasons:
        st.write("• " + reason)

    st.subheader("Candlestick Pattern Checks")

    for pattern in patterns:
        st.write("• " + pattern)

    st.subheader("RSI (14) Chart")

    rsi_fig = go.Figure()

    rsi_fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["RSI"],
            name="RSI",
        )
    )

    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")

    rsi_fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#333"),
        height=260,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(range=[0, 100], side="right", gridcolor="#eee"),
        xaxis=dict(showgrid=False),
    )

    st.plotly_chart(rsi_fig, use_container_width=True)


show_main_chart()
st.divider()

# =========================================================
# NEWS
# =========================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_stock_news(symbol):
    try:
        items = yf.Ticker(symbol).news or []
        rows = []

        for item in items:
            content = item.get("content", item) if isinstance(item, dict) else {}

            title = content.get("title") or item.get("title", "Untitled news")

            provider = content.get("provider")
            publisher = (
                provider.get("displayName", "")
                if isinstance(provider, dict)
                else item.get("publisher", "")
            )

            published = (
                content.get("pubDate")
                or content.get("displayTime")
                or item.get("providerPublishTime")
            )

            if isinstance(published, (int, float)):
                published = datetime.fromtimestamp(
                    published,
                    tz=ZoneInfo("UTC"),
                ).strftime("%Y-%m-%d %H:%M UTC")
            elif not published:
                published = "Date unavailable"
            else:
                published = str(published)

            link = content.get("link", "")

            if not link:
                canonical = content.get("canonicalUrl", {})
                if isinstance(canonical, dict):
                    link = canonical.get("url", "")

            if not link:
                click_url = content.get("clickThroughUrl", {})
                if isinstance(click_url, dict):
                    link = click_url.get("url", "")

            rows.append({
                "Headline": title,
                "Publisher": publisher or "Publisher unavailable",
                "Published": published,
                "Summary": content.get("summary", ""),
                "Link": link or "",
            })

        return rows

    except Exception:
        return []


def show_news(symbol):
    st.subheader(f"📰 Latest News — {symbol}")

    if st.button("🔄 Refresh news", key=f"news_{symbol}"):
        get_stock_news.clear()
        st.rerun()

    items = get_stock_news(symbol)

    if not items:
        st.info("No news was returned. Try refreshing or check a financial news website.")
        return

    for article in items:
        with st.container(border=True):
            st.markdown(f"**{article['Headline']}**")
            st.caption(f"{article['Publisher']} • {article['Published']}")

            if article["Summary"]:
                st.write(article["Summary"])

            link = article["Link"]

            if link and urlparse(link).scheme in ("https", "http"):
                st.markdown(f"[Read full article]({link})")


# =========================================================
# EARNINGS & FINANCIAL RESULTS
# =========================================================

@st.cache_data(ttl=3600, show
