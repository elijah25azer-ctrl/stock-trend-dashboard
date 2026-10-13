
    # High-contrast signal box
    signal_colors = {
        "BUY": "#00ff66",
        "SELL": "#ff4040",
        "HOLD": "#ffd740",
        "INSUFFICIENT DATA": "#ffffff",
    }

    signal_color = signal_colors.get(signal, "#ffffff")

    st.markdown(
        f"""
        <div style="
            background-color: #101820;
            border: 3px solid {signal_color};
            border-radius: 16px;
            padding: 28px 16px;
            text-align: center;
            margin: 12px 0 24px 0;
            width: 100%;
            box-sizing: border-box;
        ">
            <div style="
                color: #ffffff;
                font-size: 15px;
                font-weight: bold;
                letter-spacing: 3px;
            ">TECHNICAL SIGNAL</div>

            <div style="
                color: {signal_color};
                font-size: 60px;
                line-height: 1.2;
                font-weight: 900;
                margin: 14px 0;
                display: block;
                visibility: visible;
                opacity: 1;
                text-shadow: 0 0 8px {signal_color};
            ">{signal}</div>

            <div style="
                color: #ffffff;
                font-size: 22px;
                font-weight: bold;
            ">
                {ticker} · ${price:,.2f}
            </div>

            <div style="
                color: #cccccc;
                font-size: 13px;
                margin-top: 12px;
            ">
                Latest available candle · {data.index[-1]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
