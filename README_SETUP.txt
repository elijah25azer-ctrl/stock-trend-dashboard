STOCK TREND DASHBOARD — EASY WINDOWS SETUP
===========================================

WHAT IT DOES
- Shows a stock-price chart and recent price changes.
- Includes moving averages and RSI (momentum indicator).
- Gives a simple UPWARD TREND, DOWNWARD TREND, or MIXED signal.
- Compares popular stocks such as MSFT, NVDA, AAPL, AMZN, GOOGL, META, TSLA, and AMD.

IMPORTANT LIMITATIONS
This dashboard cannot know the future. Its signal is a simple educational rule, not a validated forecast or a guarantee. It may be wrong, and you can lose money. Quotes may be delayed or unavailable. Verify prices in your brokerage app. This is not financial advice.

INSTALL (Windows 10/11)
1. Install Python from https://www.python.org/downloads/
   During setup, check "Add Python to PATH" if that option appears.
2. Extract the ZIP file into a folder, such as Desktop\StockDashboard.
3. Open the extracted folder in File Explorer.
4. Click the address bar, type cmd, and press Enter.
5. In the command window, run:

   py -m pip install -r requirements.txt

6. After installation finishes, run:

   py -m streamlit run app.py

7. A browser tab should open with the dashboard. If not, copy the local URL printed in the command window into your browser.
8. To stop the app, return to the command window and press Ctrl+C.

USE IT
- Type a ticker such as MSFT or NVDA in the left sidebar.
- Choose how much price history to display.
- Click Refresh data to request a fresh download.
- Compare multiple popular stocks near the bottom.
- The dashboard needs an internet connection to fetch price data.

TROUBLESHOOTING
- If "py is not recognized", reinstall Python and enable PATH, or try `python` instead of `py`.
- If a ticker returns no data, check its spelling and try again later.
- If installation fails, check your internet connection and try the install command again.
- Do not enter brokerage passwords or account details. This app does not connect to Cash App or place trades.
