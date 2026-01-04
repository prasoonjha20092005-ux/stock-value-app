import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from fpdf import FPDF
from datetime import datetime

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="StockValue AI", page_icon="📈", layout="wide")

st.markdown("""
<style>
    /* Clean UI Overrides */
    .stApp { background-color: #FAFAFA; }
    
    /* BIG VERDICT BANNERS */
    .verdict-box {
        padding: 20px; 
        border-radius: 12px; 
        color: white; 
        text-align: center; 
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        font-family: 'Arial', sans-serif;
    }
    .verdict-green { background: linear-gradient(135deg, #28a745, #20c997); }
    .verdict-red { background: linear-gradient(135deg, #dc3545, #ff6b6b); }
    .verdict-neutral { background: linear-gradient(135deg, #304352, #d7d2cc); }
    
    .verdict-title { font-size: 28px; font-weight: 800; margin: 0; letter-spacing: 1px;}
    .verdict-sub { font-size: 18px; margin-top: 5px; opacity: 0.95; font-weight: 500;}
    
    /* Hide Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- 2. BACKEND FUNCTIONS ---

@st.cache_data(ttl=3600*24)
def search_ticker(query):
    """Finds the best ticker from a search query using Yahoo's hidden API."""
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5).json()
        if 'quotes' in response and len(response['quotes']) > 0:
            return response['quotes'][0]['symbol']
    except Exception:
        pass
    return None

@st.cache_data(ttl=900)
def get_stock_data(ticker):
    """
    Robust Data Fetcher: Tries 3 methods to avoid API blocks.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # LAYER 1: GET PRICE (Critical)
        current_price = 0.0
        try:
            current_price = stock.fast_info['last_price']
        except:
            try:
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                else:
                    return None
            except:
                return None

        # LAYER 2: GET INFO (Metadata)
        info = {}
        try:
            info = stock.info
        except:
            pass 

        # Defaults if API partially fails
        currency = "₹" if info.get('currency') == "INR" else "$"
        name = info.get('shortName', ticker)
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        
        # Valuation Logic
        negative_earnings = eps < 0
        graham_num = 0
        if eps > 0 and bvps > 0:
            graham_num = (22.5 * eps * bvps) ** 0.5 

        # LAYER 3: HISTORY & AI TREND PREDICTION
        trend_direction = "Neutral"
        ai_price_target = 0
        history = pd.DataFrame() # Default empty
        
        try:
            # We fetch history HERE so we can save the data, not the object
            history = stock.history(period="1y")
            
            if not history.empty:
                # Calculate AI Trend
                history_ai = history.reset_index()
                history_ai['DateOrdinal'] = pd.to_datetime(history_ai['Date']).map(pd
