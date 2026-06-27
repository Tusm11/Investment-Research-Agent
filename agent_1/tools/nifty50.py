import yfinance as yf

NIFTY50 = [
    ("RELIANCE.NS", "Energy"),
    ("TCS.NS", "Technology"),
    ("HDFCBANK.NS", "Financial Services"),
    ("INFY.NS", "Technology"),
    ("ICICIBANK.NS", "Financial Services"),
    ("HINDUNILVR.NS", "Consumer Defensive"),
    ("ITC.NS", "Consumer Defensive"),
    ("SBIN.NS", "Financial Services"),
    ("BHARTIARTL.NS", "Communication Services"),
    ("KOTAKBANK.NS", "Financial Services"),
    ("LT.NS", "Industrials"),
    ("AXISBANK.NS", "Financial Services"),
    ("ASIANPAINT.NS", "Basic Materials"),
    ("MARUTI.NS", "Consumer Cyclical"),
    ("TITAN.NS", "Consumer Cyclical"),
    ("SUNPHARMA.NS", "Healthcare"),
    ("BAJFINANCE.NS", "Financial Services"),
    ("WIPRO.NS", "Technology"),
    ("HCLTECH.NS", "Technology"),
    ("ULTRACEMCO.NS", "Basic Materials"),
    ("NTPC.NS", "Utilities"),
    ("POWERGRID.NS", "Utilities"),
    ("M&M.NS", "Consumer Cyclical"),
    ("TATASTEEL.NS", "Basic Materials"),
    ("NESTLEIND.NS", "Consumer Defensive"),
    ("TECHM.NS", "Technology"),
    ("ADANIENT.NS", "Industrials"),
    ("JSWSTEEL.NS", "Basic Materials"),
    ("INDUSINDBK.NS", "Financial Services"),
    ("BAJAJFINSV.NS", "Financial Services"),
    ("TRENT.NS", "Consumer Cyclical"),
    ("ONGC.NS", "Energy"),
    ("COALINDIA.NS", "Energy"),
    ("GRASIM.NS", "Basic Materials"),
    ("CIPLA.NS", "Healthcare"),
    ("DRREDDY.NS", "Healthcare"),
    ("EICHERMOT.NS", "Consumer Cyclical"),
    ("BPCL.NS", "Energy"),
    ("HEROMOTOCO.NS", "Consumer Cyclical"),
    ("DIVISLAB.NS", "Healthcare"),
    ("APOLLOHOSP.NS", "Healthcare"),
    ("SBILIFE.NS", "Financial Services"),
    ("HDFCLIFE.NS", "Financial Services"),
    ("TATAMOTORS.NS", "Consumer Cyclical"),
    ("ADANIPORTS.NS", "Industrials"),
    ("BRITANNIA.NS", "Consumer Defensive"),
    ("LTTS.NS", "Technology"),
    ("HINDALCO.NS", "Basic Materials"),
    ("SHRIRAMFIN.NS", "Financial Services"),
]


def _metrics_from_info(info):
    revenue = info.get("totalRevenue") or 0
    fcf = info.get("freeCashflow") or 0
    return {
        "returnOnEquity": info.get("returnOnEquity"),
        "operatingMargins": info.get("operatingMargins"),
        "debtToEquity": info.get("debtToEquity"),
        "currentRatio": info.get("currentRatio"),
        "revenueGrowth": info.get("revenueGrowth"),
        "freeCashflow": fcf,
        "totalRevenue": revenue,
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
    }


def get_nifty50_data():
    tickers = [{"ticker": t, "sector": s} for t, s in NIFTY50]
    companies = []

    for ticker, sector in NIFTY50:
        try:
            info = yf.Ticker(ticker).info
            companies.append({
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "sector": sector,
                "metrics": _metrics_from_info(info),
            })
        except Exception as e:
            print(f"Nifty50 fetch skipped for {ticker}: {e}")
            companies.append({"ticker": ticker, "sector": sector, "metrics": {}})

    return {
        "tickers": tickers,
        "companies": companies,
        "count": len(tickers),
    }
