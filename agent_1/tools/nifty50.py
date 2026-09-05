import yfinance as yf

NIFTY50 = [
    ("ADANIENT.NS", "Industrials"),
    ("ADANIPORTS.NS", "Industrials"),
    ("APOLLOHOSP.NS", "Healthcare"),
    ("ASIANPAINT.NS", "Basic Materials"),
    ("AXISBANK.NS", "Financial Services"),
    ("BAJAJ-AUTO.NS", "Consumer Cyclical"),
    ("BAJAJFINSV.NS", "Financial Services"),
    ("BAJFINANCE.NS", "Financial Services"),
    ("BHARTIARTL.NS", "Communication Services"),
    ("BPCL.NS", "Energy"),
    ("BRITANNIA.NS", "Consumer Defensive"),
    ("CIPLA.NS", "Healthcare"),
    ("COALINDIA.NS", "Energy"),
    ("DIVISLAB.NS", "Healthcare"),
    ("DRREDDY.NS", "Healthcare"),
    ("EICHERMOT.NS", "Consumer Cyclical"),
    ("GRASIM.NS", "Basic Materials"),
    ("HCLTECH.NS", "Technology"),
    ("HDFCBANK.NS", "Financial Services"),
    ("HDFCLIFE.NS", "Financial Services"),
    ("HEROMOTOCO.NS", "Consumer Cyclical"),
    ("HINDALCO.NS", "Basic Materials"),
    ("HINDUNILVR.NS", "Consumer Defensive"),
    ("ICICIBANK.NS", "Financial Services"),
    ("INDUSINDBK.NS", "Financial Services"),
    ("INFY.NS", "Technology"),
    ("ITC.NS", "Consumer Defensive"),
    ("JSWSTEEL.NS", "Basic Materials"),
    ("KOTAKBANK.NS", "Financial Services"),
    ("LT.NS", "Industrials"),
    ("LTTS.NS", "Technology"),
    ("M&M.NS", "Consumer Cyclical"),
    ("MARUTI.NS", "Consumer Cyclical"),
    ("NESTLEIND.NS", "Consumer Defensive"),
    ("NTPC.NS", "Utilities"),
    ("ONGC.NS", "Energy"),
    ("POWERGRID.NS", "Utilities"),
    ("RELIANCE.NS", "Energy"),
    ("SBILIFE.NS", "Financial Services"),
    ("SBIN.NS", "Financial Services"),
    ("SHRIRAMFIN.NS", "Financial Services"),
    ("SUNPHARMA.NS", "Healthcare"),
    ("TATACONSUM.NS", "Consumer Defensive"),
    ("TATASTEEL.NS", "Basic Materials"),
    ("TCS.NS", "Technology"),
    ("TECHM.NS", "Technology"),
    ("TITAN.NS", "Consumer Cyclical"),
    ("ULTRACEMCO.NS", "Basic Materials"),
    ("UPL.NS", "Basic Materials"),
    ("WIPRO.NS", "Technology")
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
            # Silently skip tickers with errors (delisted or invalid)
            companies.append({"ticker": ticker, "sector": sector, "metrics": {}})

    return {
        "tickers": tickers,
        "companies": companies,
        "count": len(tickers),
    }
