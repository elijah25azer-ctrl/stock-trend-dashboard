import html as htmllib
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="Stock Signal Dashboard",
    page_icon="📈",
    layout="wide",
)

# Live stock bar is rendered into this slot
# (the code that fills it is defined further down)
stock_bar_slot = st.container()

st.title("📈 Stock Signal Dashboard")
st.caption(
    "Technical signals | Candlesticks | Watchlist | News | Earnings"
)

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
    "Tip: for a single-day intraday view like a broker chart, use "
    "history 1d with interval 1m or 5m. Yahoo only allows 1m for the "
    "last ~7 days."
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

if custom_tickers.strip():
    for symbol in custom_tickers.upper().replace(" ", "").split(","):
        if symbol and symbol not in watchlist:
            watchlist.append(symbol)

auto_refresh = st.sidebar.toggle(
    "Auto-refresh live data",
    value=True,
)

show_sma = st.sidebar.toggle(
    "Show SMA 20 / 50 lines",
    value=False,
)

if st.sidebar.button("🔄 Refresh all data"):
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

    weekday = now.weekday() < 5
    is_open = weekday and opening <= now < closing

    st.subheader("🕒 US Stock Market Clock")

    c1, c2, c3 = st.columns(3)
    c1.metric("Eastern Time", now.strftime("%I:%M:%S %p"))
    c2.metric("Market Opens", "9:30 AM")
    c3.metric("Market Closes", "4:00 PM")

    if is_open:
        st.success("🟢 REGULAR MARKET OPEN")
        remaining = closing - now
        seconds = max(0, int(remaining.total_seconds()))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        st.write(f"Time until close: {hours}h {minutes}m {seconds}s")
    else:
        st.info("🔴 REGULAR MARKET CLOSED")

        if weekday and now < opening:
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
        "Regular weekday hours only. Exchange holidays and early "
        "closures are not checked."
    )

show_market_clock()
st.divider()

# =========================================================
# STOCK PRICE DATA
# =========================================================

@st.cache_data(ttl=4)
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
            current["Open"], current["High"],
            current["Low"], current["Close"],
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
# NEWS DATA
# =========================================================

@st.cache_data(ttl=900)
def get_stock_news(symbol):
    try:
        items = yf.Ticker(symbol).news
        rows = []

        for item in items or []:
            content = item.get("content", item)

            title = content.get("title", "Untitled news")
            summary = content.get("summary", "")
            publisher = content.get("publisher", "")

            provider = content.get("provider")
            if isinstance(provider, dict):
                publisher = provider.get("displayName", publisher)

            published = (
                content.get("pubDate")
                or content.get("displayTime")
                or content.get("providerPublishTime")
            )

            try:
                if isinstance(published, (int, float)):
                    published = datetime.fromtimestamp(
                        published, tz=ZoneInfo("UTC")
                    ).strftime("%Y-%m-%d %H:%M UTC")
                elif published:
                    published = str(published)
                else:
                    published = "Date unavailable"
            except Exception:
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

            rows.append({
                "Headline": title,
                "Publisher": publisher or "Publisher unavailable",
                "Published": published,
                "Summary": summary or "",
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
        st.info(
            "No news was returned. Try refreshing or check a "
            "financial news website."
        )
        return

    for article in items:
        with st.container(border=True):
            st.markdown(f"**{article['Headline']}**")
            st.caption(
                f"{article['Publisher']} • {article['Published']}"
            )

            if article["Summary"]:
                st.write(article["Summary"])

            link = article["Link"]

            if link and urlparse(link).scheme in ("https", "http"):
                st.markdown(f"[Read full article]({link})")

# =========================================================
# EARNINGS & FINANCIAL RESULTS
# =========================================================

@st.cache_data(ttl=3600)
def get_earnings_data(symbol):
    """Get quarterly financial results and reported EPS history."""
    try:
        stock = yf.Ticker(symbol)

        # Quarterly income statement
        income = stock.quarterly_income_stmt
        financial_rows = []

        if income is not None and not income.empty:
            available_rows = {
                str(index).lower(): index for index in income.index
            }

            def find_row(*names):
                for name in names:
                    key = name.lower()
                    if key in available_rows:
                        return available_rows[key]
                return None

            revenue_row = find_row("Total Revenue", "Operating Revenue")
            income_row = find_row("Net Income", "Net Income Common Stockholders")
            eps_row = find_row("Diluted EPS", "Basic EPS")
            operating_row = find_row("Operating Income")

            for date in income.columns:
                def get_value(row):
                    if row is None:
                        return None
                    value = income.loc[row, date]
                    if pd.isna(value):
                        return None
                    return float(value)

                financial_rows.append({
                    "Quarter End": str(pd.Timestamp(date).date()),
                    "Revenue ($)": get_value(revenue_row),
                    "Net Income ($)": get_value(income_row),
                    "Operating Income ($)": get_value(operating_row),
                    "EPS ($/share)": get_value(eps_row),
                })

        financials = pd.DataFrame(financial_rows)

        # Earnings estimates and reported EPS
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
                            float(estimate)
                            if pd.notna(estimate) else None
                        ),
                        "Reported EPS ($)": (
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


def show_earnings(symbol):
    st.subheader(f"💰 {symbol} — Earnings & Financial Results")

    if st.button("🔄 Refresh earnings", key=f"earnings_{symbol}"):
        get_earnings_data.clear()
        st.rerun()

    financials, earnings = get_earnings_data(symbol)

    # Latest reported financial results
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
            money(latest["Operating Income ($)"])
        )
        c4.metric(
            "Diluted EPS",
            eps_money(latest["EPS ($/share)"])
        )

        st.caption(
            "Revenue is money brought in. Net income is profit after "
            "expenses. Values are reported in US dollars where applicable."
        )

        st.markdown("### Previous Quarterly Results")
        st.dataframe(
            financials,
            use_container_width=True,
            hide_index=True,
        )

    # Earnings estimates compared with actual reported EPS
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

        st.caption(
            "EPS means earnings per share. Surprise percentages are "
            "provided by the data source and may be unavailable."
        )

# =========================================================
# BAR STYLING (used by the live stock bar)
# =========================================================

INDEX_BAR_CSS = """
<style>
.idx-wrap {
    display: flex; gap: 12px; flex-wrap: wrap;
    padding: 14px; margin-bottom: 8px;
    background: #0b0b0b; border: 1px solid #1f6b3a;
    border-radius: 20px;
    box-shadow: 0 0 18px rgba(31, 107, 58, 0.35);
}
.idx-card {
    position: relative; flex: 1 1 180px; min-width: 180px;
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; background: #161616;
    border: 1px solid #2a2a2a; border-radius: 8px;
}
.idx-logo {
    width: 44px; height: 44px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 13px; flex-shrink: 0;
}
.idx-name { color: #9a9a9a; font-size: 12px; }
.idx-price { color: #ffffff; font-size: 17px; font-weight: 700; }
.idx-chg { font-size: 12px; font-weight: 600; margin-left: 4px; }
.idx-up { color: #2ecc71; }
.idx-down { color: #ff6b6b; }
.idx-flat { color: #9a9a9a; }
.idx-badge {
    position: absolute; top: -7px; right: 8px;
    font-size: 11px; font-weight: 700;
    padding: 1px 7px; border-radius: 6px;
}
.idx-badge.idx-up { background: #12361f; color: #2ecc71; }
.idx-badge.idx-down { background: #3a1616; color: #ff6b6b; }
.idx-badge.idx-flat { background: #262626; color: #9a9a9a; }
</style>
"""


# =========================================================
# LIVE STOCK BAR (MSFT, AAPL, NVDA, TSLA, AMZN)
# =========================================================

# (symbol, company, logo background, logo text color)
TOP_STOCKS = [
    ("MSFT", "Microsoft", "#00a4ef", "#ffffff"),
    ("AAPL", "Apple", "#a2aaad", "#111111"),
    ("NVDA", "NVIDIA", "#76b900", "#111111"),
    ("TSLA", "Tesla", "#cc0000", "#ffffff"),
    ("AMZN", "Amazon", "#ff9900", "#111111"),
]

@st.cache_data(ttl=600)
def get_daily_closes(symbol):
    """Recent daily closes, used to find yesterday's close."""
    df = get_stock_data(symbol, "5d", "1d")
    if df.empty:
        return []
    return [(d.date(), float(c)) for d, c in zip(df.index, df["Close"])]

@st.cache_data(ttl=8)
def get_quote(symbol):
    """Latest price (newest 1-minute candle), previous close, candle time."""
    intraday = get_stock_data(symbol, "1d", "1m")
    daily = get_daily_closes(symbol)

    if intraday.empty:
        if len(daily) < 2:
            return None
        return daily[-1][1], daily[-2][1], str(daily[-1][0])

    price = float(intraday["Close"].iloc[-1])
    last_day = intraday.index[-1].date()

    prev = None
    for day, close in reversed(daily):
        if day < last_day:
            prev = close
            break
    if prev is None:
        prev = float(intraday["Open"].iloc[0])

    return price, prev, intraday.index[-1].strftime("%I:%M:%S %p")

@st.fragment(run_every="10s" if auto_refresh else None)
def show_stock_bar():
    cards = []

    for symbol, company, bg, fg in TOP_STOCKS:
        quote = get_quote(symbol)

        if quote is None:
            price_txt, chg_txt, badge_txt, cls = "N/A", "", "–", "idx-flat"
        else:
            price, prev, _ = quote
            change = price - prev
            pct = (price / prev - 1) * 100 if prev else 0
            price_txt = f"${price:,.2f}"
            chg_txt = f"{change:+.2f} ({pct:+.2f}%)"
            cls = "idx-up" if change >= 0 else "idx-down"
            badge_txt = "▲" if change >= 0 else "▼"

        cards.append(
            '<div class="idx-card">'
            f'<div class="idx-logo" style="background:{bg};color:{fg};">'
            f'{htmllib.escape(symbol)}</div>'
            '<div>'
            f'<div class="idx-name">{htmllib.escape(company)}</div>'
            f'<div class="idx-price">{price_txt}</div>'
            f'<div class="idx-chg {cls}" style="margin-left:0;">{chg_txt}</div>'
            '</div>'
            f'<div class="idx-badge {cls}">{badge_txt}</div>'
            '</div>'
        )

    st.markdown(
        INDEX_BAR_CSS + '<div class="idx-wrap">' + "".join(cards) + '</div>',
        unsafe_allow_html=True,
    )

    now_et = datetime.now(ZoneInfo("America/New_York"))
    st.caption(
        f"🟢 Live prices from the newest 1-minute candle | "
        f"Last checked {now_et.strftime('%I:%M:%S %p')} ET | "
        "Updates every 10 seconds. Yahoo data may be delayed."
    )

with stock_bar_slot:
    show_stock_bar()

# =========================================================
# WATCHLIST
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

            current = float(data["Close"].iloc[-1])
            previous = float(data["Close"].iloc[-2])
            change_pct = (
                (current / previous - 1) * 100 if previous else 0
            )
            rsi = data["RSI"].iloc[-1]

            rows.append({
                "Ticker": symbol,
                "Price": f"${current:,.2f}",
                "Daily Change": f"{change_pct:+.2f}%",
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
        "Daily change compares the latest two available daily candles. "
        "Data may be delayed."
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
    price = float(last["Close"])
    previous = float(data["Close"].iloc[-2])
    change_pct = (price / previous - 1) * 100 if previous else 0
    rsi = last["RSI"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Latest Price", f"${price:,.2f}", f"{change_pct:+.2f}%")
    c2.metric("Technical Signal", signal)
    c3.metric("RSI (14)", f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A")
    c4.metric(
        "SMA 20",
        f"${float(last['SMA20']):,.2f}"
        if pd.notna(last["SMA20"]) else "N/A",
    )

    st.caption(
        f"Latest available candle: {data.index[-1]} | "
        "Actual traded prices (not dividend-adjusted)."
    )

    UP_COLOR = "#238a23"    # green candles
    DOWN_COLOR = "#d6404f"  # red candles

    has_volume = "Volume" in data.columns
    fig = make_subplots(
        rows=2 if has_volume else 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.0,
        row_heights=[0.84, 0.16] if has_volume else [1.0],
    )

    fig.add_trace(go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Price",
        increasing=dict(line=dict(color=UP_COLOR, width=1), fillcolor=UP_COLOR),
        decreasing=dict(line=dict(color=DOWN_COLOR, width=1), fillcolor=DOWN_COLOR),
        whiskerwidth=0,
    ), row=1, col=1)

    if show_sma:
        fig.add_trace(go.Scatter(
            x=data.index,
            y=data["SMA20"],
            name="SMA 20",
            line=dict(color="#f5a623", width=1.2),
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=data.index,
            y=data["SMA50"],
            name="SMA 50",
            line=dict(color="#4a90e2", width=1.2),
        ), row=1, col=1)

    if has_volume:
        vol_colors = [
            UP_COLOR if c >= o else DOWN_COLOR
            for o, c in zip(data["Open"], data["Close"])
        ]
        fig.add_trace(go.Bar(
            x=data.index,
            y=data["Volume"],
            name="Volume",
            marker=dict(color=vol_colors, line=dict(width=0)),
            opacity=0.55,
            showlegend=False,
        ), row=2, col=1)
        fig.update_yaxes(visible=False, row=2, col=1)

    # Hide weekends (and overnight for intraday candles) so there are no gaps
    breaks = [dict(bounds=["sat", "mon"])]
    if interval != "1d":
        breaks.append(dict(bounds=[16, 9.5], pattern="hour"))

    fig.update_xaxes(
        rangebreaks=breaks,
        showgrid=False,
        rangeslider_visible=False,
        showline=True,
        linecolor="#dddddd",
    )

    fig.update_yaxes(
        side="right",
        showgrid=True,
        gridcolor="#eeeeee",
        zeroline=False,
        tickformat=",.2f",
        row=1, col=1,
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#333333"),
        height=550,
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis_rangeslider_visible=False,
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
    rsi_fig.add_trace(go.Scatter(
        x=data.index,
        y=data["RSI"],
        name="RSI",
    ))
    rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")
    rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")
    rsi_fig.update_layout(
        template="plotly_white",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#333333"),
        height=260,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis=dict(range=[0, 100], side="right", gridcolor="#eeeeee"),
        xaxis=dict(showgrid=False),
    )

    st.plotly_chart(rsi_fig, use_container_width=True)

show_main_chart()
st.divider()

# =========================================================
# NEWS AND EARNINGS CENTER
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
# FOOTER
# =========================================================

st.divider()
st.caption(
    "Educational tool, not financial advice. Technical signals are not "
    "guaranteed predictions. Yahoo Finance data may be delayed or "
    "incomplete. Verify news, earnings dates, and prices with official "
    "sources before making financial decisions."
)
