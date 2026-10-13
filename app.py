
# BLACK BUY / SELL / HOLD SIGNAL BOX
signal_color = {
    "BUY WATCH": "#00e676",
    "SELL / AVOID NEW ENTRY": "#ff5252",
    "HOLD / WAIT": "#ffd740"
}.get(signal, "#ffffff")

st.markdown(
    f"""
    <div style="
        background-color: #000000;
        border: 2px solid #333333;
        border-radius: 8px;
        padding: 30px 20px;
        text-align: center;
        margin: 10px 0 25px 0;
    ">
        <div style="
            color: #aaaaaa;
            font-size: 14px;
            letter-spacing: 3px;
        ">STOCK SIGNAL</div>

        <div style="
            color: {signal_color};
            font-size: 38px;
            font-weight: 900;
            margin-top: 12px;
        ">{signal}</div>

        <div style="
            color: #aaaaaa;
            font-size: 13px;
            margin-top: 10px;
        ">{ticker} • Rule-based analysis</div>
    </div>
    """,
    unsafe_allow_html=True
)
