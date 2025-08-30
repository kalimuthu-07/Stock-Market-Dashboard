import streamlit as st
import yfinance as yf
import matplotlib.pyplot as plt
import feedparser
import pandas as pd
import pandas_ta as ta
import mysql.connector
from streamlit_option_menu import option_menu

import matplotlib.dates as mdates




if "page" not in st.session_state:
    st.session_state.page = "login"   
if "user" not in st.session_state:
    st.session_state.user = None
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

 

def init_session():
    for key in ["username", "user_id", "page"]:
        if key not in st.session_state:
            st.session_state[key] = None
    if st.session_state["page"] is None:
        st.session_state["page"] = "login"
   

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Kali@0609",
        database="stock_db"
    )


def check_login(username, password):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    return user

def check_signup(full_name, username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (full_name, username, password) VALUES (%s, %s, %s)",
            (full_name, username, password)
        )
        conn.commit()
        return True
    except mysql.connector.Error as e:
        st.error(f"Error signing up: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def get_user_watchlist(user_id):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT ticker FROM watchlist_prices WHERE user_id = %s", (user_id,))
    result = cursor.fetchall()
    cursor.close()
    conn.close()
    return [row["ticker"] for row in result]

def add_to_watchlist(user_id, ticker, date, close_price):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO watchlist_prices (user_id, ticker, date, close_price)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE date=VALUES(date), close_price=VALUES(close_price)
        """, (user_id, ticker, date, close_price))
        conn.commit()
        st.success(f"{ticker} added to your watchlist")
    except Exception as e:
        st.error(f"Database error: {e}")
    finally:
        cursor.close()
        conn.close()


def login_page():
    st.title("Stock Dashboard Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        user = check_login(username, password)
        if user:
            st.session_state.user = user
            st.session_state.page = "home"
        else:
            st.error("Invalid username or password")
    st.markdown("---")
    if st.button("Create a new account"):
        st.session_state.page = "signup"



def signup_page():
    st.title("Stock Dashboard Signup")

    full_name = st.text_input("Full Name", key="signup_fullname")
    username = st.text_input("Username", key="signup_username")
    password = st.text_input("Password", type="password", key="signup_password")
    confirm_password = st.text_input("Confirm Password", type="password", key="signup_confirm")

    if st.button("Sign Up"):
       
        if not full_name.strip() or not username.strip() or not password or not confirm_password:
            st.warning("Please fill all fields")
        elif password != confirm_password:
            st.warning("Passwords do not match")
        else:
            success = check_signup(full_name, username, password)
            if success:
                st.success("Signup successful! Please login.")
                st.session_state.page = "login"




def page_home():
    st.title("Home")
    user = st.session_state.get('user')
    st.subheader(f"Welcome {user['full_name']}")

    watchlist_data = get_user_watchlist(user['id'])
    if watchlist_data:
        selected_ticker = st.selectbox("Select a Ticker from Your Watchlist:", watchlist_data)
        st.write("You selected:", selected_ticker)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        
        cursor.execute("""
            SELECT date, close_price 
            FROM watchlist_prices
            WHERE ticker=%s AND user_id=%s
            ORDER BY date DESC LIMIT 1
        """, (selected_ticker, user['id']))
        latest = cursor.fetchone()

        if latest:
            st.success(f"Latest Close Price for {selected_ticker} on {latest['date']}: {latest['close_price']}")

        
        cursor.execute("""
            SELECT date, close_price AS close
            FROM watchlist_prices
            WHERE ticker=%s AND user_id=%s
            ORDER BY date DESC LIMIT 7
        """, (selected_ticker, user['id']))
        rows = cursor.fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame(rows).sort_values("date")

           
            fig, ax = plt.subplots(figsize=(8,4))  
            ax.plot(df["date"], df["close"], marker="o", linestyle="-", linewidth=2, color="blue")

           
            ax.set_title(f"{selected_ticker} - Last 7 Days", fontsize=14, fontweight="bold")
            ax.set_xlabel("Date", fontsize=12)
            ax.set_ylabel("Close Price", fontsize=12)

           
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

           
            ax.grid(True, linestyle="--", alpha=0.6)

          
            for i, row in df.iterrows():
                ax.text(row["date"], row["close"], f"{row['close']:.2f}", 
                        ha="center", va="bottom", fontsize=9, color="black")

            st.pyplot(fig)

        else:
            st.warning(f"No historical data for {selected_ticker}")
    else:
        st.info("Your watchlist is empty.")


def page_historical_data():
    st.title("Historical Data Section")
    ticker = st.text_input("Enter stock ticker (e.g., AAPL, TSLA, MSFT):").upper()
    date_range = st.selectbox("Select Date Range:", ["1mo", "6mo", "1y"])

    history = pd.DataFrame()
    if ticker:
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period=date_range)

            if not history.empty:
                st.subheader(f" Historical Data for {ticker}")
                st.dataframe(history)

                if st.button("Download CSV"):
                    filename = f"{ticker}_history.csv"
                    history.to_csv(filename)
                    st.success(f"Downloaded as {filename}")
            else:
                st.warning(f"No historical data found for {ticker}")
        except Exception as e:
            st.error(f"Error fetching data for {ticker}: {e}")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_data (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticker VARCHAR(10),
            date DATE,
            open FLOAT,
            high FLOAT,
            low FLOAT,
            close FLOAT,
            volume BIGINT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist_prices (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT,
            ticker VARCHAR(10),
            date DATE,
            close_price FLOAT
        )
    """)

    conn.commit()

    if st.button("save Historical Data to DB") and not history.empty:
        try:
            history_clean = history.dropna(subset=["Open", "High", "Low", "Close", "Volume"])
            insert_count = 0
            for index, row in history_clean.iterrows():
                cursor.execute("""
                    INSERT IGNORE INTO historical_data (ticker, date, open, high, low, close, volume)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    ticker.upper(),
                    index.date(),
                    float(row['Open']),
                    float(row['High']),
                    float(row['Low']),
                    float(row['Close']),
                    int(row['Volume'])
                ))
                insert_count += 1
            conn.commit()
            st.success(f"Saved {insert_count} rows for {ticker.upper()} to MySQL.")
        except Exception as e:
            st.error(f"Error saving data: {e}")

   
    user = st.session_state.get("user", None)
    if st.button("Add to Watchlist"):
        if not user:
            st.warning("Please log in to add stocks to your watchlist.")
            st.stop()

        if not ticker:
            st.warning("Please enter a stock ticker.")
            st.stop()

        ticker_upper = ticker.upper()

        if "watchlist" not in st.session_state:
            st.session_state.watchlist = []

        if ticker_upper not in st.session_state.watchlist:
            st.session_state.watchlist.append(ticker_upper)
            st.success(f"{ticker_upper} added to watchlist.")

            latest_price = history["Close"].iloc[-1] if not history.empty else None
            if latest_price:
                cursor.execute("""
                    INSERT INTO watchlist_prices (user_id, ticker, date, close_price)
                    VALUES (%s, %s, %s, %s)
                """, (
                    user["id"],
                    ticker_upper,
                    pd.Timestamp.today().date(),
                    float(latest_price)
                ))
                conn.commit()
                st.info("Watchlist stock price saved to database.")
            else:
                st.warning("Could not retrieve latest price for this stock.")
        else:
            st.info(f"{ticker_upper} is already in your watchlist.")

    cursor.close()
    conn.close()

def page_news_data():
    st.subheader(" Latest News for Any Stock Ticker")

    ticker_input = st.text_input(
        "Enter comma-separated ticker symbols (e.g., AAPL, TSLA, INFY.NS):"
    )

    if ticker_input:
        selected_tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

        def fetch_news(ticker_symbol):
            feed_url = f"https://finance.yahoo.com/rss/headline?s={ticker_symbol}"
            feed = feedparser.parse(feed_url)
            return feed.entries

        for ticker in selected_tickers:
            st.markdown(f"## News for {ticker}")
            news_entries = fetch_news(ticker)

            if news_entries:
                for entry in news_entries[:5]:
                    with st.container():
                        st.markdown(
                            f"""
                            <div style="background-color: #f8f9fa;
                                        padding: 16px 20px;
                                        border-radius: 10px;
                                        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
                                        margin-bottom: 18px;
                                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
                                <h4 style="margin: 0 0 6px 0; font-size: 16px;">
                                    <a href="{entry.link}" target="_blank" style="text-decoration: none; color: #1a0dab;">
                                        {entry.title}
                                    </a>
                                </h4>
                                <p style="color: gray; font-size: 13px; margin: 0;">
                                    🗓 Published on {entry.published}
                                </p>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.info(f"No news found for {ticker}.")
def page_technical_analysis():
    st.title(" Technical Analysis")
    ticker = st.text_input("Enter Ticker:").upper().strip()
    if ticker:
        try:
            stock = yf.Ticker(ticker)
            history = stock.history(period="3mo")
            if not history.empty:
                
                rsi = ta.rsi(history['Close'], length=14)
                st.subheader("RSI (Relative Strength Index)")
                fig_rsi, ax_rsi = plt.subplots()
                ax_rsi.plot(rsi, color='orange')
                ax_rsi.axhline(70, color='red', linestyle='--')
                ax_rsi.axhline(30, color='green', linestyle='--')
                st.pyplot(fig_rsi)

                
                st.markdown("""
                **RSI Explanation**  
                - RSI (Relative Strength Index) measures the **speed and change of price movements**.  
                - Values above **70** → Stock is considered **overbought** (possible trend reversal down).  
                - Values below **30** → Stock is considered **oversold** (possible trend reversal up).  
                """)

              
                macd = ta.macd(history['Close'])
                st.subheader("MACD (Moving Average Convergence Divergence)")
                fig_macd, ax_macd = plt.subplots()
                ax_macd.plot(macd['MACD_12_26_9'], label='MACD')
                ax_macd.plot(macd['MACDs_12_26_9'], label='Signal')
                ax_macd.bar(macd.index, macd['MACDh_12_26_9'], color='gray', alpha=0.3)
                ax_macd.legend()
                st.pyplot(fig_macd)

                
                st.markdown("""
                **MACD Explanation**  
                - MACD is a **trend-following momentum indicator**.  
                - It shows the relationship between two moving averages (12-day and 26-day).  
                - When **MACD crosses above Signal line** → bullish signal.  
                - When **MACD crosses below Signal line** → bearish signal.  
                - Histogram shows the **strength of momentum**.  
                """)
        except Exception as e:
            st.error(f"Error: {e}")

def page_compare_stocks():
    st.title("Compare Multiple Stocks")
    ticker_input = st.text_input("Enter comma-separated tickers:")
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

    if st.button("COMPARE") and tickers:
        prices = {}
        for symbol in tickers:
            try:
                data = yf.Ticker(symbol).history(period="5d")
                if not data.empty:
                    prices[symbol] = data["Close"].iloc[-1]
            except Exception as e:
                st.warning(f"Error fetching {symbol}: {e}")
        
        if prices:
            fig, ax = plt.subplots()
            bars = ax.bar(prices.keys(), prices.values())

           
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height,
                    f"{height:.2f}",   
                    ha="center", va="bottom", fontsize=10, fontweight="bold"
                )

            ax.set_ylabel("Closing Price")
            ax.set_title("Latest Closing Prices of Selected Stocks")
            st.pyplot(fig)




def main():
    user = st.session_state.get("user")
if st.session_state.get("user") is not None:
    with st.sidebar:
        selected = option_menu(
            menu_title=f"Welcome {st.session_state['user']['full_name']}",
            options=["Home", "Historical Data", "News Data", "Technical Analysis", "Compare Stocks", "Logout"],
            icons=["house", "clock-history", "newspaper", "activity", "bar-chart", "box-arrow-right"]
        )

    if selected == "Home":
        page_home()
    elif selected == "Historical Data":
        page_historical_data()
    elif selected == "News Data":
        page_news_data()
    elif selected == "Technical Analysis":
        page_technical_analysis()
    elif selected == "Compare Stocks":
        page_compare_stocks()
    elif selected == "Logout":
        del st.session_state['user']
        st.rerun()

else:
       
        if st.session_state.page == "login":
            login_page()
        elif st.session_state.page == "signup":
            signup_page()
