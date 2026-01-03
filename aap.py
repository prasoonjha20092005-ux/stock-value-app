import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
import base64
from datetime import datetime, timedelta

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="MarketLens AI", page_icon="📊", layout="wide")

st.markdown("""
<style>
    /* Clean UI Overrides */
    .stApp { background-color: #FAFAFA; }
    
    /* BIG VERDICT BANNERS */
    .big-verdict {
        padding: 20px; 
        border-radius: 12px; 
        color: white; 
        text-align: center; 
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        font-family: 'Arial', sans-serif;
    }
    .verdict-green { background: linear-gradient(135deg, #00b09b, #96c93d); }
    .verdict-red { background: linear-gradient(135deg, #ff5f6d, #ffc371); }
    .verdict-neutral { background: linear-gradient(135deg, #304352, #d7d2cc); }
    
    /* Header & Text Styling */
    h1, h2, h3 { font-family: 'Helvetica', sans-serif; }
    .metric-label { font-size: 14px; color: #555; }
    .metric-value { font-size: 24px; font-weight: bold; color: #000; }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. ROBUST BACKEND FUNCTIONS ---

@st.cache_data(ttl=3600*24)
def search_ticker(query):
    """
    Finds the best ticker from a search query using Yahoo's hidden API.
    Handles 'Nvidia' -> 'NVDA', 'Reliance' -> 'RELIANCE.NS'
    """
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5).json()
        
        if 'quotes' in response and len(response['quotes']) > 0:
            # Filter for Equity to avoid indices/options if possible
            for quote in response['quotes']:
                if quote.get('quoteType') == 'EQUITY':
                    return quote['symbol']
            # Fallback to first result
            return response['quotes'][0]['symbol']
    except Exception as e:
        print(f"Search Error: {e}")
    return None

@st.cache_data(ttl=900) # Cache for 15 mins
def get_stock_data(ticker):
    """
    Fetches data with 3 layers of fallback to prevent 'None' errors and API blocks.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # --- LAYER 1: GET PRICE (Critical) ---
        # We try fast_info first, then history. .info is last because it blocks often.
        current_price = 0.0
        try:
            current_price = stock.fast_info['last_price']
        except:
            try:
                # Fallback: Download 1 day of history
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                else:
                    return None # Ticker likely doesn't exist
            except:
                return None # Completely failed to get price

        # --- LAYER 2: GET METADATA (Info) ---
        # We accept that this might fail on cloud servers, so we use defaults.
        info = {}
        try:
            info = stock.info
        except:
            pass # Continue with empty info if blocked

        # Safely extract data with defaults
        currency = "₹" if info.get('currency') == "INR" else "$"
        name = info.get('shortName', ticker)
        
        # Financials for Valuation
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        pe = info.get('trailingPE', 0)
        
        # Valuation Logic
        negative_earnings = eps < 0
        graham_num = 0
        if eps > 0 and bvps > 0:
            graham_num = (22.5 * eps * bvps) ** 0.5 

        # --- LAYER 3: AI TREND PREDICTION ---
        trend_direction = "Neutral"
        ai_price_target = 0
        try:
            history = stock.history(period="1y")
            if not history.empty:
                history = history.reset_index()
                # Use Ordinal dates for Linear Regression
                history['DateOrdinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
                
                X = history[['DateOrdinal']].values
                y = history['Close'].values
                
                model = LinearRegression()
                model.fit(X, y)
                
                # Predict 30 days out
                future_ordinal = X[-1][0] + 30
                ai_price_target = model.predict([[future_ordinal]])[0]
                
                trend_direction = "Bullish" if ai_price_target > current_price else "Bearish"
        except:
            pass 

        return {
            "symbol": ticker,
            "name": name,
            "currency": currency,
            "price": current_price,
            "change": current_price - info.get('previousClose', current_price),
            "pct_change": 0.0, # Simplified fallback
            "market_cap": info.get('marketCap', 0),
            "high_52": info.get('fiftyTwoWeekHigh', 0),
            "low_52": info.get('fiftyTwoWeekLow', 0),
            "pe": pe,
            "eps": eps,
            "bvps": bvps,
            "div_yield": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            "sector": info.get('sector', 'Unknown'),
            "summary": info.get('longBusinessSummary', 'Summary unavailable due to API limits.'),
            "graham_num": graham_num,
            "negative_earnings": negative_earnings,
            "ai_trend": trend_direction,
            "ai_price": ai_price_target,
            "analyst_target": info.get('targetMeanPrice', 0),
            "analyst_rec": info.get('recommendationKey', 'N/A').replace('_', ' ').title(),
            "stock_obj": stock
        }
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return None

def create_pdf(data):
    """Generates a PDF report of the analysis."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, txt=f"Investment Report: {data['name']} ({data['symbol']})", ln=True, align='C')
    pdf.ln(10)
    
    # Snapshot
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Price: {data['currency']}{data['price']:.2f} | Sector: {data['sector']}", ln=True)
    pdf.ln(5)
    
    # Valuation Section
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, txt="Valuation Analysis", ln=True)
    pdf.set_font("Arial", size=12)
    
    if data['negative_earnings']:
        pdf.set_text_color(220, 50, 50) # Red
        pdf.cell(0, 10, txt="WARNING: Negative Earnings (Loss-making company).", ln=True)
        pdf.cell(0, 10, txt="Standard intrinsic value models do not apply.", ln=True)
        pdf.set_text_color(0, 0, 0)
    elif data['graham_num'] > 0:
        margin = ((data['graham_num'] - data['price']) / data['price']) * 100
        verdict = "UNDERVALUED" if margin > 0 else "OVERVALUED"
        pdf.cell(0, 10, txt=f"Intrinsic Value (Graham): {data['currency']}{data['graham_num']:.2f}", ln=True)
        pdf.cell(0, 10, txt=f"Verdict: {verdict} by {abs(margin):.1f}%", ln=True)
        
    pdf.ln(10)
    pdf.cell(0, 10, txt=f"AI Prediction (30d): {data['ai_trend']} (Target: {data['currency']}{data['ai_price']:.2f})", ln=True)
    pdf.cell(0, 10, txt=f"Analyst Consensus: {data['analyst_rec']}", ln=True)
    
    # Footer
    pdf.set_y(-30)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, f"Generated by MarketLens AI - {datetime.now().strftime('%Y-%m-%d')}", 0, 0, 'C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP LAYOUT ---
st.title("📊 MarketLens AI")
st.markdown("Before you invest, check the *real* value.")

# Search Bar with Smart Logic
col_search, col_dropdown = st.columns([3, 1])
with col_search:
    search_query = st.text_input("🔍 Search Stock", placeholder="Type name (e.g. Zomato, Nvidia, Tata Motors)", label_visibility="collapsed")

ticker = None
if search_query:
    # Check if input looks like a ticker (3-5 chars) or a name
    if len(search_query) < 6 and search_query.isalpha():
         # Assume it's a ticker if short
         ticker = search_query.upper()
         # Specific fix for Indian users typing 'RELIANCE' without .NS
         if ticker in ["RELIANCE", "TATASTEEL", "HDFCBANK", "INFY", "ITC", "SBIN"]:
             ticker += ".NS"
    else:
        # It's a name, use Smart Search
        with st.spinner(f"Searching market for '{search_query}'..."):
            ticker = search_ticker(search_query)

if ticker:
    # Fetch Data
    data = get_stock_data(ticker)
    
    if data:
        # --- A. HEADER SECTION ---
        st.markdown("---")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"## {data['name']} ({data['symbol']})")
            st.caption(f"Sector: {data['sector']}")
            # Color code price change
            color = "green" if data['change'] >= 0 else "red"
            st.markdown(f"### {data['currency']}{data['price']:.2f} <span style='color:{color}; font-size:18px'> {data['change']:+.2f}</span>", unsafe_allow_html=True)
        
        with c2:
            st.metric("Market Cap", f"{data['currency']}{data['market_cap'] / 1e9:,.1f}B")
        with c3:
            st.metric("P/E Ratio", f"{data['pe']:.2f}" if data['pe'] else "N/A")
        with c4:
             # PDF Download
            try:
                pdf_bytes = create_pdf(data)
                st.download_button(label="📄 Download PDF", data=pdf_bytes, file_name=f"{data['symbol']}_Report.pdf", mime='application/pdf')
            except Exception as e:
                st.warning("PDF Gen failed (font issue on cloud).")

        # --- B. THE VERDICT BANNER ---
        st.markdown("<br>", unsafe_allow_html=True)
        
        if data['negative_earnings']:
            st.markdown(f"""
            <div class="big-verdict verdict-neutral">
                <h2>⚠️ NEGATIVE EARNINGS</h2>
                <p>Company is currently loss-making (EPS: {data['eps']}).<br>Graham Intrinsic Value cannot be calculated.</p>
            </div>
            """, unsafe_allow_html=True)
        elif data['graham_num'] > 0:
            diff = ((data['graham_num'] - data['price']) / data['price']) * 100
            if diff > 15:
                st.markdown(f"""
                <div class="big-verdict verdict-green">
                    <h2>✅ UNDERVALUED</h2>
                    <p>Trading {diff:.1f}% BELOW Fair Value ({data['currency']}{data['graham_num']:.2f})</p>
                </div>
                """, unsafe_allow_html=True)
            elif diff < -15:
                st.markdown(f"""
                <div class="big-verdict verdict-red">
                    <h2>❌ OVERVALUED</h2>
                    <p>Trading {abs(diff):.1f}% ABOVE Fair Value ({data['currency']}{data['graham_num']:.2f})</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="big-verdict verdict-neutral">
                    <h2>⚖️ FAIRLY VALUED</h2>
                    <p>Trading within normal range of Fair Value ({data['currency']}{data['graham_num']:.2f})</p>
                </div>
                """, unsafe_allow_html=True)

        # --- C. INTERACTIVE CHART ---
        st.subheader("📈 Price Chart")
        
        # Timeframe Selector
        t_col1, t_col2 = st.columns([1, 4])
        with t_col1:
            period = st.selectbox("Timeframe", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
        
        # Plotly Chart
        hist = data['stock_obj'].history(period=period)
        if not hist.empty:
            fig = go.Figure(data=[go.Candlestick(x=hist.index,
                            open=hist['Open'], high=hist['High'],
                            low=hist['Low'], close=hist['Close'])])
            fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chart data unavailable.")

        # --- D. DETAILED METRICS ---
        st.subheader("📋 Key Fundamentals")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("52W High", f"{data['currency']}{data['high_52']}")
        m2.metric("52W Low", f"{data['currency']}{data['low_52']}")
        m3.metric("Book Value", f"{data['currency']}{data['bvps']}")
        m4.metric("Div. Yield", f"{data['div_yield']:.2f}%")
        
        # --- E. AI & ANALYST PREDICTIONS ---
        st.markdown("---")
        st.subheader("🤖 Future Intelligence")
        col_ai, col_analyst = st.columns(2)
        
        with col_ai:
            st.info(f"**AI Trend (30 Days):** {data['ai_trend']}")
            if data['ai_price'] > 0:
                st.caption(f"Projected Target: {data['currency']}{data['ai_price']:.2f}")
            st.markdown("*Based on Linear Regression of 1-year price history.*")
            
        with col_analyst:
            st.success(f"**Wall St. Consensus:** {data['analyst_rec']}")
            if data['analyst_target'] > 0:
                st.caption(f"Analyst Target: {data['currency']}{data['analyst_target']}")
            st.markdown("*Aggregated from major institutional analysts.*")

        # --- F. FOOTER ---
        with st.expander("ℹ️ How we calculate this"):
            st.markdown("""
            * **Intrinsic Value:** Uses the Graham Formula `sqrt(22.5 * EPS * BVPS)`. Only applies to profitable companies.
            * **AI Prediction:** A Linear Regression model trained on the last 365 days of close prices.
            * **Data Source:** Real-time market data via Yahoo Finance API.
            """)
            
    else:
        st.error(f"Could not load data for '{search_query}'. The stock might be delisted or the name is unclear.")
        st.info("Try searching for the specific ticker symbol (e.g., 'NVDA' or 'RELIANCE.NS').")

else:
    if not search_query:
        st.info("👆 Enter a stock name above to start analysis.")
