import logging
import warnings
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

# Suppress yfinance warnings
warnings.filterwarnings("ignore")
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('yfinance').propagate = False

# Suppress httpx logs
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('httpx').propagate = False

logger = logging.getLogger(__name__)

def _get_nselib_history(ticker: str, days: int) -> pd.DataFrame:
    try:
        import nselib
        from nselib import capital_market
        
        # Remove .NS for nselib
        symbol = ticker.replace(".NS", "").replace(".BO", "")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # nselib expects format dd-mm-yyyy
        from_str = start_date.strftime("%d-%m-%Y")
        to_str = end_date.strftime("%d-%m-%Y")
        
        df = capital_market.price_volume_and_deliverable_position_data(
            symbol=symbol, 
            from_date=from_str, 
            to_date=to_str
        )
        
        if df is None or df.empty:
            return pd.DataFrame()
            
        # Clean up column names to match yfinance (Open, High, Low, Close, Volume)
        # Nselib typically returns: Date, OpenPrice, HighPrice, LowPrice, ClosePrice, TotalTradedQuantity
        col_map = {
            "OpenPrice": "Open",
            "HighPrice": "High",
            "LowPrice": "Low",
            "ClosePrice": "Close",
            "TotalTradedQuantity": "Volume",
            "Date": "Date"
        }
        
        df = df.rename(columns=col_map)
        
        # Ensure numeric
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                if isinstance(df[col].iloc[0], str):
                    df[col] = df[col].str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors="coerce")
                
        # Parse date and set as index to match yfinance behavior if needed, 
        # but for our use we often reset_index anyway.
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], format="%d-%b-%Y", errors="coerce")
            df = df.sort_values("Date").set_index("Date")
            
        return df
    except Exception as e:
        logger.warning(f"nselib fallback failed for {ticker}: {e}")
        return pd.DataFrame()


def get_price_history(ticker: str, period: str = "180d") -> pd.DataFrame:
    """
    Attempts to fetch price history using yfinance.
    Falls back to nselib if yfinance fails or returns empty data.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist is not None and not hist.empty:
            return hist
    except Exception as e:
        logger.warning(f"yfinance history failed for {ticker} (period={period}): {e}")
        
    logger.info(f"Using nselib fallback for {ticker}")
    
    # Convert period string to days approx
    days = 180
    if "d" in period:
        days = int(period.replace("d", ""))
    elif "mo" in period:
        days = int(period.replace("mo", "")) * 30
    elif "y" in period:
        days = int(period.replace("y", "")) * 365
        
    hist = _get_nselib_history(ticker, days=days)
    return hist


def get_company_info(ticker: str) -> dict:
    """
    Attempts to fetch company info using yfinance.
    Falls back to a constructed dict with nselib close price if yfinance fails.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Check if basic info actually exists
        if info and (info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")):
            return info
    except Exception as e:
        logger.warning(f"yfinance info failed for {ticker}: {e}")
        
    logger.info(f"Using nselib fallback for {ticker} info")
    
    info = {}
    info["longName"] = ticker.replace(".NS", "")
    
    # Try to get latest price from nselib (last 5 days to ensure we hit a trading day)
    hist = _get_nselib_history(ticker, days=5)
    if not hist.empty and "Close" in hist.columns:
        info["currentPrice"] = float(hist["Close"].iloc[-1])
        if len(hist) > 1:
            info["previousClose"] = float(hist["Close"].iloc[-2])
    
    return info
