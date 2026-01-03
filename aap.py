import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import timedelta
from sklearn.linear_model import LinearRegression
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StockValue AI", page_icon="📈", layout="centered")

# --- 2. CUSTOM STYLING ---
# This makes the app look professional and hides the default Streamlit menu
st.markdown("""
<style>
    .metric-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. THE BACKEND (Data Fetching & AI) ---
@st.cache_data(ttl=3600*24) # Cache data for 24 hours to prevent IP bans
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        
        # A. Fetch Basic Info
        info = stock.info
        current_price = info.get('currentPrice')
        
        # If no price found, the ticker is likely invalid
        if not current_price:
            return None

        # B. Graham Number Data (Intrinsic Value)
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        # C. Analyst Consensus
        target_mean = info.get('targetMeanPrice', 0)
        recommendation = info.get('recommendationKey', 'none').replace('_', ' ').title()

        # D. AI Trend Prediction (Linear Regression)
        # Get 1 year of history
        history = stock.history(period="1y")
        
        if not history.empty:
            history = history.reset_index()
            # Convert dates to numbers for math model
            history['DateOrdinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
            
            # Train the Model
            X = history[['DateOrdinal']].values
            y = history['Close'].values
            model = LinearRegression()
            model.fit(X, y)
            
            # Predict 30 days into future
            last_date_ordinal = X[-1][0]
            future_date_ordinal = last_date_ordinal + 30
            prediction_30d = model.predict([[future_date_ordinal]])[0]
            
            trend_direction = "UP" if prediction_30d > current_price else "DOWN"
        else:
            prediction_30d = 0
            trend_direction = "Neutral"

        return {
            "symbol": ticker,
            "name": info.get('shortName', ticker),
            "price": current_price,
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

# --- 4. THE FRONTEND (User Interface) ---
st.title("📈 StockValue AI")
st.write("Free Intrinsic Value Calculator + AI Price Predictor")

# Search Bar
ticker_input = st.text_input("Enter Stock Symbol (e.g., AAPL, TSLA, NVDA)", "").upper().strip()

if ticker_input:
    with st.spinner(f"Analyzing {ticker_input}..."):
        data = get_stock_data(ticker_input)

    if data:
        # --- HEADER ---
        st.header(f"{data['name']} ({data['symbol']})")
        
        # --- TOP METRICS ---
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"${data['price']}")
        
        # Color code the prediction
        pred_color = "normal"
        if data['trend'] == "UP":
            col3.metric("AI 30-Day Forecast", f"${data['ai_pred']:.2f}", "Bullish")
        else:
            col3.metric("AI 30-Day Forecast", f"${data['ai_pred']:.2f}", "-Bearish")

        col2.metric("Wall St. Target", f"${data['target_mean']}", data['recommendation'])

        st.divider()

        # --- SECTION 1: INTRINSIC VALUE (Graham Number) ---
        st.subheader("💰 Intrinsic Value (Graham Formula)")
        st.caption("Based on Benjamin Graham's formula (Warren Buffett's mentor). Ideal for defensive value investors.")
        
        if data['eps'] > 0 and data['bvps'] > 0:
            graham_num = (22.5 * data['eps'] * data['bvps']) ** 0.5
            upside = ((graham_num - data['price']) / data['price']) * 100
            
            c1, c2 = st.columns(2)
            c1.metric("Fair Value Price", f"${graham_num:.2f}")
            if upside > 0:
                c2.metric("Potential Upside", f"{upside:.2f}%", "Undervalued")
                st.success(f"✅ **BUY SIGNAL:** Trading {upside:.1f}% BELOW fair value.")
            else:
                c2.metric("Overvaluation", f"{upside:.2f}%", "-Overvalued")
                st.error(f"⚠️ **CAUTION:** Trading {abs(upside):.1f}% ABOVE fair value.")
        else:
            st.warning("⚠️ Cannot calculate Graham Number. This company likely has negative earnings (lost money recently).")

        # --- SECTION 2: CHARTS ---
        st.subheader("📉 1-Year Price Trend")
        st.line_chart(data['history'].set_index('Date')['Close'])

        # --- SECTION 3: MONETIZATION (How you earn) ---
        st.divider()
        st.info("💡 **Tip:** Never trade alone. Use professional tools.")
        
        m1, m2 = st.columns(2)
        with m1:
            # REPLACE '#' WITH YOUR AFFILIATE LINKS
            st.markdown("👉 **[Open Account on Robinhood](#)**") 
            st.caption("Get a free stock when you sign up.")
        with m2:
            st.markdown("👉 **[Read 'The Intelligent Investor'](#)**")
            st.caption("Learn the math behind this calculator.")
            
    else:
        st.error("❌ Stock not found. Please check the symbol (e.g., try 'AAPL').")