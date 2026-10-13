
@st.fragment(run_every="1s")
def show_market_clock():
    import pandas_market_calendars as mcal

    now = pd.Timestamp.now(tz="UTC")
    eastern_now = pd.Timestamp.now(tz="America/New_York")

    calendar = mcal.get_calendar("NYSE")

    schedule = calendar.schedule(
        start_date=eastern_now.date(),
        end_date=(eastern_now + pd.Timedelta(days=14)).date(),
    )

    current_session = None
    next_session = None

    for _, session in schedule.iterrows():
        market_open = session["market_open"]
        market_close = session["market_close"]

        if market_open <= now < market_close:
            current_session = session
        elif market_open > now and next_session is None:
            next_session = session

    st.subheader("🕒 US Stock Market Hours")

    if current_session is not None:
        opening = current_session["market_open"]
        closing = current_session["market_close"]

        open_seconds = max(0, int((closing - now).total_seconds()))
        hours, remainder = divmod(open_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.success("🟢 MARKET IS OPEN")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Today's opening time",
                opening.tz_convert("America/New_York").strftime(
                    "%I:%M %p ET"
                ),
            )

        with col2:
            st.metric(
                "Closes in",
                f"{hours:02d}:{minutes:02d}:{seconds:02d}",
            )

        st.info(
            "Market closes today at "
            + closing.tz_convert("America/New_York").strftime(
                "%I:%M %p ET"
            )
        )

    elif next_session is not None:
        opening = next_session["market_open"]
        closing = next_session["market_close"]

        open_seconds = max(0, int((opening - now).total_seconds()))
        days, remainder = divmod(open_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        st.warning("🔴 MARKET IS CLOSED")

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Opens in",
                f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}",
            )

        with col2:
            st.metric(
                "Next closing time",
                closing.tz_convert("America/New_York").strftime(
                    "%A, %b %d · %I:%M %p ET"
                ),
            )

        st.info(
            "Next opening: "
            + opening.tz_convert("America/New_York").strftime(
                "%A, %B %d at %I:%M %p ET"
            )
        )

    else:
        st.info("The next market session could not be determined.")


show_market_clock()
