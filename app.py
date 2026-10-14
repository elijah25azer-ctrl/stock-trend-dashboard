make it all one code with this \
import html as htmllib\
import pandas as pd\
import plotly.graph_objects as go\
from plotly.subplots import make_subplots\
import streamlit as st\
import yfinance as yf\
from datetime import datetime, timedelta\
from zoneinfo import ZoneInfo\
from urllib.parse import urlparse\
\
\# =========================================================\
\# PAGE SETTINGS\
\# =========================================================\
\
st.set_page_config(\
&#x20;   page_title="Stock Signal Dashboard",\
&#x20;   page_icon="📈",\
&#x20;   layout="wide",\
)\
\
stock_bar_slot = st.container()\
\
st.title("📈 Stock Signal Dashboard")\
st.caption(\
&#x20;   "Technical signals | Candlesticks | Watchlist | News | Earnings"\
)\
\
\# =========================================================\
\# STOCK OPTIONS\
\# =========================================================\
\
STOCK_OPTIONS = sorted(set("""\
AAPL MSFT NVDA TSLA AMZN GOOGL GOOG META AMD INTC PLTR NFLX\
AVGO ORCL CRM JPM V MA WMT COST KO PEP DIS UBER SHOP COIN\
HOOD SOFI MSTR SMCI ARM MU QCOM ADBE CSCO IBM TSM LLY NVO\
XOM CVX BA F GM SPY QQQ DIA IWM VOO VTI SCHD JEPI JEPQ\
ASML ANET PANW CRWD NOW SNOW NET DDOG MDB RBLX U RIVN LCID\
NIO XPEV LI BABA BIDU PDD JD SE PYPL XYZ AFRM UPST NU MELI\
AMAT LRCX KLAC MRVL TXN ADI ON NXPI SNPS CDNS INTU ACN\
WDAY TEAM ZM DOCU TWLO PATH IONQ RGTI QUBT ASTS RKLB LUNR\
LMT RTX NOC GD CAT DE CMI HON GE ETN UNH JNJ ABBV MRK PFE\
AMGN GILD REGN ISRG BSX TGT HD LOW MCD SBUX CMG YUM NKE\
LULU TJX ROST CAVA CELH MNST PM MO CL PG EL MDLZ GIS\
BAC WFC C GS MS BLK SCHW CBOE ICE CME AXP DFS BRK-B\
CVNA ABNB BKNG EXPE DASH LYFT UPS FDX DAL UAL AAL LUV\
CCL RCL MAR HLT T FUBO VZ TMUS CMCSA PARA WBD FOXA\
PLD AMT EQIX REAL VICI SPG COP SLB OXY EOG MPC PSX KMI WMB\
RSP IVV SPLG VUG VTV ARKK ARKG XLF XLK XLE XLV XLI XLY\
XLP XLU XLRE SMH SOXX TQQQ SQQQ IBIT FBTC ETHA GLD SLV\
USO UNG TLT HYG LQD\
""".split()))\
\
\# =========================================================\
\# SIDEBAR SETTINGS\
\# =========================================================\
\
st.sidebar.header("Stock Settings")\
\
ticker = st.sidebar.text_input(\
&#x20;   "Main chart ticker",\
&#x20;   value="MSFT",\
).strip().upper()\
\
period = st.sidebar.selectbox(\
&#x20;   "Chart history",\
&#x20;   ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],\
&#x20;   index=4,\
)\
\
interval = st.sidebar.selectbox(\
&#x20;   "Candle interval",\
&#x20;   ["1d", "1h", "30m", "15m", "5m", "1m"],\
&#x20;   index=0,\
)\
\
st.sidebar.caption(\
&#x20;   "Tip: for a single-day intraday view like a broker chart, use "\
&#x20;   "history 1d with interval 1m or 5m. Yahoo only allows 1m for the "\
&#x20;   "last \~7 days."\
)\
\
watchlist = st.sidebar.multiselect(\
&#x20;   "Watchlist",\
&#x20;   options=STOCK_OPTIONS,\
&#x20;   default=["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"],\
)\
\
custom_tickers = st.sidebar.text_input(\
&#x20;   "Add extra tickers",\
&#x20;   placeholder="Example: AMD, PLTR",\
)\
\
if custom_tickers.strip():\
&#x20;   for symbol in custom_tickers.upper().replace(" ", "").split(","):\
&#x20;       if symbol and symbol not in watchlist:\
&#x20;           watchlist.append(symbol)\
\
auto_refresh = st.sidebar.toggle(\
&#x20;   "Auto-refresh live data",\
&#x20;   value=True,\
)\
\
show_sma = st.sidebar.toggle(\
&#x20;   "Show SMA 20 / 50 lines",\
&#x20;   value=False,\
)\
\
if st.sidebar.button("🔄 Refresh all data"):\
&#x20;   st.cache_data.clear()\
&#x20;   st.rerun()\
\
if not ticker:\
&#x20;   st.warning("Enter a stock ticker.")\
&#x20;   st.stop()\
\
\# =========================================================\
\# MARKET CLOCK\
\# =========================================================\
\
@st.fragment(run_every="1s")\
def show_market_clock():\
&#x20;   now = datetime.now(ZoneInfo("America/New_York"))\
\
&#x20;   opening = now\.replace(\
&#x20;       hour=9, minute=30, second=0, microsecond=0\
&#x20;   )\
&#x20;   closing = now\.replace(\
&#x20;       hour=16, minute=0, second=0, microsecond=0\
&#x20;   )\
\
&#x20;   weekday = now\.weekday() < 5\
&#x20;   is_open = weekday and opening <= now < closing\
\
&#x20;   st.subheader("🕒 US Stock Market Clock")\
\
&#x20;   c1, c2, c3 = st.columns(3)\
&#x20;   c1.metric("Eastern Time", now\.strftime("%I:%M:%S %p"))\
&#x20;   c2.metric("Market Opens", "9:30 AM")\
&#x20;   c3.metric("Market Closes", "4:00 PM")\
\
&#x20;   if is_open:\
&#x20;       st.success("🟢 REGULAR MARKET OPEN")\
&#x20;       remaining = closing - now\
&#x20;       seconds = max(0, int(remaining.total_seconds()))\
&#x20;       hours, remainder = divmod(seconds, 3600)\
&#x20;       minutes, seconds = divmod(remainder, 60)\
&#x20;       st.write(f"Time until close: {hours}h {minutes}m {seconds}s")\
&#x20;   else:\
&#x20;       st.info("🔴 REGULAR MARKET CLOSED")\
\
&#x20;       if weekday and now < opening:\
&#x20;           next_open = now\
&#x20;       else:\
&#x20;           next_open = now + timedelta(days=1)\
\
&#x20;       while next_open.weekday() >= 5:\
&#x20;           next_open += timedelta(days=1)\
\
&#x20;       st.write(\
&#x20;           f"Next weekday opening: {next_open.strftime('%A, %B %d')} "\
&#x20;           "at 9:30 AM ET."\
&#x20;       )\
\
&#x20;   st.caption(\
&#x20;       "Regular weekday hours only. Exchange holidays and early "\
&#x20;       "closures are not checked."\
&#x20;   )\
\
show_market_clock()\
st.divider()\
\
\# =========================================================\
\# STOCK PRICE DATA\
\# =========================================================\
\
@st.cache_data(ttl=4)\
def get_stock_data(symbol, history, candle_interval):\
&#x20;   try:\
&#x20;       df = yf.download(\
&#x20;           symbol,\
&#x20;           period=history,\
&#x20;           interval=candle_interval,\
&#x20;           auto_adjust=False,\
&#x20;           progress=False,\
&#x20;           threads=False,\
&#x20;       )\
\
&#x20;       if df is None or df.empty:\
&#x20;           return pd.DataFrame()\
\
&#x20;       if isinstance(df.columns, pd.MultiIndex):\
&#x20;           df.columns = df.columns.get_level_values(0)\
\
&#x20;       df = df.loc[:, \~df.columns.duplicated()].copy()\
\
&#x20;       required = ["Open", "High", "Low", "Close"]\
&#x20;       if not all(col in df.columns for col in required):\
&#x20;           return pd.DataFrame()\
\
&#x20;       for col in required:\
&#x20;           df[col] = pd.to_numeric(df[col], errors="coerce")\
\
&#x20;       return df.dropna(subset=required).copy()\
\
&#x20;   except Exception:\
&#x20;       return pd.DataFrame()\
\
\# =========================================================\
\# TECHNICAL INDICATORS\
\# =========================================================\
\
def add_indicators(df):\
&#x20;   df = df.copy()\
&#x20;   close = df["Close"].astype(float)\
\
&#x20;   df["SMA20"] = close.rolling(20).mean()\
&#x20;   df["SMA50"] = close.rolling(50).mean()\
\
&#x20;   change = close.diff()\
&#x20;   gains = change.clip(lower=0)\
&#x20;   losses = -change.clip(upper=0)\
\
&#x20;   avg_gain = gains.ewm(\
&#x20;       alpha=1 / 14,\
&#x20;       min_periods=14,\
&#x20;       adjust=False,\
&#x20;   ).mean()\
\
&#x20;   avg_loss = losses.ewm(\
&#x20;       alpha=1 / 14,\
&#x20;       min_periods=14,\
&#x20;       adjust=False,\
&#x20;   ).mean()\
\
&#x20;   rs = avg_gain / avg_loss.replace(0, float("nan"))\
&#x20;   df["RSI"] = 100 - (100 / (1 + rs))\
\
&#x20;   df.loc[(avg_loss == 0) & (avg_gain > 0), "RSI"] = 100\
&#x20;   df.loc[(avg_gain == 0) & (avg_loss > 0), "RSI"] = 0\
&#x20;   df.loc[(avg_gain == 0) & (avg_loss == 0), "RSI"] = 50\
\
&#x20;   return df\
\
\# =========================================================\
\# BUY / HOLD / SELL SIGNAL\
\# =========================================================\
\
def calculate_signal(df):\
&#x20;   if len(df) < 2:\
&#x20;       return "INSUFFICIENT DATA", 0, 0, ["Not enough candles."]\
\
&#x20;   last = df.iloc[-1]\
&#x20;   price = float(last["Close"])\
&#x20;   sma20 = last["SMA20"]\
&#x20;   sma50 = last["SMA50"]\
&#x20;   rsi = last["RSI"]\
\
&#x20;   score = 0\
&#x20;   checks = 0\
&#x20;   reasons = []\
\
&#x20;   if pd.notna(sma20):\
&#x20;       checks += 1\
&#x20;       if price > float(sma20):\
&#x20;           score += 1\
&#x20;           reasons.append("Price is above SMA20 (bullish).")\
&#x20;       elif price < float(sma20):\
&#x20;           score -= 1\
&#x20;           reasons.append("Price is below SMA20 (bearish).")\
&#x20;       else:\
&#x20;           reasons.append("Price equals SMA20.")\
&#x20;   else:\
&#x20;       reasons.append("SMA20 needs more candles.")\
\
&#x20;   if pd.notna(sma20) and pd.notna(sma50):\
&#x20;       checks += 1\
&#x20;       if float(sma20) > float(sma50):\
&#x20;           score += 1\
&#x20;           reasons.append("SMA20 is above SMA50 (bullish).")\
&#x20;       elif float(sma20) < float(sma50):\
&#x20;           score -= 1\
&#x20;           reasons.append("SMA20 is below SMA50 (bearish).")\
&#x20;       else:\
&#x20;           reasons.append("Moving averages are equal.")\
&#x20;   else:\
&#x20;       reasons.append("Moving averages need more data.")\
\
&#x20;   if pd.notna(rsi):\
&#x20;       checks += 1\
&#x20;       rsi = float(rsi)\
\
&#x20;       if rsi < 30:\
&#x20;           score += 1\
&#x20;           reasons.append(f"RSI {rsi:.1f}: commonly considered oversold.")\
&#x20;       elif rsi > 70:\
&#x20;           score -= 1\
&#x20;           reasons.append(f"RSI {rsi:.1f}: commonly considered overbought.")\
&#x20;       else:\
&#x20;           reasons.append(f"RSI is {rsi:.1f}, within 30–70.")\
&#x20;   else:\
&#x20;       reasons.append("RSI needs more candles.")\
\
&#x20;   if checks < 2:\
&#x20;       signal = "INSUFFICIENT DATA"\
&#x20;   elif score >= 2:\
&#x20;       signal = "BUY"\
&#x20;   elif score <= -2:\
&#x20;       signal = "SELL"\
&#x20;   else:\
&#x20;       signal = "HOLD"\
\
&#x20;   return signal, score, checks, reasons\
\
\# =========================================================\
\# CANDLESTICK PATTERNS\
\# =========================================================\
\
def detect_patterns(df):\
&#x20;   if len(df) < 2:\
&#x20;       return ["Not enough candles."]\
\
&#x20;   current = df.iloc[-1]\
&#x20;   previous = df.iloc[-2]\
\
&#x20;   o, h, low, c = map(\
&#x20;       float,\
&#x20;       [\
&#x20;           current["Open"], current["High"],\
&#x20;           current["Low"], current["Close"],\
&#x20;       ],\
&#x20;   )\
\
&#x20;   po = float(previous["Open"])\
&#x20;   pc = float(previous["Close"])\
\
&#x20;   body = abs(c - o)\
&#x20;   previous_body = abs(pc - po)\
&#x20;   candle_range = max(h - low, 1e-9)\
\
&#x20;   upper_wick = h - max(o, c)\
&#x20;   lower_wick = min(o, c) - low\
\
&#x20;   patterns = []\
\
&#x20;   if (\
&#x20;       pc < po and c > o and o <= pc and c >= po\
&#x20;       and body >= previous_body\
&#x20;   ):\
&#x20;       patterns.append("Possible bullish engulfing.")\
\
&#x20;   if (\
&#x20;       pc > po and c < o and o >= pc and c <= po\
&#x20;       and body >= previous_body\
&#x20;   ):\
&#x20;       patterns.append("Possible bearish engulfing.")\
\
&#x20;   if (\
&#x20;       lower_wick >= 2 \* max(body, 1e-9)\
&#x20;       and upper_wick <= max(body \* 0.6, candle_range \* 0.08)\
&#x20;       and body / candle_range <= 0.4\
&#x20;   ):\
&#x20;       patterns.append("Hammer-like candle.")\
\
&#x20;   if (\
&#x20;       upper_wick >= 2 \* max(body, 1e-9)\
&#x20;       and lower_wick <= max(body \* 0.6, candle_range \* 0.08)\
&#x20;       and body / candle_range <= 0.4\
&#x20;   ):\
&#x20;       patterns.append("Shooting-star-like candle.")\
\
&#x20;   return patterns or ["No selected pattern detected."]\
\
\# =========================================================\
\# NEWS DATA\
\# =========================================================\
\
@st.cache_data(ttl=900)\
def get_stock_news(symbol):\
&#x20;   try:\
&#x20;       items = yf.Ticker(symbol).news\
&#x20;       rows = []\
\
&#x20;       for item in items or []:\
&#x20;           content = item.get("content", item)\
\
&#x20;           title = content.get("title", "Untitled news")\
&#x20;           summary = content.get("summary", "")\
&#x20;           publisher = content.get("publisher", "")\
\
&#x20;           provider = content.get("provider")\
&#x20;           if isinstance(provider, dict):\
&#x20;               publisher = provider.get("displayName", publisher)\
\
&#x20;           published = (\
&#x20;               content.get("pubDate")\
&#x20;               or content.get("displayTime")\
&#x20;               or content.get("providerPublishTime")\
&#x20;           )\
\
&#x20;           try:\
&#x20;               if isinstance(published, (int, float)):\
&#x20;                   published = datetime.fromtimestamp(\
&#x20;                       published, tz=ZoneInfo("UTC")\
&#x20;                   ).strftime("%Y-%m-%d %H:%M UTC")\
&#x20;               elif published:\
&#x20;                   published = str(published)\
&#x20;               else:\
&#x20;                   published = "Date unavailable"\
&#x20;           except Exception:\
&#x20;               published = "Date unavailable"\
\
&#x20;           link = content.get("link", "")\
\
&#x20;           if not link:\
&#x20;               canonical = content.get("canonicalUrl", {})\
&#x20;               if isinstance(canonical, dict):\
&#x20;                   link = canonical.get("url", "")\
\
&#x20;           if not link:\
&#x20;               click_url = content.get("clickThroughUrl", {})\
&#x20;               if isinstance(click_url, dict):\
&#x20;                   link = click_url.get("url", "")\
\
&#x20;           rows.append({\
&#x20;               "Headline": title,\
&#x20;               "Publisher": publisher or "Publisher unavailable",\
&#x20;               "Published": published,\
&#x20;               "Summary": summary or "",\
&#x20;               "Link": link or "",\
&#x20;           })\
\
&#x20;       return rows\
\
&#x20;   except Exception:\
&#x20;       return []\
\
def show_news(symbol):\
&#x20;   st.subheader(f"📰 Latest News — {symbol}")\
\
&#x20;   if st.button("🔄 Refresh news", key=f"news\_{symbol}"):\
&#x20;       get_stock_news.clear()\
&#x20;       st.rerun()\
\
&#x20;   items = get_stock_news(symbol)\
\
&#x20;   if not items:\
&#x20;       st.info(\
&#x20;           "No news was returned. Try refreshing or check a "\
&#x20;           "financial news website."\
&#x20;       )\
&#x20;       return\
\
&#x20;   for article in items:\
&#x20;       with st.container(border=True):\
&#x20;           st.markdown(f"\*\*{article['Headline']}\*\*")\
&#x20;           st.caption(\
&#x20;               f"{article['Publisher']} • {article['Published']}"\
&#x20;           )\
\
&#x20;           if article["Summary"]:\
&#x20;               st.write(article["Summary"])\
\
&#x20;           link = article["Link"]\
\
&#x20;           if link and urlparse(link).scheme in ("https", "http"):\
&#x20;               st.markdown(f"[Read full article]\({link})")\
\
\# =========================================================\
\# EARNINGS & FINANCIAL RESULTS\
\# =========================================================\
\
@st.cache_data(ttl=3600)\
def get_earnings_data(symbol):\
&#x20;   """Get quarterly financial results and reported EPS history."""\
&#x20;   try:\
&#x20;       stock = yf.Ticker(symbol)\
&#x20;       income = stock.quarterly_income_stmt\
&#x20;       financial_rows = []\
\
&#x20;       if income is not None and not income.empty:\
&#x20;           available_rows = {\
&#x20;               str(index).lower(): index for index in income.index\
&#x20;           }\
\
&#x20;           def find_row(\*names):\
&#x20;               for name in names:\
&#x20;                   key = name.lower()\
&#x20;                   if key in available_rows:\
&#x20;                       return available_rows[key]\
&#x20;               return None\
\
&#x20;           revenue_row = find_row("Total Revenue", "Operating Revenue")\
&#x20;           income_row = find_row(\
&#x20;               "Net Income", "Net Income Common Stockholders"\
&#x20;           )\
&#x20;           eps_row = find_row("Diluted EPS", "Basic EPS")\
&#x20;           operating_row = find_row("Operating Income")\
\
&#x20;           for date in income.columns:\
&#x20;               def get_value(row):\
&#x20;                   if row is None:\
&#x20;                       return None\
&#x20;                   value = income.loc[row, date]\
&#x20;                   if pd.isna(value):\
&#x20;                       return None\
&#x20;                   return float(value)\
\
&#x20;               financial_rows.append({\
&#x20;                   "Quarter End": str(pd.Timestamp(date).date()),\
&#x20;                   "Revenue ($)": get_value(revenue_row),\
&#x20;                   "Net Income ($)": get_value(income_row),\
&#x20;                   "Operating Income ($)": get_value(operating_row),\
&#x20;                   "EPS ($/share)": get_value(eps_row),\
&#x20;               })\
\
&#x20;       financials = pd.DataFrame(financial_rows)\
&#x20;       earnings_rows = []\
\
&#x20;       try:\
&#x20;           earnings = stock.get_earnings_dates(limit=12)\
\
&#x20;           if earnings is not None and not earnings.empty:\
&#x20;               for date, row in earnings.iterrows():\
&#x20;                   estimate = row\.get("EPS Estimate")\
&#x20;                   actual = row\.get("Reported EPS")\
&#x20;                   surprise = row\.get("Surprise(%)")\
\
&#x20;                   earnings_rows.append({\
&#x20;                       "Earnings Date": str(date),\
&#x20;                       "EPS Estimate ($)": (\
&#x20;                           float(estimate)\
&#x20;                           if pd.notna(estimate) else None\
&#x20;                       ),\
&#x20;                       "Reported EPS ($)": (\
&#x20;                           float(actual)\
&#x20;                           if pd.notna(actual) else None\
&#x20;                       ),\
&#x20;                       "Surprise (%)": (\
&#x20;                           float(surprise)\
&#x20;                           if pd.notna(surprise) else None\
&#x20;                       ),\
&#x20;                   })\
&#x20;       except Exception:\
&#x20;           pass\
\
&#x20;       return financials, pd.DataFrame(earnings_rows)\
\
&#x20;   except Exception:\
&#x20;       return pd.DataFrame(), pd.DataFrame()\
\
\
def show_earnings(symbol):\
&#x20;   st.subheader(f"💰 {symbol} — Earnings & Financial Results")\
\
&#x20;   if st.button("🔄 Refresh earnings", key=f"earnings\_{symbol}"):\
&#x20;       get_earnings_data.clear()\
&#x20;       st.rerun()\
\
&#x20;   financials, earnings = get_earnings_data(symbol)\
\
&#x20;   st.markdown("### Latest Quarterly Financial Results")\
\
&#x20;   if financials.empty:\
&#x20;       st.info(\
&#x20;           "Quarterly financial statements aren't available "\
&#x20;           "for this ticker right now."\
&#x20;       )\
&#x20;   else:\
&#x20;       latest = financials.iloc[0]\
\
&#x20;       def money(value):\
&#x20;           if value is None or pd.isna(value):\
&#x20;               return "N/A"\
&#x20;           return f"${value:,.0f}"\
\
&#x20;       def eps_money(value):\
&#x20;           if value is None or pd.isna(value):\
&#x20;               return "N/A"\
&#x20;           return f"${value:,.2f}"\
\
&#x20;       st.caption(f"Quarter ending: {latest['Quarter End']}")\
\
&#x20;       c1, c2 = st.columns(2)\
&#x20;       c1.metric("Revenue", money(latest["Revenue ($)"]))\
&#x20;       c2.metric("Net Income", money(latest["Net Income ($)"]))\
\
&#x20;       c3, c4 = st.columns(2)\
&#x20;       c3.metric(\
&#x20;           "Operating Income",\
&#x20;           money(latest["Operating Income ($)"])\
&#x20;       )\
&#x20;       c4.metric(\
&#x20;           "Diluted EPS",\
&#x20;           eps_money(latest["EPS ($/share)"])\
&#x20;       )\
\
&#x20;       st.caption(\
&#x20;           "Revenue is money brought in. Net income is profit after "\
&#x20;           "expenses. Values are reported in US dollars where applicable."\
&#x20;       )\
\
&#x20;       st.markdown("### Previous Quarterly Results")\
&#x20;       st.dataframe(\
&#x20;           financials,\
&#x20;           use_container_width=True,\
&#x20;           hide_index=True,\
&#x20;       )\
\
&#x20;   st.markdown("### 📊 Earnings: Estimate vs. Actual")\
\
&#x20;   if earnings.empty:\
&#x20;       st.info(\
&#x20;           "EPS estimates and reported earnings history aren't "\
&#x20;           "available right now."\
&#x20;       )\
&#x20;   else:\
&#x20;       st.dataframe(\
&#x20;           earnings,\
&#x20;           use_container_width=True,\
&#x20;           hide_index=True,\
&#x20;       )\
\
&#x20;       st.caption(\
&#x20;           "EPS means earnings per share. Surprise percentages are "\
&#x20;           "provided by the data source and may be unavailable."\
&#x20;       )\
\
\# =========================================================\
\# FIXED STOCK BAR STYLING — APPLIES TO EVERY TICKER\
\# =========================================================\
\
INDEX_BAR_CSS = """\
\<style>\
.idx-wrap {\
&#x20;   width: 100%;\
&#x20;   min-width: 0;\
&#x20;   box-sizing: border-box;\
&#x20;   display: block;\
&#x20;   padding: 0;\
&#x20;   margin: 0 0 6px 0;\
&#x20;   background: transparent;\
&#x20;   border: none;\
&#x20;   border-radius: 0;\
&#x20;   box-shadow: none;\
}\
.idx-card {\
&#x20;   position: relative;\
&#x20;   width: 100%;\
&#x20;   min-width: 0;\
&#x20;   min-height: 76px;\
&#x20;   box-sizing: border-box;\
&#x20;   display: flex;\
&#x20;   align-items: center;\
&#x20;   gap: 9px;\
&#x20;   padding: 10px;\
&#x20;   background: #161616;\
&#x20;   border: 1px solid #303030;\
&#x20;   border-radius: 10px;\
&#x20;   overflow: hidden;\
}\
.idx-logo {\
&#x20;   width: 40px;\
&#x20;   height: 40px;\
&#x20;   min-width: 40px;\
&#x20;   border-radius: 7px;\
&#x20;   display: flex;\
&#x20;   align-items: center;\
&#x20;   justify-content: center;\
&#x20;   font-weight: 800;\
&#x20;   font-size: 11px;\
&#x20;   flex-shrink: 0;\
}\
.idx-card > div:nth-child(2) {\
&#x20;   min-width: 0;\
&#x20;   flex: 1 1 auto;\
&#x20;   overflow: hidden;\
}\
.idx-name {\
&#x20;   color: #a7a7a7;\
&#x20;   font-size: 11px;\
&#x20;   line-height: 1.25;\
&#x20;   overflow: hidden;\
&#x20;   text-overflow: ellipsis;\
&#x20;   white-space: nowrap;\
}\
.idx-price {\
&#x20;   color: #ffffff;\
&#x20;   font-size: 15px;\
&#x20;   line-height: 1.35;\
&#x20;   font-weight: 700;\
&#x20;   white-space: nowrap;\
}\
.idx-chg {\
&#x20;   font-size: 10px;\
&#x20;   line-height: 1.3;\
&#x20;   font-weight: 600;\
&#x20;   overflow-wrap: anywhere;\
}\
.idx-up { color: #2ecc71; }\
.idx-down { color: #ff6b6b; }\
.idx-flat { color: #9a9a9a; }\
.idx-badge {\
&#x20;   position: absolute;\
&#x20;   top: 5px;\
&#x20;   right: 6px;\
&#x20;   font-size: 9px;\
&#x20;   line-height: 1;\
&#x20;   font-weight: 700;\
&#x20;   padding: 4px 5px;\
&#x20;   border-radius: 5px;\
}\
.idx-badge.idx-up { background: #12361f; color: #2ecc71; }\
.idx-badge.idx-down { background: #3a1616; color: #ff6b6b; }\
.idx-badge.idx-flat { background: #262626; color: #9a9a9a; }\
@media (max-width: 900px) {\
&#x20;   .idx-card { padding: 8px; gap: 7px; }\
&#x20;   .idx-logo {\
&#x20;       width: 34px;\
&#x20;       height: 34px;\
&#x20;       min-width: 34px;\
&#x20;       font-size: 10px;\
&#x20;   }\
&#x20;   .idx-price { font-size: 13px; }\
&#x20;   .idx-chg { font-size: 9px; }\
}\
\</style>\
"""\
\
\# =========================================================\
\# LIVE STOCK BAR\
\# =========================================================\
\
DEFAULT_TOP_STOCKS = ["MSFT", "AAPL", "NVDA", "TSLA", "AMZN"]\
\
KNOWN_NAMES = {\
&#x20;   "MSFT": "Microsoft",\
&#x20;   "AAPL": "Apple",\
&#x20;   "NVDA": "NVIDIA",\
&#x20;   "TSLA": "Tesla",\
&#x20;   "AMZN": "Amazon",\
}\
\
KNOWN_STYLES = {\
&#x20;   "MSFT": ("#00a4ef", "#ffffff"),\
&#x20;   "AAPL": ("#a2aaad", "#111111"),\
&#x20;   "NVDA": ("#76b900", "#111111"),\
&#x20;   "TSLA": ("#cc0000", "#ffffff"),\
&#x20;   "AMZN": ("#ff9900", "#111111"),\
}\
\
\
def parse_stock_list(text):\
&#x20;   out = []\
&#x20;   for item in (text or "").upper().replace(" ", "").split(","):\
&#x20;       if item and item not in out:\
&#x20;           out.append(item)\
&#x20;   return out[:5]\
\
\
if "top_stocks" not in st.session_state:\
&#x20;   saved = parse_stock_list(st.query_params.get("stocks", ""))\
&#x20;   if saved:\
&#x20;       filler = [d for d in DEFAULT_TOP_STOCKS if d not in saved]\
&#x20;       st.session_state["top_stocks"] = (saved + filler)[:5]\
&#x20;   else:\
&#x20;       st.session_state["top_stocks"] = list(DEFAULT_TOP_STOCKS)\
\
\
@st.cache_data(ttl=86400)\
def get_company_name(symbol):\
&#x20;   if symbol in KNOWN_NAMES:\
&#x20;       return KNOWN_NAMES[symbol]\
&#x20;   try:\
&#x20;       info = yf.Ticker(symbol).info\
&#x20;       return info.get("shortName") or info.get("longName") or symbol\
&#x20;   except Exception:\
&#x20;       return symbol\
\
\
def logo_colors(symbol):\
&#x20;   if symbol in KNOWN_STYLES:\
&#x20;       return KNOWN_STYLES[symbol]\
&#x20;   hue = (sum(ord(ch) for ch in symbol) \* 37) % 360\
&#x20;   return f"hsl({hue},65%,45%)", "#ffffff"\
\
\
@st.cache_data(ttl=600)\
def get_daily_closes(symbol):\
&#x20;   df = get_stock_data(symbol, "5d", "1d")\
&#x20;   if df.empty:\
&#x20;       return []\
&#x20;   return [\
&#x20;       (d.date(), float(c))\
&#x20;       for d, c in zip(df.index, df["Close"])\
&#x20;   ]\
\
\
@st.cache_data(ttl=8)\
def get_quote(symbol):\
&#x20;   intraday = get_stock_data(symbol, "1d", "1m")\
&#x20;   daily = get_daily_closes(symbol)\
\
&#x20;   if intraday.empty:\
&#x20;       if len(daily) < 2:\
&#x20;           return None\
&#x20;       return daily[-1][1], daily[-2][1], str(daily[-1][0])\
\
&#x20;   price = float(intraday["Close"].iloc[-1])\
&#x20;   last_day = intraday.index[-1].date()\
\
&#x20;   prev = None\
&#x20;   for day, close in reversed(daily):\
&#x20;       if day < last_day:\
&#x20;           prev = close\
&#x20;           break\
\
&#x20;   if prev is None:\
&#x20;       prev = float(intraday["Open"].iloc[0])\
\
&#x20;   return price, prev, intraday.index[-1].strftime("%I:%M:%S %p")\
\
\
@st.fragment(run_every="10s" if auto_refresh else None)\
def show_stock_bar():\
&#x20;   symbols = st.session_state["top_stocks"]\
&#x20;   cols = st.columns(len(symbols))\
\
&#x20;   for col, symbol in zip(cols, symbols):\
&#x20;       quote = get_quote(symbol)\
&#x20;       bg, fg = logo_colors(symbol)\
&#x20;       company = get_company_name(symbol)[:20]\
\
&#x20;       if quote is None:\
&#x20;           price_txt = "N/A"\
&#x20;           chg_txt = ""\
&#x20;           badge_txt = "–"\
&#x20;           cls = "idx-flat"\
&#x20;       else:\
&#x20;           price, prev, \_ = quote\
&#x20;           change = price - prev\
&#x20;           pct = (price / prev - 1) \* 100 if prev else 0\
&#x20;           price_txt = f"${price:,.2f}"\
&#x20;           chg_txt = f"{change:+.2f} ({pct:+.2f}%)"\
&#x20;           cls = "idx-up" if change >= 0 else "idx-down"\
&#x20;           badge_txt = "▲" if change >= 0 else "▼"\
\
&#x20;       card = (\
&#x20;           '\<div class="idx-wrap">'\
&#x20;           '\<div class="idx-card">'\
&#x20;           f'\<div class="idx-logo" style="background:{bg};color:{fg};">'\
&#x20;           f'{htmllib.escape(symbol[:5])}\</div>'\
&#x20;           '\<div>'\
&#x20;           f'\<div class="idx-name">{htmllib.escape(company)}\</div>'\
&#x20;           f'\<div class="idx-price">{price_txt}\</div>'\
&#x20;           f'\<div class="idx-chg {cls}">{chg_txt}\</div>'\
&#x20;           '\</div>'\
&#x20;           f'\<div class="idx-badge {cls}">{badge_txt}\</div>'\
&#x20;           '\</div>'\
&#x20;           '\</div>'\
&#x20;       )\
\
&#x20;       with col:\
&#x20;           st.markdown(\
&#x20;               INDEX_BAR_CSS + card,\
&#x20;               unsafe_allow_html=True,\
&#x20;           )\
\
\
@st.fragment(run_every="10s" if auto_refresh else None)\
def show_bar_status():\
&#x20;   now_et = datetime.now(ZoneInfo("America/New_York"))\
&#x20;   st.caption(\
&#x20;       f"Yahoo quote from newest available 1-minute candle | "\
&#x20;       f"Last checked {now_et.strftime('%I:%M:%S %p')} ET | "\
&#x20;       "Updates every 10 seconds. Yahoo data may be delayed."\
&#x20;   )\
\
\
with stock_bar_slot:\
&#x20;   show_stock_bar()\
\
&#x20;   current_stocks = st.session_state["top_stocks"]\
&#x20;   edit_cols = st.columns(len(current_stocks))\
\
&#x20;   for i, (col, current) in enumerate(zip(edit_cols, current_stocks)):\
&#x20;       with col:\
&#x20;           with st.popover(\
&#x20;               f"✏️ Change {current}",\
&#x20;               use_container_width=True,\
&#x20;           ):\
&#x20;               new_symbol = st.text_input(\
&#x20;                   "New ticker",\
&#x20;                   key=f"new_ticker\_{i}\_{current}",\
&#x20;                   placeholder="Example: AMD",\
&#x20;               )\
\
&#x20;               if st.button("Apply", key=f"apply_ticker\_{i}\_{current}"):\
&#x20;                   sym = new_symbol.strip().upper()\
\
&#x20;                   if not sym:\
&#x20;                       st.warning("Type a ticker first.")\
&#x20;                   elif sym in current_stocks:\
&#x20;                       st.warning(f"{sym} is already in the bar.")\
&#x20;                   elif get_quote(sym) is None:\
&#x20;                       st.error(\
&#x20;                           f"No data found for {sym}. Check the ticker."\
&#x20;                       )\
&#x20;                   else:\
&#x20;                       st.session_state["top_stocks"][i] = sym\
&#x20;                       st.query_params["stocks"] = ",".join(\
&#x20;                           st.session_state["top_stocks"]\
&#x20;                       )\
&#x20;                       st.rerun()\
\
&#x20;   show_bar_status()\
\
\# =========================================================\
\# WATCHLIST\
\# =========================================================\
\
@st.fragment(run_every="60s" if auto_refresh else None)\
def show_watchlist():\
&#x20;   st.subheader("⭐ Watchlist")\
\
&#x20;   if not watchlist:\
&#x20;       st.info("Select stocks in the sidebar.")\
&#x20;       return\
\
&#x20;   rows = []\
&#x20;   progress = st.progress(0)\
&#x20;   status = st.empty()\
\
&#x20;   for i, symbol in enumerate(watchlist):\
&#x20;       status.caption(f"Loading {symbol} ({i + 1}/{len(watchlist)})")\
&#x20;       df = get_stock_data(symbol, "3mo", "1d")\
\
&#x20;       if df.empty or len(df) < 2:\
&#x20;           rows.append({\
&#x20;               "Ticker": symbol,\
&#x20;               "Price": "Unavailable",\
&#x20;               "Daily Change": "N/A",\
&#x20;               "RSI": "N/A",\
&#x20;               "Signal": "NO DATA",\
&#x20;           })\
&#x20;       else:\
&#x20;           data = add_indicators(df)\
&#x20;           signal, \_, \_, \_ = calculate_signal(data)\
\
&#x20;           current = float(data["Close"].iloc[-1])\
&#x20;           previous = float(data["Close"].iloc[-2])\
&#x20;           change_pct = (\
&#x20;               (current / previous - 1) \* 100 if previous else 0\
&#x20;           )\
&#x20;           rsi = data["RSI"].iloc[-1]\
\
&#x20;           rows.append({\
&#x20;               "Ticker": symbol,\
&#x20;               "Price": f"${current:,.2f}",\
&#x20;               "Daily Change": f"{change_pct:+.2f}%",\
&#x20;               "RSI": f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",\
&#x20;               "Signal": signal,\
&#x20;           })\
\
&#x20;       progress.progress((i + 1) / len(watchlist))\
\
&#x20;   progress.empty()\
&#x20;   status.empty()\
\
&#x20;   st.dataframe(\
&#x20;       pd.DataFrame(rows),\
&#x20;       use_container_width=True,\
&#x20;       hide_index=True,\
&#x20;   )\
\
&#x20;   st.caption(\
&#x20;       "Daily change compares the latest two available daily candles. "\
&#x20;       "Data may be delayed."\
&#x20;   )\
\
\
show_watchlist()\
st.divider()\
\
\# =========================================================\
\# MAIN CHART\
\# =========================================================\
\
@st.fragment(run_every="15s" if auto_refresh else None)\
def show_main_chart():\
&#x20;   st.subheader(f"📊 Main Stock: {ticker}")\
\
&#x20;   raw = get_stock_data(ticker, period, interval)\
\
&#x20;   if raw\.empty or len(raw) < 2:\
&#x20;       st.error(\
&#x20;           "No usable data found. Check the ticker, connection, "\
&#x20;           "or selected candle interval."\
&#x20;       )\
&#x20;       return\
\
&#x20;   data = add_indicators(raw)\
&#x20;   signal, score, checks, reasons = calculate_signal(data)\
&#x20;   patterns = detect_patterns(data)\
\
&#x20;   last = data.iloc[-1]\
&#x20;   rsi = last["RSI"]\
\
&#x20;   quote = get_quote(ticker)\
\
&#x20;   if quote is not None:\
&#x20;       price, previous_close, quote_time = quote\
&#x20;       change_pct = (\
&#x20;           (price / previous_close - 1) \* 100\
&#x20;           if previous_close else 0\
&#x20;       )\
&#x20;       price_label = "Latest Quote"\
&#x20;       price_caption = (\
&#x20;           f"Quote from the newest available 1-minute candle: "\
&#x20;           f"{quote_time}. The candlestick chart below uses your "\
&#x20;           "selected candle interval; its last candle close can "\
&#x20;           "differ from this quote."\
&#x20;       )\
&#x20;   else:\
&#x20;       price = float(last["Close"])\
&#x20;       previous = float(data["Close"].iloc[-2])\
&#x20;       change_pct = (\
&#x20;           (price / previous - 1) \* 100 if previous else 0\
&#x20;       )\
&#x20;       price_label = "Latest Candle Close"\
&#x20;       price_caption = (\
&#x20;           "Quote unavailable. Showing selected-interval candle close "\
&#x20;           f"from {data.index[-1]} instead."\
&#x20;       )\
\
&#x20;   c1, c2, c3, c4 = st.columns(4)\
\
&#x20;   c1.metric(price_label, f"${price:,.2f}", f"{change_pct:+.2f}%")\
&#x20;   c2.metric("Technical Signal", signal)\
&#x20;   c3.metric(\
&#x20;       "RSI (14)",\
&#x20;       f"{float(rsi):.1f}" if pd.notna(rsi) else "N/A",\
&#x20;   )\
&#x20;   c4.metric(\
&#x20;       "SMA 20",\
&#x20;       f"${float(last['SMA20']):,.2f}"\
&#x20;       if pd.notna(last["SMA20"]) else "N/A",\
&#x20;   )\
\
&#x20;   st.caption(\
&#x20;       price_caption + " Actual traded prices (not dividend-adjusted). "\
&#x20;       "Yahoo Finance data may be delayed."\
&#x20;   )\
\
&#x20;   UP_COLOR = "#238a23"\
&#x20;   DOWN_COLOR = "#d6404f"\
\
&#x20;   has_volume = "Volume" in data.columns\
&#x20;   fig = make_subplots(\
&#x20;       rows=2 if has_volume else 1,\
&#x20;       cols=1,\
&#x20;       shared_xaxes=True,\
&#x20;       vertical_spacing=0.0,\
&#x20;       row_heights=[0.84, 0.16] if has_volume else [1.0],\
&#x20;   )\
\
&#x20;   fig.add_trace(\
&#x20;       go.Candlestick(\
&#x20;           x=data.index,\
&#x20;           open=data["Open"],\
&#x20;           high=data["High"],\
&#x20;           low=data["Low"],\
&#x20;           close=data["Close"],\
&#x20;           name="Price",\
&#x20;           increasing=dict(\
&#x20;               line=dict(color=UP_COLOR, width=1),\
&#x20;               fillcolor=UP_COLOR,\
&#x20;           ),\
&#x20;           decreasing=dict(\
&#x20;               line=dict(color=DOWN_COLOR, width=1),\
&#x20;               fillcolor=DOWN_COLOR,\
&#x20;           ),\
&#x20;           whiskerwidth=0,\
&#x20;       ),\
&#x20;       row=1,\
&#x20;       col=1,\
&#x20;   )\
\
&#x20;   if show_sma:\
&#x20;       fig.add_trace(\
&#x20;           go.Scatter(\
&#x20;               x=data.index,\
&#x20;               y=data["SMA20"],\
&#x20;               name="SMA 20",\
&#x20;               line=dict(color="#f5a623", width=1.2),\
&#x20;           ),\
&#x20;           row=1,\
&#x20;           col=1,\
&#x20;       )\
\
&#x20;       fig.add_trace(\
&#x20;           go.Scatter(\
&#x20;               x=data.index,\
&#x20;               y=data["SMA50"],\
&#x20;               name="SMA 50",\
&#x20;               line=dict(color="#4a90e2", width=1.2),\
&#x20;           ),\
&#x20;           row=1,\
&#x20;           col=1,\
&#x20;       )\
\
&#x20;   if has_volume:\
&#x20;       vol_colors = [\
&#x20;           UP_COLOR if c >= o else DOWN_COLOR\
&#x20;           for o, c in zip(data["Open"], data["Close"])\
&#x20;       ]\
\
&#x20;       fig.add_trace(\
&#x20;           go.Bar(\
&#x20;               x=data.index,\
&#x20;               y=data["Volume"],\
&#x20;               name="Volume",\
&#x20;               marker=dict(\
&#x20;                   color=vol_colors,\
&#x20;                   line=dict(width=0),\
&#x20;               ),\
&#x20;               opacity=0.55,\
&#x20;               showlegend=False,\
&#x20;           ),\
&#x20;           row=2,\
&#x20;           col=1,\
&#x20;       )\
\
&#x20;       fig.update_yaxes(visible=False, row=2, col=1)\
\
&#x20;   breaks = [dict(bounds=["sat", "mon"])]\
\
&#x20;   if interval != "1d":\
&#x20;       breaks.append(dict(bounds=[16, 9.5], pattern="hour"))\
\
&#x20;   fig.update_xaxes(\
&#x20;       rangebreaks=breaks,\
&#x20;       showgrid=False,\
&#x20;       rangeslider_visible=False,\
&#x20;       showline=True,\
&#x20;       linecolor="#dddddd",\
&#x20;   )\
\
&#x20;   fig.update_yaxes(\
&#x20;       side="right",\
&#x20;       showgrid=True,\
&#x20;       gridcolor="#eeeeee",\
&#x20;       zeroline=False,\
&#x20;       tickformat=",.2f",\
&#x20;       row=1,\
&#x20;       col=1,\
&#x20;   )\
\
&#x20;   fig.update_layout(\
&#x20;       template="plotly_white",\
&#x20;       paper_bgcolor="white",\
&#x20;       plot_bgcolor="white",\
&#x20;       font=dict(color="#333333"),\
&#x20;       height=550,\
&#x20;       margin=dict(l=20, r=20, t=20, b=20),\
&#x20;       xaxis_rangeslider_visible=False,\
&#x20;       hovermode="x unified",\
&#x20;       legend=dict(orientation="h", y=1.02, x=0),\
&#x20;   )\
\
&#x20;   st.plotly_chart(fig, use_container_width=True)\
\
&#x20;   st.subheader("Why this signal was generated")\
&#x20;   st.write(f"Technical score: {score} | Valid checks: {checks} of 3")\
\
&#x20;   for reason in reasons:\
&#x20;       st.write("• " + reason)\
\
&#x20;   st.subheader("Candlestick Pattern Checks")\
\
&#x20;   for pattern in patterns:\
&#x20;       st.write("• " + pattern)\
\
&#x20;   st.subheader("RSI (14) Chart")\
\
&#x20;   rsi_fig = go.Figure()\
\
&#x20;   rsi_fig.add_trace(\
&#x20;       go.Scatter(\
&#x20;           x=data.index,\
&#x20;           y=data["RSI"],\
&#x20;           name="RSI",\
&#x20;       )\
&#x20;   )\
\
&#x20;   rsi_fig.add_hline(y=70, line_dash="dash", line_color="red")\
&#x20;   rsi_fig.add_hline(y=30, line_dash="dash", line_color="green")\
\
&#x20;   rsi_fig.update_layout(\
&#x20;       template="plotly_white",\
&#x20;       paper_bgcolor="white",\
&#x20;       plot_bgcolor="white",\
&#x20;       font=dict(color="#333333"),\
&#x20;       height=260,\
&#x20;       margin=dict(l=20, r=20, t=20, b=20),\
&#x20;       yaxis=dict(range=[0, 100], side="right", gridcolor="#eeeeee"),\
&#x20;       xaxis=dict(showgrid=False),\
&#x20;   )\
\
&#x20;   st.plotly_chart(rsi_fig, use_container_width=True)\
\
\
show_main_chart()\
st.divider()\
\
\# =========================================================\
\# NEWS AND EARNINGS CENTER\
\# =========================================================\
\
st.header("📰 News & Earnings Center")\
\
news_tab, earnings_tab = st.tabs([\
&#x20;   "📰 Stock News",\
&#x20;   "💰 Earnings & Financials",\
])\
\
with news_tab:\
&#x20;   show_news(ticker)\
\
with earnings_tab:\
&#x20;   show_earnings(ticker)\
\
\# =========================================================\
\# FOOTER\
\# =========================================================\
\
st.divider()\
\
st.caption(\
&#x20;   "Educational tool, not financial advice. Technical signals are not "\
&#x20;   "guaranteed predictions. Yahoo Finance data may be delayed or "\
&#x20;   "incomplete. Verify news, earnings dates, and prices with official "\
&#x20;   "sources before making financial decisions."\
)\
