
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

st.title("📈 Stock Signal Dashboard")
st.caption("Stock prices | Candlestick charts | Signals | Watchlist | News | Earnings")

# =========================================================
# SIDEBAR
# =========================================================

STOCK_OPTIONS = sorted(set("""
AAPL MSFT NVDA TSLA AMZN GOOGL GOOG META AMD INTC PLTR NFLX
AVGO ORCL CRM JPM V MA WMT COST KO PEP DIS UBER SHOP COIN
HOOD SOFI MSTR SMCI ARM MU QCOM ADBE CSCO IBM TSM LLY NVO
XOM CVX BA F GM SPY QQQ DIA IWM VOO VTI SCHD JEPI JEPQ
ASML ANET PANW CRWD NOW SNOW NET DDOG MDB RBLX U RIVN LCID
AMAT LRCX KLAC MRVL TXN ADI ON NXPI SNPS CDNS INTU ACN
WDAY TEAM ZM DOCU TWLO PATH IONQ RGTI QUBT ASTS RKLB LUNR
LMT RTX NOC GD CAT DE HON GE ETN UNH JNJ ABBV MRK PFE
AMGN GILD REGN ISRG BSX TGT HD LOW MCD SBUX CMG YUM NKE
LULU TJX ROST CAVA CELH MNST PM MO CL PG EL MDLZ GIS
BAC WFC C GS MS BLK SCHW CBOE ICE CME AXP DFS BRK-B
CVNA ABNB BKNG EXPE DASH LYFT UPS FDX DAL UAL AAL LUV
CCL RCL MAR HLT PLD AMT EQIX REAL VICI SPG COP SLB OXY
EOG MPC PSX KMI WMB RSP IVV SPLG VUG VTV ARKK ARKG XLF
XLK XLE XLV XLI XLY XLP XLU XLRE SMH SOXX TQQQ SQQQ
IBIT FBTC ETHA GLD SLV USO UNG TLT HYG LQD
""".split()))

st.sidebar.header("Stock Settings")

ticker = st.sidebar.text_input(
    "Main chart ticker",
    value="MSFT",
).strip().upper()

period = st.sidebar.selectbox(
    "Chart history",
    ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
    index=3,
)

interval = st.sidebar.selectbox(
    "Candle interval",
    ["1d", "1h", "30m", "15m", "5m", "1m"],
    index=0,
)

watchlist = st.sidebar.multiselect(
    "Watchlist",
    STOCK_OPTIONS,
    default=["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"],
)

extra_tickers = st.sidebar.text_input(
    "Add extra tickers",
    placeholder="AMD, PLTR",
)

for symbol in extra_tickers.upper().replace(" ", "").split(","):
    if symbol and symbol not in watchlist:
        watchlist.append(symbol)

auto_refresh = st.sidebar.toggle(
    "Auto-refresh",
    value=True,
)

show_sma = st.sidebar.toggle(
    "Show SMA 20 / SMA 50",
    value=True,
)

if st.sidebar.button("Refresh all data"):
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

    opening = now.replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    closing = now.replace(
        hour=16, minute=0, second=0, microsecond=0
    )

    market_open = (
        now.weekday() < 5
        and opening <= now < closing
    )

    st.subheader("🕒 US Stock Market Clock")

    c1, c2, c3 = st.columns(3)

    c1.metric("Eastern Time", now.strftime("%I:%M:%S %p"))
    c2.metric("Market Opens", "9:30 AM ET")
    c3.metric("Market Closes", "4:00 PM ET")

    if market_open:
        st.success("🟢 REGULAR MARKET OPEN")
        remaining = int((closing - now).total_seconds())
        hours, remainder = divmod(remaining, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.write(
            f"Time until close: {hours}h {minutes}m {seconds}s"
        )
    else:
        st.info("🔴 REGULAR MARKET CLOSED")

    st.caption(
        "The clock uses Eastern Time. Exchange holidays and early "
        "closures are not included."
    )


show_market_clock()
st.divider()

# =========================================================
# STOCK DATA
# =========================================================

@st.cache_data(ttl=5, show_spinner=False)
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

        return df.dropna(subset=required).sort_index()

    except Exception:
        return pd.DataFrame()


# =========================================================
# SHARED LIVE QUOTE FUNCTION
# Used by the top bar, watchlist, and main chart.
# =========================================================

@st.cache_data(ttl=8, show_spinner=False)
def get_quote(symbol):
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

            df["Close"] = pd.to_numeric(
                df["Close"],
                errors="coerce",
            )

            return df.dropna(subset=["Close"]).sort_index()

        intraday = clean_prices(intraday)
        daily = clean_prices(daily)

        if not intraday.empty:
            latest_time = pd.Timestamp(intraday.index[-1])
            price = float(intraday["Close"].iloc[-1])
            quote_day = latest_time.date()

            previous = None

            for timestamp, close in zip(
                daily.index,
                daily["Close"],
            ):
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
        return "INSUFFICIENT DATA", 0, 0, [
            "Not enough candles to calculate a signal."
        ]

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
            reasons.append("Price is above SMA20.")
        elif price < float(sma20):
            score -= 1
            reasons.append("Price is below SMA20.")
        else:
            reasons.append("Price equals SMA20.")
    else:
        reasons.append("Not enough data for SMA20.")

    if pd.notna(sma20) and pd.notna(sma50):
        checks += 1

        if float(sma20) > float(sma50):
            score += 1
            reasons.append("SMA20 is above SMA50.")
        elif float(sma20) < float(sma50):
            score -= 1
            reasons.append("SMA20 is below SMA50.")
        else:
            reasons.append("SMA20 equals SMA50.")
    else:
        reasons.append("Not enough data for both moving averages.")

    if pd.notna(rsi):
        checks += 1
        rsi = float(rsi)

        if rsi < 30:
            score += 1
            reasons.append(
                f"RSI is {rsi:.1f}, commonly considered oversold."
            )
        elif rsi > 70:
            score -= 1
            reasons.append(
                f"RSI is {rsi:.1f}, commonly considered overbought."
            )
        else:
            reasons.append(f"RSI is {rsi:.1f}, between 30 and 70.")
    else:
        reasons.append("Not enough data for RSI.")

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
        pc < po
        and c > o
        and o <= pc
        and c >= po
        and body >= previous_body
    ):
        patterns.append("Possible bullish engulfing.")

    if (
        pc > po
        and c < o
        and o >= pc
        and c <= po
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
# STOCK BAR
# =========================================================

DEFAULT_TOP_STOCKS = ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"]

KNOWN_NAMES = {
    "MSFT": "Microsoft",
    "AAPL": "Apple",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "AMZN": "Amazon",
}

KNOWN_COLORS = {
    "MSFT": ("#00a4ef", "#ffffff"),
    "AAPL": ("#a2aaad", "#111111"),
    "NVDA": ("#76b900", "#111111"),
    "TSLA": ("#cc0000", "#ffffff"),
    "AMZN": ("#ff9900", "#111111"),
}

if "top_stocks" not in st.session_state:
    st.session_state["top_stocks"] = DEFAULT_TOP_STOCKS.copy()


def get_company_name(symbol):
    if symbol in KNOWN_NAMES:
        return KNOWN_NAMES[symbol]

    return symbol


def logo_colors(symbol):
    if symbol in KNOWN_COLORS:
        return KNOWN_COLORS[symbol]

    hue = (sum(ord(ch) for ch in symbol) * 37) % 360
    return f"hsl({hue},65%,45%)", "#ffffff"


@st.fragment(run_every="10s" if auto_refresh else None)
def show_stock_bar():
    st.subheader("📌 Stock Price Bar")

    cols = st.columns(5)

    for i, symbol in enumerate(st.session_state["top_stocks"]):
        quote_data = get_quote(symbol)
        bg, fg = logo_colors(symbol)

        with cols[i]:
            st.markdown(
                f"""
                <div style="
                    border:1px solid #444;
                    border-radius:10px;
                    padding:12px;
                    background:#161616;
                    color:white;
                    min-height:110px;
                ">
                    <div style="
                        display:inline-block;
                        background:{bg};
                        color:{fg};
                        padding:6px 8px;
                        border-radius:6px;
                        font-weight:bold;
                    ">{htmllib.escape(symbol)}</div>
                    <div style="margin-top:8px;font-size:12px;color:#aaa;">
                        {htmllib.escape(get_company_name(symbol))}
                    </div>
                """,
                unsafe_allow_html=True,
            )

            if quote_data is None:
                st.markdown("**Price unavailable**")
            else:
                price, previous, quote_time = quote_data
                change_pct = (
                    (price / previous - 1) * 100 if previous else 0
                )

                color = (
                    "#2ecc71" if change_pct > 0
                    else "#ff6b6b" if change_pct < 0
                    else "#aaaaaa"
                )

                st.markdown(
                    f"""
                    <div style="font-size:18px;font-weight:bold;color:white;">
                        ${price:,.2f}
                    </div>
                    <div style="font-size:13px;color:{color};">
                        {change_pct:+.2f}%
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("</div>", unsafe_allow_html=True)

    st.caption("Prices may be delayed by Yahoo Finance.")


show_stock_bar()

# Allow changing the five tickers.
with st.expander("✏️ Customize the stock bar"):
    edit_cols = st.columns(5)

    for i, col in enumerate(edit_cols):
        with col:
            new_symbol = st.text_input(
                f"Stock {i + 1}",
                value=st.session_state["top_stocks"][i],
                key=f"top_stock_edit_{i}",
            ).strip().upper()

            if new_symbol:
                st.session_state["top_stocks"][i] = new_symbol

st.divider()

# =========================================================
# WATCHLIST — FIXED TO USE THE SHARED QUOTE
# =========================================================

@st.fragment(run_every="60s" if auto_refresh else None)
def show_watchlist():
    st.subheader("⭐ Watchlist")

    if not watchlist:
        st.info("Choose stocks from the sidebar.")
        return

    rows = []
    progress = st.progress(0)

    for i, symbol in enumerate(watchlist):
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

                change_pct = (
                    (current / previous - 1) * 100
                    if previous else 0
                )

                price_text = f"${current:,.2f}"
                change_text = f"{change_pct:+.2f}%"
            else:
                price_text = "Unavailable"
                change_text = "N/A"

            rows.append({
                "Ticker": symbol,
                "Price": price_text,
                "Daily Change": change_text,
                "RSI": (
                    f"{float(rsi):.1f}"
                    if pd.notna(rsi) else "N/A"
                ),
                "Signal": signal,
            })

        progress.progress((i + 1) / len(watchlist))

    progress.empty()

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Watchlist prices use the shared quote function. "
        "RSI and technical signals use daily candles."
    )


show_watchlist()
st.divider()

# =========================================================
# MAIN STOCK CHART
# =========================================================

@st.fragment(run_every="15s" if auto_refresh else None)
def show_main_chart():
    st.subheader(f"📊 Main Stock: {ticker}")

    raw = get_stock_data(ticker, period, interval)

    if raw.empty or len(raw) < 2:
        st.error(
            "No stock data found. Check the ticker, history, "
            "or candle interval."
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

    change_pct = (
        (price / previous - 1) * 100 if previous else 0
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        price_label,
        f"${price:,.2f}",
        f"{change_pct:+.2f}%",
    )

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
        f"Quote timestamp: {quote_time}. "
        "The latest quote and latest chart candle may differ because "
        "they use different intervals. Yahoo Finance data may be delayed."
    )

    has_volume = "Volume" in data.columns

    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.8, 0.2] if has_volume else [1.0],
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Candlesticks",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
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
                line=dict(color="orange", width=1.5),
            ),
            row=1,
            col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data["SMA50"],
                name="SMA 50",
                line=dict(color="royalblue", width=1.5),
            ),
            row=1,
            col=1,
        )

    if has_volume:
        volume_colors = [
            "#26a69a" if close >= opening else "#ef5350"
            for opening, close in zip(data["Open"], data["Close"])
        ]

        fig.add_trace(
            go.Bar(
                x=data.index,
                y=data["Volume"],
                marker_color=volume_colors,
                name="Volume",
                showlegend=False,
            ),
            row=2,
            col=1,
        )

        fig.update_yaxes(visible=False, row=2, col=1)

    fig.update_layout(
        template="plotly_dark",
        height=600,
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        margin=dict(l=10, r=10, t=25, b=10),
        legend=dict(orientation="h"),
    )

    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📈 RSI (14)")

    rsi_fig = go.Figure()

    rsi_fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["RSI"],
            name="RSI",
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
        template="plotly_dark",
        height=280,
        yaxis=dict(range=[0, 100]),
    )

    st.plotly_chart(rsi_fig, use_container_width=True)

    st.subheader("🤖 Signal Explanation")

    st.write(f"Signal: **{signal}**")
    st.write(f"Technical score: {score} | Available checks: {checks}/3")

    for reason in reasons:
        st.write("• " + reason)

    st.subheader("🕯️ Candlestick Pattern Checks")

    for pattern in patterns:
        st.write("• " + pattern)


show_main_chart()
st.divider()

# =========================================================
# STOCK NEWS
# =========================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_stock_news(symbol):
    try:
        items = yf.Ticker(symbol).news or []
        results = []

        for item in items:
            content = (
                item.get("content", item)
                if isinstance(item, dict)
                else {}
            )

            title = (
                content.get("title")
                or item.get("title", "Untitled article")
            )

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

            link = content.get("link", "")

            if not link:
                canonical = content.get("canonicalUrl", {})

                if isinstance(canonical, dict):
                    link = canonical.get("url", "")

            if not link:
                click_url = content.get("clickThroughUrl", {})

                if isinstance(click_url, dict):
                    link = click_url.get("url", "")

            results.append({
                "Headline": title,
                "Publisher": publisher or "Publisher unavailable",
                "Published": str(published),
                "Summary": content.get("summary", ""),
                "Link": link or "",
            })

        return results

    except Exception:
        return []


def show_news(symbol):
    st.subheader(f"📰 Latest News — {symbol}")

    articles = get_stock_news(symbol)

    if not articles:
        st.info(
            "No news returned. Try refreshing or checking another ticker."
        )
        return

    for article in articles:
        with st.container(border=True):
            st.markdown(f"**{article['Headline']}**")

            st.caption(
                f"{article['Publisher']} • {article['Published']}"
            )

            if article["Summary"]:
                st.write(article["Summary"])

            link = article["Link"]

            if (
                link
                and urlparse(link).scheme in ("https", "http")
            ):
                st.markdown(f"[Read full article]({link})")


# =========================================================
# EARNINGS AND FINANCIAL RESULTS
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        income = stock.quarterly_income_stmt
        financial_rows = []

        if income is not None and not income.empty:
            lookup = {
                str(index).strip().lower(): index
                for index in income.index
            }

            def find_row(*names):
                for name in names:
                    if name.lower() in lookup:
                        return lookup[name.lower()]

                for name in names:
                    for key, original in lookup.items():
                        if name.lower() in key:
                            return original

                return None

            revenue_row = find_row(
                "Total Revenue",
                "Operating Revenue",
                "Revenue",
            )

            net_income_row = find_row(
                "Net Income",
                "Net Income Common Stockholders",
                "Net Income Continuous Operations",
            )

            operating_row = find_row("Operating Income")
            eps_row = find_row("Diluted EPS", "Basic EPS")

            for date in sorted(income.columns, reverse=True):

                def get_value(row):
                    if row is None:
                        return None

                    try:
                        value = income.loc[row, date]
                        return (
                            float(value)
                            if pd.notna(value)
                            else None
                        )
                    except (TypeError, ValueError, KeyError):
                        return None

                financial_rows.append({
                    "Quarter End": str(pd.Timestamp(date).date()),
                    "Revenue ($)": get_value(revenue_row),
                    "Net Income ($)": get_value(net_income_row),
                    "Operating Income ($)": get_value(operating_row),
                    "EPS ($)": get_value(eps_row),
                })

        financials = pd.DataFrame(financial_rows)
        earnings_rows = []

        try:
            dates = stock.get_earnings_dates(limit=12)

            if dates is not None and not dates.empty:
                for date, row in dates.iterrows():
                    estimate = row.get("EPS Estimate")
                    actual = row.get("Reported EPS")
                    surprise = row.get("Surprise(%)")

                    earnings_rows.append({
                        "Earnings Date": str(date),
                        "EPS Estimate": (
                            float(estimate)
                            if pd.notna(estimate) else None
                        ),
                        "Reported EPS": (
                            float(actual)
                            if pd.notna(actual) else None
                        ),
                        "Surprise (%)": (
                            float(surprise)
                            if pd.notna(surprise) else None
                        ),
                    })

        except Exception:
            pass

        return financials, pd.DataFrame(earnings_rows)

    except Exception:
        return pd.DataFrame(), pd.DataFrame()


def format_money(value):
    if value is None or pd.isna(value):
        return "N/A"

    value = float(value)
    absolute = abs(value)

    if absolute >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:,.2f}T"

    if absolute >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"

    if absolute >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"

    return f"${value:,.0f}"


def show_earnings(symbol):
    st.subheader(f"💰 {symbol} — Earnings & Financials")

    st.caption(
        "Revenue is money earned from sales; net income is profit "
        "after expenses. Financial data may be delayed or incomplete."
    )

    financials, earnings = get_earnings_data(symbol)

    st.markdown("### Quarterly Financial Results")

    if financials.empty:
        st.info("Quarterly financial statements are unavailable.")
    else:
        latest = financials.iloc[0]

        st.caption(f"Latest quarter ending: {latest['Quarter End']}")

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Revenue",
            format_money(latest["Revenue ($)"]),
        )

        c2.metric(
            "Net Income",
            format_money(latest["Net Income ($)"]),
        )

        c3.metric(
            "Operating Income",
            format_money(latest["Operating Income ($)"]),
        )

        eps = latest["EPS ($)"]

        c4.metric(
            "EPS",
            "N/A" if eps is None or pd.isna(eps)
            else f"${float(eps):,.2f}",
        )

        display = financials.copy()

        for column in [
            "Revenue ($)",
            "Net Income ($)",
            "Operating Income ($)",
        ]:
            display[column] = display[column].apply(format_money)

        display["EPS ($)"] = display["EPS ($)"].apply(
            lambda value: (
                "N/A"
                if value is None or pd.isna(value)
                else f"${float(value):,.2f}"
            )
        )

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("### Earnings: Estimates vs. Actual")

    if earnings.empty:
        st.info("Earnings estimates or reported EPS are unavailable.")
    else:
        st.dataframe(
            earnings,
            use_container_width=True,
            hide_index=True,
        )

    st.markdown(
        f"[View {symbol} financials on Yahoo Finance]"
        f"(https://finance.yahoo.com/quote/{quote(symbol)}/financials/)"
    )


# =========================================================
# NEWS AND EARNINGS TABS
# =========================================================

st.header("📰 News & Earnings Center")

news_tab, earnings_tab = st.tabs([
    "📰 Stock News",
    "💰 Earnings & Financials",
])

with news_tab:
    show_news(ticker)

with earnings_tab:
    show_earnings(ticker)

# =========================================================
# DISCLAIMER
# =========================================================

st.divider()

st.caption(
    "Educational tool only, not financial advice. BUY/HOLD/SELL signals "
    "are based on simple technical indicators and are not guaranteed "
    "predictions. Yahoo Finance quotes can be delayed or incomplete. "
    "Verify market prices and financial information before making decisions."
)
