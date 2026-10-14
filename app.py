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

DEFAULT_TOP_STOCKS = ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"]

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

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

if not ticker:
    st.warning("Enter a stock ticker.")
    st.stop()

# =========================================================
# DATA CLEANING
# =========================================================
def clean_data(data):
    """Normalize Yahoo Finance data columns."""
    if data is None or data.empty:
        return pd.DataFrame()

    data = data.copy()

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.loc[:, ~data.columns.duplicated()]

    if "Close" in data.columns:
        data = data.dropna(subset=["Close"])

    return data


# =========================================================
# HISTORICAL STOCK DATA
# =========================================================
@st.cache_data(ttl=60, show_spinner=False)
def get_stock_data(symbol, history, candle_interval):
    try:
        data = yf.download(
            symbol,
            period=history,
            interval=candle_interval,
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=False,
            timeout=15,
        )

        return clean_data(data)

    except Exception:
        return pd.DataFrame()


# =========================================================
# LIVE-ISH QUOTE FUNCTION
# =========================================================
@st.cache_data(ttl=10, show_spinner=False)
def get_quote(symbol):
    """
    Return the latest available intraday price and previous close.
    Yahoo Finance may delay data; this is not a guaranteed real-time feed.
    """
    try:
        intraday = yf.download(
            symbol,
            period="1d",
            interval="1m",
            auto_adjust=False,
            prepost=True,
            progress=False,
            threads=False,
            timeout=15,
        )

        intraday = clean_data(intraday)

        daily = yf.download(
            symbol,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False,
            timeout=15,
        )

        daily = clean_data(daily)

        if intraday.empty or "Close" not in intraday.columns:
            if not daily.empty and "Close" in daily.columns:
                last_close = float(daily["Close"].dropna().iloc[-1])
                previous_close = (
                    float(daily["Close"].dropna().iloc[-2])
                    if len(daily["Close"].dropna()) >= 2
                    else last_close
                )
                return last_close, previous_close, "Latest daily close"

            return None, None, "Quote unavailable"

        prices = intraday["Close"].dropna()

        if prices.empty:
            return None, None, "Quote unavailable"

        latest_price = float(prices.iloc[-1])

        if daily.empty or "Close" not in daily.columns:
            previous_close = latest_price
        else:
            daily_closes = daily["Close"].dropna()

            if daily_closes.empty:
                previous_close = latest_price
            else:
                previous_close = float(daily_closes.iloc[-1])

        latest_time = intraday.index[-1]

        return latest_price, previous_close, str(latest_time)

    except Exception:
        return None, None, "Quote unavailable"


# =========================================================
# FORMAT QUOTES
# =========================================================
def format_price(value):
    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"

        return f"${float(value):,.2f}"

    except (ValueError, TypeError):
        return "N/A"


def format_change(price, previous_close):
    if price is None or previous_close is None:
        return "N/A"

    try:
        if previous_close == 0:
            return "N/A"

        change = price - previous_close
        percentage = (change / previous_close) * 100

        return f"{change:+.2f} ({percentage:+.2f}%)"

    except (ValueError, TypeError, ZeroDivisionError):
        return "N/A"


# =========================================================
# TOP STOCK BAR
# =========================================================
st.subheader("📊 Market Watch")

top_columns = st.columns(len(DEFAULT_TOP_STOCKS))

for column, symbol in zip(top_columns, DEFAULT_TOP_STOCKS):
    with column:
        price, previous_close, quote_time = get_quote(symbol)

        st.metric(
            label=symbol,
            value=format_price(price),
            delta=format_change(price, previous_close),
        )

        st.caption(f"Quote time: {quote_time}")


# =========================================================
# MAIN STOCK QUOTE
# =========================================================
st.divider()
st.subheader(f"📈 {ticker} Stock Overview")

price, previous_close, quote_time = get_quote(ticker)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Latest Available Price",
        format_price(price),
        format_change(price, previous_close),
    )

with col2:
    if price is not None and previous_close is not None:
        st.metric(
            "Previous Close",
            format_price(previous_close),
        )
    else:
        st.metric("Previous Close", "N/A")

with col3:
    st.metric("Quote Timestamp", quote_time)


# =========================================================
# HISTORICAL CHART
# =========================================================
st.divider()
st.subheader("🕯️ Candlestick Chart")

with st.spinner(f"Loading chart data for {ticker}..."):
    chart_data = get_stock_data(ticker, period, interval)

if chart_data.empty:
    st.error(
        "Could not load chart data. Check the ticker, "
        "history range, and candle interval."
    )
    st.stop()

required_columns = ["Open", "High", "Low", "Close"]

if not all(column in chart_data.columns for column in required_columns):
    st.error("The returned data does not contain all candlestick columns.")
    st.stop()

# Moving averages
chart_data["SMA20"] = chart_data["Close"].rolling(20).mean()
chart_data["SMA50"] = chart_data["Close"].rolling(50).mean()

show_sma20 = st.checkbox("Show SMA 20", value=True)
show_sma50 = st.checkbox("Show SMA 50", value=True)

fig = go.Figure()

fig.add_trace(
    go.Candlestick(
        x=chart_data.index,
        open=chart_data["Open"],
        high=chart_data["High"],
        low=chart_data["Low"],
        close=chart_data["Close"],
        name=ticker,
    )
)

if show_sma20:
    fig.add_trace(
        go.Scatter(
            x=chart_data.index,
            y=chart_data["SMA20"],
            mode="lines",
            name="SMA 20",
        )
    )

if show_sma50:
    fig.add_trace(
        go.Scatter(
            x=chart_data.index,
            y=chart_data["SMA50"],
            mode="lines",
            name="SMA 50",
        )
    )

fig.update_layout(
    title=f"{ticker} Price Chart",
    xaxis_title="Time",
    yaxis_title="Price ($)",
    xaxis_rangeslider_visible=False,
    height=600,
    template="plotly_dark",
)

st.plotly_chart(fig, use_container_width=True)


# =========================================================
# RSI CALCULATION
# =========================================================
delta = chart_data["Close"].diff()

gain = delta.clip(lower=0)
loss = -delta.clip(upper=0)

average_gain = gain.rolling(14).mean()
average_loss = loss.rolling(14).mean()

relative_strength = average_gain / average_loss.replace(0, float("nan"))

chart_data["RSI"] = 100 - (100 / (1 + relative_strength))
chart_data["RSI"] = chart_data["RSI"].fillna(50)

latest_rsi = float(chart_data["RSI"].iloc[-1])
latest_close = float(chart_data["Close"].iloc[-1])

# =========================================================
# TECHNICAL SIGNALS
# =========================================================
latest_sma20 = chart_data["SMA20"].iloc[-1]
latest_sma50 = chart_data["SMA50"].iloc[-1]

if pd.isna(latest_sma20) or pd.isna(latest_sma50):
    signal = "HOLD / WAIT"
    explanation = "Not enough chart history for both moving averages."
elif latest_close > latest_sma20 and latest_sma20 > latest_sma50 and latest_rsi < 70:
    signal = "BUY WATCH"
    explanation = (
        "The price is above both moving averages and short-term trend "
        "is positive. This is not a guarantee the price will rise."
    )
elif latest_close < latest_sma20 and latest_sma20 < latest_sma50:
    signal = "SELL / EXIT WATCH"
    explanation = (
        "The price is below both moving averages, suggesting a weaker "
        "trend. This does not guarantee the price will fall further."
    )
else:
    signal = "HOLD / WAIT"
    explanation = (
        "The indicators do not show a clear trend under these simple rules."
    )

st.divider()
st.subheader("🧠 Technical Signal")

signal_col, rsi_col = st.columns(2)

with signal_col:
    st.metric("Current Technical Signal", signal)
    st.write(explanation)

with rsi_col:
    st.metric("RSI (14)", f"{latest_rsi:.2f}")

    if latest_rsi >= 70:
        st.warning("RSI is high. Price momentum may be stretched.")
    elif latest_rsi <= 30:
        st.info("RSI is low. Price momentum may be weak.")
    else:
        st.write("RSI is in the middle range.")


# =========================================================
# RSI CHART
# =========================================================
st.subheader("📉 Relative Strength Index")

rsi_fig = go.Figure()

rsi_fig.add_trace(
    go.Scatter(
        x=chart_data.index,
        y=chart_data["RSI"],
        mode="lines",
        name="RSI 14",
    )
)

rsi_fig.add_hline(y=70, line_dash="dash", annotation_text="Overbought 70")
rsi_fig.add_hline(y=30, line_dash="dash", annotation_text="Oversold 30")

rsi_fig.update_layout(
    title=f"{ticker} RSI",
    yaxis_title="RSI",
    yaxis_range=[0, 100],
    height=300,
    template="plotly_dark",
)

st.plotly_chart(rsi_fig, use_container_width=True)


# =========================================================
# WATCHLIST
# =========================================================
st.divider()
st.subheader("⭐ Watchlist")

watchlist = st.multiselect(
    "Choose stocks to watch",
    options=STOCK_OPTIONS,
    default=DEFAULT_TOP_STOCKS,
)

if watchlist:
    rows = []

    progress = st.progress(0)

    for index, symbol in enumerate(watchlist):
        live_price, prior_close, quote_time = get_quote(symbol)

        history_data = get_stock_data(symbol, "3mo", "1d")

        rsi_value = None
        trend = "Unavailable"

        if not history_data.empty and "Close" in history_data.columns:
            closes = history_data["Close"].dropna()

            if len(closes) >= 20:
                change_series = closes.diff()
                gains = change_series.clip(lower=0).rolling(14).mean()
                losses = (-change_series.clip(upper=0)).rolling(14).mean()
                rs = gains / losses.replace(0, float("nan"))
                rsi_series = 100 - (100 / (1 + rs))
                rsi_value = float(rsi_series.iloc[-1])

                sma20 = closes.rolling(20).mean().iloc[-1]
                sma50 = closes.rolling(50).mean().iloc[-1]

                if closes.iloc[-1] > sma20 and sma20 > sma50:
                    trend = "Upward"
                elif closes.iloc[-1] < sma20 and sma20 < sma50:
                    trend = "Downward"
                else:
                    trend = "Mixed"

        if live_price is not None and prior_close not in (None, 0):
            daily_change = (live_price - prior_close) / prior_close * 100
        else:
            daily_change = None

        rows.append(
            {
                "Ticker": symbol,
                "Latest Quote": format_price(live_price),
                "Daily Change (%)": (
                    f"{daily_change:+.2f}%"
                    if daily_change is not None
                    else "N/A"
                ),
                "RSI (14)": (
                    round(rsi_value, 2)
                    if rsi_value is not None and not pd.isna(rsi_value)
                    else "N/A"
                ),
                "Trend": trend,
                "Quote Timestamp": quote_time,
            }
        )

        progress.progress((index + 1) / len(watchlist))

    progress.empty()

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Choose at least one ticker to populate the watchlist.")


# =========================================================
# MARKET CLOCK
# =========================================================
st.divider()
st.subheader("🕒 US Stock Market Clock")

now_ny = datetime.now(ZoneInfo("America/New_York"))

st.write(
    f"**New York time:** {now_ny.strftime('%A, %B %d, %Y — %I:%M:%S %p %Z')}"
)

market_minutes = now_ny.hour * 60 + now_ny.minute
market_open = 9 * 60 + 30
market_close = 16 * 60

if now_ny.weekday() >= 5:
    market_status = "Closed — weekend"
elif market_minutes < market_open:
    market_status = "Closed — before regular hours"
elif market_minutes >= market_close:
    market_status = "Closed — after regular hours"
else:
    market_status = "Regular trading hours"

st.metric("NYSE / Nasdaq Regular Session", market_status)

st.caption(
    "This clock does not check exchange holidays or special early-close days."
)


# =========================================================
# NEWS
# =========================================================
st.divider()
st.subheader("📰 Stock News")

try:
    news_items = yf.Ticker(ticker).news or []

    if news_items:
        for item in news_items[:10]:
            content = item.get("content", item)

            title = content.get("title", "News article")
            summary = content.get("summary", "")
            link = ""

            canonical = content.get("canonicalUrl", {})
            if isinstance(canonical, dict):
                link = canonical.get("url", "")

            if not link:
                link = content.get("link", "")

            st.markdown(f"**{title}**")

            if summary:
                st.write(summary)

            if link:
                st.markdown(f"[Read article]({link})")

            st.divider()
    else:
        st.info("No news articles were returned for this ticker.")

except Exception:
    st.info("News is temporarily unavailable.")


# =========================================================
# EARNINGS / FINANCIAL INFORMATION
# =========================================================
st.divider()
st.subheader("💰 Company Financials")

try:
    company = yf.Ticker(ticker)

    info = company.get_info()

    financial_cols = st.columns(3)

    with financial_cols[0]:
        market_cap = info.get("marketCap")
        st.metric(
            "Market Capitalization",
            (
                f"${market_cap:,.0f}"
                if isinstance(market_cap, (int, float))
                else "N/A"
            ),
        )

    with financial_cols[1]:
        pe_ratio = info.get("trailingPE")
        st.metric(
            "Trailing P/E",
            f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else "N/A",
        )

    with financial_cols[2]:
        dividend_yield = info.get("dividendYield")
        st.metric(
            "Dividend Yield",
            (
                f"{dividend_yield * 100:.2f}%"
                if isinstance(dividend_yield, (int, float))
                else "N/A"
            ),
        )

    st.markdown("**Quarterly Income Statement**")

    quarterly_income = company.quarterly_income_stmt

    if quarterly_income is not None and not quarterly_income.empty:
        st.dataframe(
            quarterly_income,
            use_container_width=True,
        )
    else:
        st.info("Quarterly income statement is unavailable.")

    st.markdown("**Upcoming / Recent Earnings Dates**")

    try:
        earnings_dates = company.get_earnings_dates(limit=8)

        if earnings_dates is not None and not earnings_dates.empty:
            st.dataframe(
                earnings_dates,
                use_container_width=True,
            )
        else:
            st.info("No earnings dates were returned.")
    except Exception:
        st.info("Earnings dates are unavailable for this ticker.")

except Exception:
    st.info("Company financial information is temporarily unavailable.")


# =========================================================
# HELP / RISK REMINDER
# =========================================================
st.divider()

with st.expander("How to read this dashboard"):
    st.markdown("""
    - **Latest quote:** the latest available price returned by Yahoo Finance.
    - **Candlesticks:** each candle represents the selected chart interval.
    - **SMA 20 / SMA 50:** averages of recent closing prices.
    - **RSI:** a momentum indicator between 0 and 100.
    - **BUY WATCH:** a simple technical pattern, not a promise of profit.
    - **HOLD / WAIT:** the selected indicators do not agree on a clear trend.
    - **SELL / EXIT WATCH:** a weak trend under the rules used here, not a guarantee of further losses.
    - **Data timing:** feeds can be delayed, incomplete, or different between providers.
    """)

st.warning(
    "For learning only, not financial advice. These indicators cannot reliably "
    "predict the market. Check current quotes, fees, and order details with your "
    "broker before making financial decisions."
)

st.caption(
    f"Dashboard rendered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
