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
    .metric-card {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        text-align: center;
    }
    .big-verdict {
        padding: 20px; border-radius: 12px; color: white; text-align: center; margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
    }
    .verdict-green { background: linear-gradient(135deg, #00b09b, #96c93d); }
    .verdict-red { background: linear-gradient(135deg, #ff5f6d, #ffc371); }
    .verdict-neutral { background: linear-gradient(135deg, #304352, #d7d2cc); }
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Table Styling */
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

# --- 2. HELPER FUNCTIONS ---

@st.cache_data(ttl=3600)
def search_ticker(query):
    """Finds the best ticker from a search query using Yahoo API"""
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers).json()
        if 'quotes' in response and len(response['quotes']) > 0:
            return response['quotes'][0]['symbol']
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    """Fetches comprehensive data similar to Moneycontrol"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Validation
        if 'currentPrice' not in info:
            return None

        # Basic Info
        currency = "₹" if info.get('currency') == "INR" else "$"
        
        # Financials for Valuation
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        pe = info.get('trailingPE', 0)
        sector_pe = info.get('trailingPE', 20) # Proxy if missing
        
        # Negative Earnings Logic
        negative_earnings = eps < 0
        
        # Graham Number (Only valid if EPS > 0)
        graham_num = (22.5 * eps * bvps) ** 0.5 if (eps > 0 and bvps > 0) else 0

        # AI Trend
        history = stock.history(period="1y")
        trend = "Neutral"
        if not history.empty:
            history = history.reset_index()
            history['Ordinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
            model = LinearRegression()
            model.fit(history[['Ordinal']], history['Close'])
            future_date = history['Ordinal'].iloc[-1] + 30
            pred = model.predict([[future_date]])[0]
            trend = "Bullish" if pred > info['currentPrice'] else "Bearish"

        return {
            "symbol": ticker,
            "name": info.get('shortName', ticker),
            "currency": currency,
            "price": info.get('currentPrice'),
            "change": info.get('currentPrice') - info.get('previousClose', 0),
            "pct_change": ((info.get('currentPrice') - info.get('previousClose', 1)) / info.get('previousClose', 1)) * 100,
            "market_cap": info.get('marketCap', 0),
            "high_52": info.get('fiftyTwoWeekHigh'),
            "low_52": info.get('fiftyTwoWeekLow'),
            "pe": pe,
            "pb": info.get('priceToBook'),
            "eps": eps,
            "book_value": bvps,
            "div_yield": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown'),
            "website": info.get('website', '#'),
            "summary": info.get('longBusinessSummary', 'No summary available.'),
            "graham_num": graham_num,
            "negative_earnings": negative_earnings,
            "ai_trend": trend,
            "ai_price": pred if not history.empty else 0,
            "analyst_target": info.get('targetMeanPrice', 0),
            "analyst_rec": info.get('recommendationKey', 'none').replace('_', ' ').title(),
            "stock_obj": stock # Pass the object for charts
        }
    except Exception as e:
        return None

def create_pdf(data):
    """Generates a PDF report of the analysis"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"Investment Report: {data['name']} ({data['symbol']})", ln=True, align='C')
    pdf.ln(10)
    
    # Pricing
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Current Price: {data['currency']}{data['price']}", ln=True)
    pdf.cell(200, 10, txt=f"52-Week High/Low: {data['currency']}{data['high_52']} / {data['currency']}{data['low_52']}", ln=True)
    pdf.ln(5)
    
    # Valuation
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Valuation Analysis", ln=True)
    pdf.set_font("Arial", size=12)
    
    if data['negative_earnings']:
        pdf.set_text_color(220, 50, 50)
        pdf.cell(200, 10, txt="WARNING: Company has negative earnings (Loss-making).", ln=True)
        pdf.cell(200, 10, txt="Graham Number method is not applicable.", ln=True)
        pdf.set_text_color(0, 0, 0)
    else:
        pdf.cell(200, 10, txt=f"Intrinsic Value (Graham): {data['currency']}{data['graham_num']:.2f}", ln=True)
        margin = ((data['graham_num'] - data['price']) / data['price']) * 100
        status = "UNDERVALUED" if margin > 0 else "OVERVALUED"
        pdf.cell(200, 10, txt=f"Verdict: {status} by {abs(margin):.1f}%", ln=True)
        
    pdf.ln(5)
    pdf.cell(200, 10, txt=f"Analyst Consensus: {data['analyst_rec']} (Target: {data['currency']}{data['analyst_target']})", ln=True)
    pdf.cell(200, 10, txt=f"AI Trend Prediction (30 Days): {data['ai_trend']}", ln=True)
    
    # Footer
    pdf.set_y(-30)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, f"Generated by MarketLens AI on {datetime.now().strftime('%Y-%m-%d')}", 0, 0, 'C')
    
    return pdf.output(dest='S').encode('latin-1')

# --- 3. MAIN APP LAYOUT ---
st.title("📊 MarketLens AI")
st.markdown("*Professional-grade intrinsic value & trend analyzer.*")

# Search Bar
col_search, col_dropdown = st.columns([2, 1])
with col_search:
    search_query = st.text_input("🔍 Search Stock", placeholder="e.g., Reliance, Tata Motors, Nvidia...", label_visibility="collapsed")

# Logic to handle "dropdown" feel
ticker = None
if search_query:
    with st.spinner("Finding best match..."):
        ticker = search_ticker(search_query)

if ticker:
    data = get_stock_data(ticker)
    
    if data:
        # --- A. HEADER SECTION ---
        st.markdown("---")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"## {data['name']}")
            st.caption(f"{data['sector']} | {data['industry']}")
            st.markdown(f"### {data['currency']}{data['price']}  <span style='color:{'green' if data['change']>0 else 'red'}; font-size:18px'> {data['change']:+.2f} ({data['pct_change']:+.2f}%)</span>", unsafe_allow_html=True)
        
        with c2:
            st.metric("Market Cap", f"{data['currency']}{data['market_cap'] / 1e9:,.1f}B")
        with c3:
            st.metric("P/E Ratio", f"{data['pe']:.2f}" if data['pe'] else "N/A")
        with c4:
             # PDF Download Button
            pdf_bytes = create_pdf(data)
            st.download_button(label="📄 Download Report", data=pdf_bytes, file_name=f"{data['symbol']}_Report.pdf", mime='application/pdf')

        # --- B. THE VERDICT BANNER ---
        st.markdown("<br>", unsafe_allow_html=True)
        if data['negative_earnings']:
            st.markdown(f"""
            <div class="big-verdict verdict-neutral">
                <h2>⚠️ NEGATIVE EARNINGS</h2>
                <p>This company is currently making a LOSS (EPS: {data['eps']}).<br>Intrinsic value cannot be calculated using standard value investing formulas.</p>
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

        # --- C. INTERACTIVE CHART (1D, 1M, etc) ---
        st.subheader("📈 Price Chart")
        period = st.select_slider("Select Timeframe", options=["1mo", "3mo", "6mo", "1y", "5y", "max"], value="1y")
        
        chart_data = data['stock_obj'].history(period=period)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=chart_data.index,
                        open=chart_data['Open'], high=chart_data['High'],
                        low=chart_data['Low'], close=chart_data['Close'], name='Price'))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

        # --- D. DETAILED METRICS (Moneycontrol Style) ---
        st.subheader("📋 Key Fundamentals")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("52W High", f"{data['currency']}{data['high_52']}")
        m2.metric("52W Low", f"{data['currency']}{data['low_52']}")
        m3.metric("Book Value", f"{data['currency']}{data['book_value']}")
        m4.metric("Dividend Yield", f"{data['div_yield']:.2f}%")
        
        # --- E. AI & ANALYST SECTION ---
        st.markdown("---")
        st.subheader("🤖 Future Predictions")
        col_ai, col_analyst = st.columns(2)
        
        with col_ai:
            st.info(f"**AI Trend (30 Days):** {data['ai_trend']}")
            st.caption(f"Predicted Price Target: {data['currency']}{data['ai_price']:.2f}")
            st.markdown("*Based on Linear Regression of last 1 year price movement.*")
            
        with col_analyst:
            st.success(f"**Wall St. Consensus:** {data['analyst_rec']}")
            st.caption(f"Average Target: {data['currency']}{data['analyst_target']}")
            st.markdown("*Aggregated from major institutional analysts.*")

        # --- F. ABOUT / DISCLAIMER ---
        with st.expander("ℹ️ How This Works (Methodology)"):
            st.markdown("""
            **1. Intrinsic Value:** Uses the **Benjamin Graham Formula** `sqrt(22.5 * EPS * BVPS)`. This is strictly for profitable companies.
            **2. AI Prediction:** Uses **Scikit-Learn Linear Regression** on the last 365 days of closing prices to project the trend line 30 days out.
            **3. Analyst Consensus:** Pulled directly from institutional data (Reuters/Refinitiv via Yahoo Finance).
            **Disclaimer:** This tool is for educational purposes only. Do not buy/sell based solely on this data.
            """)

    else:
        st.error(f"Could not load data for {ticker}. The stock might be delisted or the API is busy.")

else:
    # --- LANDING PAGE HINT ---
    if not search_query:
        st.info("👆 Type a company name above to begin.")
