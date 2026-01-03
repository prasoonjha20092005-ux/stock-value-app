@st.cache_data(ttl=3600)
def get_stock_data(ticker):
    """
    Fetches data with 3 layers of fallback to prevent 'None' errors.
    """
    try:
        stock = yf.Ticker(ticker)
        
        # --- LAYER 1: GET PRICE (Most Critical) ---
        # We use fast_info or history because .info is often blocked
        current_price = 0.0
        try:
            # fast_info is reliable and doesn't trigger bot detection often
            current_price = stock.fast_info['last_price']
        except:
            # Fallback: Download 1 day of history
            try:
                hist = stock.history(period="1d")
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                else:
                    return None # Ticker likely doesn't exist
            except:
                return None # Failed to get price
                
        # --- LAYER 2: GET METADATA (Info) ---
        # We wrap this in a separate try-except so if it fails, we still show the price
        info = {}
        try:
            info = stock.info
        except:
            # If Yahoo blocks 'info', we use an empty dict and just show price
            pass

        # Safely extract data with defaults if missing
        currency = "₹" if info.get('currency') == "INR" else "$"
        name = info.get('shortName', ticker)
        
        # Financials for Valuation
        eps = info.get('trailingEps', 0)
        bvps = info.get('bookValue', 0)
        pe = info.get('trailingPE', 0)
        
        # Negative Earnings Logic
        negative_earnings = eps < 0
        graham_num = (22.5 * eps * bvps) ** 0.5 if (eps > 0 and bvps > 0) else 0

        # --- LAYER 3: AI TREND ---
        trend = "Neutral"
        pred_price = 0
        try:
            history = stock.history(period="1y")
            if not history.empty:
                history = history.reset_index()
                history['Ordinal'] = pd.to_datetime(history['Date']).map(pd.Timestamp.toordinal)
                model = LinearRegression()
                model.fit(history[['Ordinal']], history['Close'])
                future_date = history['Ordinal'].iloc[-1] + 30
                pred = model.predict([[future_date]])[0]
                pred_price = pred
                trend = "Bullish" if pred > current_price else "Bearish"
        except:
            pass # AI failure shouldn't crash the app

        return {
            "symbol": ticker,
            "name": name,
            "currency": currency,
            "price": current_price,
            "change": current_price - info.get('previousClose', current_price), # Default to 0 change if missing
            "pct_change": 0.0, # Simplified for fallback
            "market_cap": info.get('marketCap', 0),
            "high_52": info.get('fiftyTwoWeekHigh', 0),
            "low_52": info.get('fiftyTwoWeekLow', 0),
            "pe": pe,
            "pb": info.get('priceToBook', 0),
            "eps": eps,
            "book_value": bvps,
            "div_yield": info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            "sector": info.get('sector', 'Unknown'),
            "industry": info.get('industry', 'Unknown'),
            "website": info.get('website', '#'),
            "summary": info.get('longBusinessSummary', 'Summary unavailable due to API limits.'),
            "graham_num": graham_num,
            "negative_earnings": negative_earnings,
            "ai_trend": trend,
            "ai_price": pred_price,
            "analyst_target": info.get('targetMeanPrice', 0),
            "analyst_rec": info.get('recommendationKey', 'none').replace('_', ' ').title(),
            "stock_obj": stock
        }
    except Exception as e:
        print(f"Error: {e}") # Print error to console logs for debugging
        return None
