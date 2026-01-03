import streamlit as st
import yfinance as yf
import pandas as pd
import requests  # <--- NEW: To access Yahoo's search API
from sklearn.linear_model import LinearRegression
import numpy as np

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StockValue AI", page_icon="📈", layout="centered")

# --- 2. CUSTOM CSS FOR "BIG VERDICT" ---
st.markdown("""
<style>
    /* Clean container look */
    .metric-container {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
    }
    /* THE BIG VERDICT BANNER */
    .verdict-box {
        padding: 25px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        color: white;
        box-shadow: 0 6px 10px rgba(0,0,0,0.15);
        border: 2px solid white;
    }
    .verdict-green { 
        background: linear-gradient(135deg, #28a745, #20c997); 
    }
    .verdict-red { 
        background: linear-gradient(135deg, #dc3545, #ff6b6b); 
    }
    .verdict-title { font-size: 32px; font-weight: 800; margin: 0; letter-spacing: 1px;}
    .verdict-sub { font-size: 20px; margin-top: 5px; opacity: 0.95; font-weight: 500;}

    /* Hide default Streamlit clutter */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 3. SMARTER BACKEND: AUTO-SEARCH & DATA FETCH ---

# A. THE "HIDDEN" YAHOO SEARCH API (Finds ticker from name)
@st.cache_data(ttl=3600*24)
def search_ticker(query):
    """
    Searches Yahoo Finance for the best matching ticker.
    Examples: 
    - Input: "Nvidia" -> Returns: "NVDA"
    - Input: "Reliance" -> Returns: "RELIANCE.NS"
    """
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'quotes' in data and len(data['quotes']) > 0:
            # Get the first result (most relevant)
            best_match = data['quotes'][0]
            return best_match['symbol']
    except Exception:
        pass
    return None

# B. DATA FETCHER
@st.cache_data(ttl=3600) 
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Validation: If no current price, the ticker is broken
        current_price = info.get('currentPrice')
        if not current_price:
            return None

        # Data for Graham Number
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        # Analyst Targets
        target_mean = info.get('targetMeanPrice', 0)
        recommendation = info.get('recommendationKey', 'none').replace('_', ' ').title()

        # Currency detection (INR vs USD)
        currency_symbol = "₹" if info.get('currency') == "INR" else "$"

        # AI Trend Prediction (Simple Linear Regression)
        history = stock.history(period="1y")
        trend_direction = "Neutral"
        prediction_30d = 0
        
        if not history.empty:
            history = history.reset_index()
            history['DateOrdinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
            
            X = history[['DateOrdinal']].values
            y = history['Close'].values
            
            # Train AI
            model = LinearRegression()
            model.fit(X, y)
            
            # Predict Future
            last_date = X[-1][0]
            future_date = last_date + 30
            prediction_30d = model.predict([[future_date]])[0]
            trend_direction = "UP" if prediction_30d > current_price else "DOWN"

        return {
            "symbol": ticker,
            "name": info.get('shortName', ticker),
            "price": current_price,
            "currency": currency_symbol,
            "eps": eps,
            "bvps": bvps,
            "target": target_mean,
            "rec": recommendation,
            "ai_pred": prediction_30d,
            "trend": trend_direction,
            "history": history
        }

    except Exception:
        return None

# --- 4. FRONTEND UI ---
st.title("📈 StockValue AI")
st.write("Smart Intrinsic Value Calculator (US & India)")

# --- SMART SEARCH BAR ---
user_query = st.text_input("Search Stock (e.g., 'Nvidia', 'Tata Motors', 'Zomato')", "").strip()

if user_query:
    # 1. First, find the REAL ticker code
    with st.spinner(f"🔍 Searching market for '{user_query}'..."):
        # Try direct search first (incase they typed NVDA)
        real_ticker = search_ticker(user_query)
        
        # Fallback: If they typed specific Indian format (RELIANCE.NS)
        if not real_ticker:
            real_ticker = user_query.upper()

    # 2. Fetch Data using the found ticker
    if real_ticker:
        data = get_stock_data(real_ticker)
        
        if data:
            # --- HEADER ---
            st.markdown(f"### 🏢 {data['name']} ({data['symbol']})")
            
            # --- THE BIG VERDICT BANNER (YOUR REQUEST) ---
            # Calculate Intrinsic Value (Graham Number)
            if data['eps'] > 0 and data['bvps'] > 0:
                graham_num = (22.5 * data['eps'] * data['bvps']) ** 0.5
                diff = ((graham_num - data['price']) / data['price']) * 100
                
                # Logic for Green/Red Banner
                if diff > 10: # More than 10% Undervalued
                    st.markdown(f"""
                    <div class="verdict-box verdict-green">
                        <p class="verdict-title">✅ UNDERVALUED</p>
                        <p class="verdict-sub">Trading {diff:.1f}% BELOW Fair Value</p>
                    </div>
                    """, unsafe_allow_html=True)
                elif diff < -10: # More than 10% Overvalued
                    st.markdown(f"""
                    <div class="verdict-box verdict-red">
                        <p class="verdict-title">❌ OVERVALUED</p>
                        <p class="verdict-sub">Trading {abs(diff):.1f}% ABOVE Fair Value</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info(f"⚖️ **FAIRLY VALUED:** Trading within {abs(diff):.1f}% of intrinsic value.")
                
                # --- DETAILED NUMBERS ---
                c1, c2, c3 = st.columns(3)
                c1.metric("Current Price", f"{data['currency']}{data['price']:.2f}")
                c2.metric("True Fair Value", f"{data['currency']}{graham_num:.2f}", help="Benjamin Graham Formula")
                c3.metric("Safety Margin", f"{diff:.1f}%")

            else:
                st.warning("⚠️ **Hard to Value:** Company has negative earnings. Graham Formula does not apply.")
                st.metric("Current Price", f"{data['currency']}{data['price']:.2f}")

            st.divider()

            # --- AI & ANALYSTS ---
            st.subheader("🔮 Predictions")
            k1, k2 = st.columns(2)
            
            with k1:
                st.markdown("**🤖 AI Trend (30 Days)**")
                if data['trend'] == "UP":
                    st.success(f"📈 Forecast to Rise to **{data['currency']}{data['ai_pred']:.2f}**")
                else:
                    st.error(f"📉 Forecast to Drop to **{data['currency']}{data['ai_pred']:.2f}**")
            
            with k2:
                st.markdown("**🤵 Analyst Consensus**")
                if data['target'] and data['target'] > 0:
                    st.info(f"Target: **{data['currency']}{data['target']}** ({data['rec']})")
                else:
                    st.write("No analyst targets available.")

            # --- CHART ---
            st.subheader("📊 1-Year Price Action")
            st.line_chart(data['history'].set_index('Date')['Close'])
            
        else:
            st.error(f"❌ Found ticker '{real_ticker}' but could not fetch data. It might be delisted.")
    else:
        st.error("❌ Stock not found. Try typing the company name clearly.")

# --- MONETIZATION COMPONENT ---
def show_monetization_options(currency_symbol):
    st.divider()
    st.markdown("### 🚀 Take Action")
    
    col1, col2, col3 = st.columns(3)
    
    # OPTION C: Education (Amazon)
    with col3:
        st.success("📚 **Learn the Math**")
        https://amzn.to/4jlK6gE
        st.markdown("[**Buy 'Intelligent Investor'**](#) \n\n The book Warren Buffett recommends.")

    st.caption("Transparency: We may earn a commission if you use this link, at no extra cost to you.")

st.divider()
st.subheader("📩 Get Undervalued Stocks Weekly")
email = st.text_input("Enter your email to get our top 5 picks every Monday:", placeholder="you@example.com")
if st.button("Subscribe Free"):
    # In a real app, save this to a database. 
    # For now, just log it or tell them it's coming soon.
    st.success("Thanks! You are on the list.")
    # You can use a tool like 'ConvertKit' or 'Mailchimp' forms here easily.
