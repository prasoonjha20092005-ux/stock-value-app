import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
from sklearn.linear_model import LinearRegression
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StockValue AI", page_icon="📈", layout="centered")

# --- 2. CUSTOM STYLING (BIG VERDICT) ---
st.markdown("""
<style>
    /* Main container styling */
    .metric-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    
    /* BIG VERDICT BANNERS */
    .verdict-box {
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 20px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .verdict-green { background-color: #28a745; } /* Green for Undervalued */
    .verdict-red { background-color: #dc3545; }   /* Red for Overvalued */
    
    .verdict-title { font-size: 24px; font-weight: bold; margin: 0; }
    .verdict-sub { font-size: 18px; margin: 5px 0 0 0; opacity: 0.9; }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. SMARTER BACKEND (India Support) ---
@st.cache_data(ttl=3600*24)
def get_stock_data(user_input):
    # CLEAN INPUT
    ticker = user_input.upper().strip()
    
    # SEARCH STRATEGY: 
    # 1. Try exact match (e.g., "NVDA", "AAPL")
    # 2. Try adding .NS (for Indian NSE, e.g., "RELIANCE" -> "RELIANCE.NS")
    search_attempts = [ticker, f"{ticker}.NS"]
    
    stock = None
    info = None
    found_ticker = None
    
    for t in search_attempts:
        try:
            temp_stock = yf.Ticker(t)
            temp_info = temp_stock.info
            # Check if we actually got a price (validates the ticker)
            if temp_info and 'currentPrice' in temp_info:
                stock = temp_stock
                info = temp_info
                found_ticker = t
                break # Stop searching if we found it
        except Exception:
            continue

    if not stock:
        return None

    # Proceed with the found stock
    try:
        current_price = info.get('currentPrice')
        currency = info.get('currency', 'USD') # Get currency (USD or INR)
        
        # Graham Number Data
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        # Analyst Consensus
        target_mean = info.get('targetMeanPrice', 0)
        recommendation = info.get('recommendationKey', 'none').replace('_', ' ').title()

        # AI Trend (Linear Regression)
        history = stock.history(period="1y")
        if not history.empty:
            history = history.reset_index()
            history['DateOrdinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
            
            X = history[['DateOrdinal']].values
            y = history['Close'].values
            model = LinearRegression()
            model.fit(X, y)
            
            last_date_ordinal = X[-1][0]
            future_date_ordinal = last_date_ordinal + 30
            prediction_30d = model.predict([[future_date_ordinal]])[0]
            
            trend_direction = "UP" if prediction_30d > current_price else "DOWN"
        else:
            prediction_30d = 0
            trend_direction = "Neutral"

        return {
            "symbol": found_ticker,
            "name": info.get('shortName', found_ticker),
            "price": current_price,
            "currency": currency,
            "eps": eps,
            "bvps": bvps,
            "target_mean": target_mean,
            "recommendation": recommendation,
            "ai_pred": prediction_30d,
            "trend": trend_direction,
            "history": history
        }

    except Exception as e:
        return None

# --- 4. THE FRONTEND ---
st.title("📈 StockValue AI")
st.write("Free Intrinsic Value Calculator + AI Price Predictor")

# Input Section
col_search, col_help = st.columns([3, 1])
with col_search:
    ticker_input = st.text_input("Enter Stock (e.g., NVDA, RELIANCE, TATASTEEL)", "").upper().strip()
with col_help:
    st.write("") # Spacer
    st.write("") 
    st.markdown("[🔍 Find Ticker](https://finance.yahoo.com/lookup)", unsafe_allow_html=True)

if ticker_input:
    with st.spinner(f"Searching for '{ticker_input}' in US & India Markets..."):
        data = get_stock_data(ticker_input)

    if data:
        # SYMBOL & PRICE
        st.header(f"{data['name']} ({data['symbol']})")
        curr_symbol = "₹" if data['currency'] == "INR" else "$"
        
        # --- THE BIG VERDICT SECTION (NEW) ---
        st.divider()
        st.subheader("⚖️ The Verdict")
        
        # Calculate Graham Number
        if data['eps'] > 0 and data['bvps'] > 0:
            graham_num = (22.5 * data['eps'] * data['bvps']) ** 0.5
            diff = ((graham_num - data['price']) / data['price']) * 100
            
            # LOGIC FOR BIG BANNER
            if diff > 0:
                # UNDERVALUED (GREEN)
                st.markdown(f"""
                <div class="verdict-box verdict-green">
                    <p class="verdict-title">✅ UNDERVALUED</p>
                    <p class="verdict-sub">Trading {diff:.1f}% BELOW Fair Value</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                # OVERVALUED (RED)
                st.markdown(f"""
                <div class="verdict-box verdict-red">
                    <p class="verdict-title">❌ OVERVALUED</p>
                    <p class="verdict-sub">Trading {abs(diff):.1f}% ABOVE Fair Value</p>
                </div>
                """, unsafe_allow_html=True)
                
            # Detailed Numbers
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"{curr_symbol}{data['price']:.2f}")
            c2.metric("True Fair Value", f"{curr_symbol}{graham_num:.2f}")
            c3.metric("Safety Margin", f"{diff:.1f}%")
            
        else:
            st.warning("⚠️ Cannot calculate Fair Value (Negative Earnings). This is often a risky sign.")
            st.metric("Current Price", f"{curr_symbol}{data['price']:.2f}")

        # --- AI & ANALYSTS ---
        st.divider()
        st.subheader("🔮 AI & Wall St. Prediction")
        
        ac1, ac2 = st.columns(2)
        with ac1:
            st.markdown("**🤖 AI Trend (30 Days)**")
            if data['trend'] == "UP":
                st.success(f"📈 Bullish: Forecast to hit **{curr_symbol}{data['ai_pred']:.2f}**")
            else:
                st.error(f"📉 Bearish: Forecast to drop to **{curr_symbol}{data['ai_pred']:.2f}**")
                
        with ac2:
            st.markdown("**🤵 Wall St. Consensus**")
            st.info(f"Target: **{curr_symbol}{data['target_mean']}** ({data['recommendation']})")

        # --- CHART ---
        st.line_chart(data['history'].set_index('Date')['Close'])
            
    else:
        st.error(f"❌ Could not find stock '{ticker_input}'.")
        st.info("💡 **Tip:** Use Ticker Symbols.")
        st.markdown("""
        * **US Stocks:** Try **NVDA** (not Nvidia), **AAPL** (not Apple).
        * **Indian Stocks:** Try **RELIANCE**, **TATASTEEL**, **HDFCBANK**.
        """)
