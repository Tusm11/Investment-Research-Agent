import os
import logging
from datetime import datetime,timezone,timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import yfinance as yf
import requests
import trafilatura
from dotenv import load_dotenv
from math import isnan

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def _prepare_network():
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY"):
        os.environ.pop(key, None)
        os.environ.pop(key.lower(), None)

    cache_dir = Path(os.getenv("TEMP", ".")) / "py-yfinance-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


_prepare_network()

from agent_1.tools.recent_news import recent_news
from agent_1.tools.nifty50 import get_nifty50_data, NIFTY50

logger = logging.getLogger(__name__)


def fetch_analyst_consensus(ticker):
    try:
        info = yf.Ticker(ticker).info
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        target = info.get("targetMeanPrice")
        upside = None
        if current and target:
            upside = round(((target - current) / current) * 100, 2)

        return {
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
            "target_mean_price": target,
            "current_price": current,
            "upside_downside_percent": upside,
        }
    except Exception as e:
        logger.warning("analyst consensus missing for %s: %s", ticker, e)
        return {}


def fetch_news_articles(ticker, days=180, max_articles=20):
    try:
        from agent_1.tools.recent_news import recent_news
        news_data = recent_news(ticker, max_articles=max_articles)
        
        articles = []
        for item in news_data.get("summary", []):
            articles.append({
                "date": item.get("date"),
                "title": item.get("headline"),
                "summary": item.get("summary"),
                "source": item.get("source", "web"),
                "url": item.get("url"),
            })

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)
        return {
            "articles": articles,
            "article_count": len(articles),
            "date_range": {"start": str(start), "end": str(end)},
        }
    except Exception as e:
        logger.warning("news fetch failed for %s: %s", ticker, e)
        return {"articles": [], "article_count": 0, "date_range": {}}


def fetch_price_history(ticker, days=180):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{days}d")
        if hist.empty:
            for period in ("90d", "1y", "2y"):
                hist = stock.history(period=period)
                if not hist.empty:
                    break
        if hist.empty:
            return {}

        hist = hist.reset_index()
        ohlcv = []
        for _, row in hist.iterrows():
            close = float(row["Close"]) if row["Close"] is not None else None
            open_ = float(row["Open"]) if row["Open"] is not None else None
            high = float(row["High"]) if row["High"] is not None else None
            low = float(row["Low"]) if row["Low"] is not None else None
            volume = row["Volume"]
            if any(v is None or (isinstance(v, float) and isnan(v)) for v in [open_, high, low, close]):
                continue
            ohlcv.append({
                "date": row["Date"].strftime("%Y-%m-%d"),
                "open": round(open_, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": int(volume) if volume is not None else 0,
            })

        year_hist = stock.history(period="1y")
        current_price = None
        if not hist.empty:
            last_close = hist["Close"].iloc[-1]
            if last_close is not None and not (isinstance(last_close, float) and isnan(last_close)):
                current_price = round(float(last_close), 2)
        if current_price is None:
            try:
                fast_info = getattr(stock, "fast_info", {}) or {}
                candidate = (
                    fast_info.get("lastPrice")
                    if hasattr(fast_info, "get")
                    else None
                )
                if candidate is None:
                    candidate = getattr(stock, "info", {}).get("currentPrice") or getattr(stock, "info", {}).get("regularMarketPrice")
                if candidate is not None and not (isinstance(candidate, float) and isnan(candidate)):
                    current_price = round(float(candidate), 2)
            except Exception:
                pass
        return {
            "ohlcv": ohlcv,
            "week_52_high": round(float(year_hist["High"].max()), 2) if not year_hist.empty else None,
            "week_52_low": round(float(year_hist["Low"].min()), 2) if not year_hist.empty else None,
            "average_volume": int(hist["Volume"].mean()),
            "current_price": current_price,
        }
    except Exception as e:
        logger.warning("price history missing for %s: %s", ticker, e)
        return {}


def fetch_financial_metrics(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "returnOnEquity": info.get("returnOnEquity"),
            "operatingMargins": info.get("operatingMargins"),
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "revenueGrowth": info.get("revenueGrowth"),
            "freeCashflow": info.get("freeCashflow"),
            "totalRevenue": info.get("totalRevenue"),
        }
    except Exception as e:
        logger.warning("financial metrics missing for %s: %s", ticker, e)
        return {}


def fetch_company_info(ticker):
    fallback = next((sector for symbol, sector in NIFTY50 if symbol == ticker), None)
    try:
        info = yf.Ticker(ticker).info
        return {
            "company_name": info.get("longName"),
            "sector": info.get("sector") or fallback,
            "industry": info.get("industry"),
            "business_summary": info.get("longBusinessSummary"),
            "employees": info.get("fullTimeEmployees"),
            "website": info.get("website"),
            "marketCap": info.get("marketCap"),
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
            "regularMarketPrice": info.get("regularMarketPrice"),
            "regularMarketPreviousClose": info.get("regularMarketPreviousClose"),
            "previousClose": info.get("previousClose"),
            "trailingPE": info.get("trailingPE"),
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "dividendYield": info.get("dividendYield"),
            "dayHigh": info.get("dayHigh"),
            "dayLow": info.get("dayLow"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
            "beta": info.get("beta"),
            "earningsDate": info.get("earningsDate"),
            "exDividendDate": info.get("exDividendDate"),
            "dividendRate": info.get("dividendRate"),
            "sharesOutstanding": info.get("sharesOutstanding"),
            "floatShares": info.get("floatShares"),
            "heldPercentInsiders": info.get("heldPercentInsiders"),
            "heldPercentInstitutions": info.get("heldPercentInstitutions"),
            "fundFamily": info.get("fundFamily"),
        }
    except Exception as e:
        logger.warning("company info missing for %s: %s", ticker, e)
        return {
            "company_name": ticker,
            "sector": fallback,
            "industry": None,
            "business_summary": None,
            "employees": None,
            "website": None,
            "marketCap": None,
            "currentPrice": None,
            "regularMarketPrice": None,
            "regularMarketPreviousClose": None,
            "previousClose": None,
            "trailingPE": None,
            "debtToEquity": None,
            "currentRatio": None,
            "dividendYield": None,
            "dayHigh": None,
            "dayLow": None,
            "open": None,
            "fiftyTwoWeekHigh": None,
            "fiftyTwoWeekLow": None,
            "beta": None,
            "earningsDate": None,
            "exDividendDate": None,
            "dividendRate": None,
            "sharesOutstanding": None,
            "floatShares": None,
            "heldPercentInsiders": None,
            "heldPercentInstitutions": None,
            "fundFamily": None,
        }


def fetch_company_website_context(ticker, max_pages=4):
    """Fetch a small amount of context from the company's own website when needed."""
    try:
        info = fetch_company_info(ticker)
        website = info.get("website")
        if not website:
            return {"website": None, "pages": []}

        candidates = [website]
        lower = website.lower()
        for path in ["/investors", "/investor-relations", "/investor", "/businesses", "/about-us", "/our-businesses", "/segments"]:
            if path not in lower:
                candidates.append(urljoin(website.rstrip("/") + "/", path.lstrip("/")))

        seen = set()
        pages = []
        session = requests.Session()
        session.trust_env = False
        headers = {"User-Agent": "Mozilla/5.0"}

        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            if len(pages) >= max_pages:
                break
            try:
                resp = session.get(url, headers=headers, timeout=6)
                if resp.status_code != 200:
                    continue
                html = resp.text
                text = trafilatura.extract(html) or ""
                text = " ".join(text.split())
                if not text:
                    continue
                pages.append({
                    "url": url,
                    "text": text[:2500],
                })
            except Exception:
                continue

        return {
            "website": website,
            "pages": pages,
        }
    except Exception as e:
        logger.warning("website context missing for %s: %s", ticker, e)
        return {"website": None, "pages": []}


def fetch_market_drivers(ticker, company_info=None):
    """Fetch broader market drivers for a company and its sector."""
    try:
        stock = yf.Ticker(ticker)
        company = ticker.split(".")[0]
        info = company_info or fetch_company_info(ticker)
        sector = info.get("sector")

        def _safe_latest(symbol):
            try:
                hist = yf.Ticker(symbol).history(period="1mo")
                if hist.empty:
                    return None
                return round(float(hist["Close"].iloc[-1]), 2)
            except Exception:
                return None

        def _safe_return(symbol, period="1mo"):
            try:
                hist = yf.Ticker(symbol).history(period=period)
                if hist.empty or len(hist) < 2:
                    return None
                start = float(hist["Close"].iloc[0])
                end = float(hist["Close"].iloc[-1])
                return round(((end - start) / start) * 100, 2) if start else None
            except Exception:
                return None

        peers = [t for t, s in NIFTY50 if s == sector and t != ticker] if sector else []
        peer_returns = []
        for peer in peers[:6]:
            ret = _safe_return(peer, "1mo")
            if ret is not None:
                peer_returns.append(ret)

        sector_return = round(sum(peer_returns) / len(peer_returns), 2) if peer_returns else None

        calendar = {}
        try:
            cal = stock.calendar
            if hasattr(cal, "to_dict"):
                calendar = {k: v for k, v in cal.to_dict().items()}
        except Exception:
            calendar = {}

        actions = []
        try:
            act = stock.actions
            if hasattr(act, "tail") and not act.empty:
                tail = act.tail(5).reset_index()
                for _, row in tail.iterrows():
                    actions.append({
                        "date": row.get("Date").strftime("%Y-%m-%d") if row.get("Date") is not None else "",
                        "dividends": float(row.get("Dividends", 0) or 0),
                        "stock_splits": float(row.get("Stock Splits", 0) or 0),
                    })
        except Exception:
            actions = []

        holders = {
            "major_holders": [],
            "institutional_holders": [],
        }
        try:
            mh = stock.major_holders
            if hasattr(mh, "to_dict"):
                holders["major_holders"] = mh.to_dict()
        except Exception:
            pass
        try:
            ih = stock.institutional_holders
            if hasattr(ih, "head") and not ih.empty:
                holders["institutional_holders"] = ih.head(5).to_dict(orient="records")
        except Exception:
            pass

        macro = {
            "nifty50_return_1mo": _safe_return("^NSEI", "1mo"),
            "nifty50_return_3mo": _safe_return("^NSEI", "3mo"),
            "banknifty_return_1mo": _safe_return("^NSEBANK", "1mo"),
            "banknifty_return_3mo": _safe_return("^NSEBANK", "3mo"),
            "usd_inr": _safe_latest("INR=X"),
            "gold": _safe_latest("GC=F"),
            "crude": _safe_latest("CL=F"),
            "silver": _safe_latest("SI=F"),
            "10y_treasury": _safe_latest("^TNX"),
        }

        return {
            "ticker": ticker,
            "sector": sector,
            "company": company,
            "macro": macro,
            "sector_performance": {
                "peer_count": len(peers),
                "sector_return_1mo": sector_return,
                "peer_sample_returns_1mo": peer_returns[:6],
            },
            "earnings": {
                "calendar": calendar,
                "earnings_date": str(info.get("earningsDate") or ""),
            },
            "corporate_actions": {
                "recent_actions": actions,
                "dividend_rate": info.get("dividendRate"),
                "ex_dividend_date": str(info.get("exDividendDate") or ""),
            },
            "promoter_activity": {
                "held_percent_insiders": info.get("heldPercentInsiders"),
                "held_percent_institutions": info.get("heldPercentInstitutions"),
                "major_holders": holders.get("major_holders", []),
                "institutional_holders": holders.get("institutional_holders", []),
            },
        }
    except Exception as e:
        logger.warning("market drivers missing for %s: %s", ticker, e)
        return {
            "ticker": ticker,
            "sector": None,
            "company": ticker,
            "macro": {},
            "sector_performance": {},
            "earnings": {},
            "corporate_actions": {},
            "promoter_activity": {},
        }


def fetch_all_data(ticker, days=180, include_nifty50=False, news_limit=20):
    fetch_timestamp = datetime.now(timezone.utc).isoformat()

    news_articles = fetch_news_articles(ticker, days=days, max_articles=news_limit)
    price_history = fetch_price_history(ticker, days=days)
    financials = fetch_financial_metrics(ticker)
    analyst_data = fetch_analyst_consensus(ticker)
    company_info = fetch_company_info(ticker)
    market_drivers = fetch_market_drivers(ticker, company_info=company_info)

    payload = {
        "ticker": ticker,
        "fetch_timestamp": fetch_timestamp,
        "news": news_articles,
        "price_history": price_history,
        "analyst_data": analyst_data,
        "company_info": company_info,
        "market_drivers": market_drivers,
    }

    if include_nifty50:
        payload["nifty50"] = get_nifty50_data()

    return payload


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    data = fetch_all_data("RELIANCE.NS", days=30)
    print(json.dumps(data, indent=2, default=str))
