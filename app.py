import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(page_title="Stock Decision Dashboard", page_icon="📈", layout="wide")

DEFAULT_WATCHLIST = ["MSFT", "NVDA", "AAPL", "AMZN", "GOOGL", "META", "TSLA", "AMD", "SPY", "QQQ"]

st.title("📈 Stock Decision Dashboard")
st.caption("Research assistant: buy-watch, wait/hold, or consider-exit signals based on simple technical rules. Signals are uncertain and are not personalized financial advice.")

with st.sidebar:
    st.header("Stock settings")
    ticker_input = st.text_input("Stock ticker", value="MSFT", help="Examples: MSFT, NVDA, AAPL, TSLA, SPY")
    period = st.selectbox("Chart history", ["3mo", "6mo", "1y", "2y", "5y"], index=2)
    interval = st.selectbox("Price interval", ["1d", "1wk"], index=0)
    if st.button("🔄 Refresh data", use_container_width=True):
        st.cache_data.clear()
    st.divider()
    st.subheader("Popular tickers")
    selected_watch = st.selectbox("Choose a ticker", DEFAULT_WATCHLIST)
    if st.button("Use selected ticker", use_container_width=True):
        st.session_state["ticker_override"] = selected_watch
        st.rerun()

ticker = st.session_state.get("ticker_override", ticker_input).strip().upper()
if not ticker:
    st.warning("Enter a stock ticker.")
    st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def load_history(symbol, selected_period, selected_interval):
    data = yf.download(symbol, period=selected_period, interval=selected_interval,
                       auto_adjust=True, progress=False, threads=False)
    if data.empty:
        return pd.DataFrame()
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna(subset=["Close"]).copy()

with st.spinner(f"Loading market data for {ticker}..."):
    try:
        df = load_history(ticker, period, interval)
    except Exception as exc:
        st.error(f"Could not load data for {ticker}. Check the ticker and try again.")
        st.caption(f"Technical detail: {exc}")
        st.stop()

if df.empty or len(df) < 25:
    st.error("Not enough price history was returned for this ticker. Check the symbol or choose a longer chart history.")
    st.stop()

df["SMA20"] = df["Close"].rolling(20).mean()
df["SMA50"] = df["Close"].rolling(50).mean()
delta = df["Close"].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rs = gain / loss.replace(0, float("nan"))
df["RSI14"] = 100 - (100 / (1 + rs))
df["RSI14"] = df["RSI14"].fillna(50)
df["Volatility20"] = df["Close"].pct_change().rolling(20).std() * (252 ** 0.5 if interval == "1d" else 52 ** 0.5)

latest = df.iloc[-1]
prev = df.iloc[-2]
price = float(latest["Close"])
sma20 = float(latest["SMA20"]) if pd.notna(latest["SMA20"]) else price
sma50 = float(latest["SMA50"]) if pd.notna(latest["SMA50"]) else sma20
rsi = float(latest["RSI14"])
recent_low = float(df["Low"].tail(20).min()) if "Low" in df.columns else float(df["Close"].tail(20).min())
recent_high = float(df["High"].tail(20).max()) if "High" in df.columns else float(df["Close"].tail(20).max())

# Transparent heuristic: not trained or backtested, and not a probability forecast.
score = 0
reasons = []
if price > sma20:
    score += 1
    reasons.append("Latest price is above the 20-period average (positive short-term sign).")
else:
    score -= 1
    reasons.append("Latest price is below the 20-period average (negative short-term sign).")
if sma20 > sma50:
    score += 1
    reasons.append("20-period average is above the 50-period average (positive trend sign).")
else:
    score -= 1
    reasons.append("20-period average is below the 50-period average (negative trend sign).")
if 45 <= rsi <= 65:
    score += 1
    reasons.append(f"RSI is {rsi:.1f}, within a middle range that avoids very weak or very stretched momentum.")
elif rsi < 35:
    reasons.append(f"RSI is {rsi:.1f}, showing weak/oversold momentum; that alone is not a buy signal.")
elif rsi > 70:
    score -= 1
    reasons.append(f"RSI is {rsi:.1f}, indicating strong but potentially stretched momentum.")
else:
    reasons.append(f"RSI is {rsi:.1f}; momentum is not in the app's preferred middle range.")

if score >= 2 and rsi < 70:
    signal = "BUY WATCH"
    color = "normal"
    summary = "Several indicators lean positive. This is a prompt for further research, not an instruction to buy."
elif score <= -1 or rsi >= 75:
    signal = "CONSIDER EXIT / AVOID NEW ENTRY"
    color = "inverse"
    summary = "The current rule set sees weakness or stretched momentum. This does not mean the price must fall."
else:
    signal = "HOLD / WAIT"
    color = "off"
    summary = "The indicators are mixed or not strong enough for a clear setup."

# Illustrative levels based on recent prices and a simple risk/reward framework.
atr_proxy = float((df["High"] - df["Low"]).tail(14).mean()) if {"High", "Low"}.issubset(df.columns) else float(df["Close"].diff().abs().tail(14).mean())
atr_proxy = max(atr_proxy if pd.notna(atr_proxy) else price * 0.02, price * 0.005)
stop_level = max(0.01, min(recent_low, price - 1.5 * atr_proxy))
risk_per_share = max(price - stop_level, price * 0.01)
target_level = price + 2 * risk_per_share

st.subheader(f"{ticker} decision overview")
st.caption(f"Latest data point returned: {df.index[-1].date()}. Data may be delayed or incomplete; verify quotes with a reliable provider before making any decision.")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Latest adjusted close", f"${price:,.2f}", f"{(price / float(prev['Close']) - 1) * 100:+.2f}% vs prior point")
m2.metric("Rule-based signal", signal)
m3.metric("RSI (14)", f"{rsi:.1f}")
m4.metric("20-period average", f"${sma20:,.2f}")

st.info(summary)
st.markdown("### Why the app gave this signal")
for reason in reasons:
    st.write(f"• {reason}")

st.markdown("### Example levels to research")
a, b, c = st.columns(3)
a.metric("Reference price", f"${price:,.2f}")
b.metric("Illustrative risk level", f"${stop_level:,.2f}", help="A hypothetical level based on recent lows/volatility. A stop order may fill at a worse price, or not at all.")
c.metric("Illustrative target", f"${target_level:,.2f}", help="A simple 2-to-1 reward/risk example, not a forecast or promise.")
st.caption("These levels are mechanical examples based on recent price history. They do not account for your finances, taxes, goals, or risk tolerance. Gaps and fast markets can cause actual results to differ.")

fig = go.Figure()
fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode="lines", name="Adjusted close"))
fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], mode="lines", name="20-period average"))
fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], mode="lines", name="50-period average"))
fig.add_hline(y=stop_level, line_dash="dash", annotation_text="Example risk level")
fig.add_hline(y=target_level, line_dash="dash", annotation_text="Example target")
fig.update_layout(height=480, xaxis_title="Date", yaxis_title="Price (USD)", legend_orientation="h", legend_y=1.08, margin=dict(l=10,r=10,t=50,b=10))
st.plotly_chart(fig, use_container_width=True)

with st.expander("How this decision system works"):
    st.write("The signal is a transparent rule-based checklist using price vs. 20-period average, 20-period vs. 50-period average, and RSI (14). It is not an AI prediction, has not been validated as profitable, and does not calculate a real probability of a stock rising.")
    st.write("BUY WATCH means indicators lean positive; HOLD / WAIT means the setup is unclear; CONSIDER EXIT / AVOID NEW ENTRY means indicators show weakness or potentially stretched momentum. These labels can be wrong.")
    st.write("This app does not place trades, connect to Cash App, or know your personal financial situation. Consider paper trading and discuss real investing decisions with a trusted adult or qualified financial professional.")

st.divider()
st.caption("Educational use only • No guaranteed predictions • Not a recommendation to buy or sell any specific security")
