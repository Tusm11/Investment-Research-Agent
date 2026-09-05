import os
import logging
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

# Suppress yfinance warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message="No data found*")
warnings.filterwarnings("ignore", message="possibly delisted*")

import yfinance as yf
import requests
import trafilatura
from dotenv import load_dotenv
from math import isnan

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


from agent_1.tools.recent_news import recent_news
from agent_1.tools.nifty50 import get_nifty50_data, NIFTY50

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared yfinance info cache — fetch .info once per ticker per process call
# ---------------------------------------------------------------------------
_INFO_CACHE: dict = {}


def _get_info(ticker: str) -> dict:
    """Fetch yfinance .info for a ticker, cached within this call."""
    if ticker not in _INFO_CACHE:
        try:
            _INFO_CACHE[ticker] = yf.Ticker(ticker).info or {}
        except Exception as e:
            logger.warning("yf.info failed for %s: %s", ticker, e)
            _INFO_CACHE[ticker] = {}
    return _INFO_CACHE[ticker]


def fetch_analyst_consensus(ticker, info: Optional[dict] = None):
    try:
        info = info or _get_info(ticker)
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        target = info.get("targetMeanPrice")
        upside = None
        if current and target:
            upside = round(((target - current) / current) * 100, 2)

        return {
            "status": "success",
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
            "target_mean_price": target,
            "current_price": current,
            "upside_downside_percent": upside,
            **_fetch_recommendation_counts(ticker),
            "source": "yahoo_finance",
        }
    except Exception as e:
        logger.warning("analyst consensus missing for %s: %s", ticker, e)
        return {
            "status": "retrieval_error",
            "error_reason": str(e),
            "recommendation_key": None,
            "number_of_analysts": None,
            "target_mean_price": None,
            "current_price": None,
            "upside_downside_percent": None,
            "buy": None,
            "hold": None,
            "sell": None,
        }


def _fetch_recommendation_counts(ticker):
    """Buy/hold/sell analyst counts from the latest yFinance recommendations summary.

    Returns counts of None (not 0) when unavailable so the UI can omit the
    breakdown instead of displaying a fake all-zero bar.
    """
    counts = {"buy": None, "hold": None, "sell": None}
    try:
        import yfinance as yf

        rec_trend = yf.Ticker(ticker).recommendations_summary
        if rec_trend is not None and not rec_trend.empty:
            latest = rec_trend.iloc[0]
            buy = int(latest.get("strongBuy", 0) or 0) + int(latest.get("buy", 0) or 0)
            hold = int(latest.get("hold", 0) or 0)
            sell = int(latest.get("sell", 0) or 0) + int(latest.get("strongSell", 0) or 0)
            if buy + hold + sell > 0:
                counts = {"buy": buy, "hold": hold, "sell": sell}
    except Exception as e:
        logger.warning("recommendation trend missing for %s: %s", ticker, e)
    return counts


def fetch_news_articles(ticker, days=180, max_articles=10):
    """Fetch news — capped at max_articles with a hard wall-clock timeout."""
    try:
        def _collect(news_data):
            return [{
                "date": item.get("date"),
                "title": item.get("headline"),
                "summary": item.get("summary"),
                "source": item.get("source", "web"),
                "url": item.get("url"),
            } for item in news_data.get("summary", [])]

        articles = _collect(recent_news(ticker, max_articles=max_articles))

        # Google RSS/scraping can fail transiently — retry once so a blip
        # doesn't return an empty set that then gets cached downstream
        if not articles:
            logger.warning("News fetch returned 0 articles for %s — retrying once", ticker)
            time.sleep(2)
            articles = _collect(recent_news(ticker, max_articles=max_articles))

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=days)
        
        # Return with status indicator
        return {
            "status": "success",
            "articles": articles,
            "article_count": len(articles),
            "date_range": {"start": str(start), "end": str(end)},
            "source": "recent_news_api",
        }
    except Exception as e:
        logger.warning("news fetch failed for %s: %s", ticker, e)
        return {
            "status": "retrieval_error",
            "error_reason": str(e),
            "articles": [],
            "article_count": 0,
            "date_range": {},
        }


def fetch_price_history(ticker, days=180):
    """Fetch OHLCV history with a single yf.download call; avoid duplicate .history() calls."""
    try:
        stock = yf.Ticker(ticker)
        # Single call covers both the rolling window and 52-week stats
        hist = stock.history(period="1y")

        if hist.empty:
            for period in ("2y",):
                hist = stock.history(period=period)
                if not hist.empty:
                    break
        if hist.empty:
            return {
                "status": "no_data",
                "error_reason": f"No price history found for {ticker}",
                "ohlcv": [],
                "week_52_high": None,
                "week_52_low": None,
                "average_volume": 0,
                "current_price": None,
            }

        hist = hist.reset_index()

        # For OHLCV, only keep the last `days` rows
        cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
        ohlcv = []
        week52_highs = []
        week52_lows = []

        for _, row in hist.iterrows():
            close = float(row["Close"]) if row["Close"] is not None else None
            open_ = float(row["Open"]) if row["Open"] is not None else None
            high = float(row["High"]) if row["High"] is not None else None
            low = float(row["Low"]) if row["Low"] is not None else None
            volume = row["Volume"]
            if any(v is None or (isinstance(v, float) and isnan(v)) for v in [open_, high, low, close]):
                logger.debug(f"Skipping row with NaN: {row['Date']}")
                continue

            # 52-week aggregates from full 1y data
            week52_highs.append(high)
            week52_lows.append(low)

            # Rolling window for OHLCV array
            row_date = row["Date"].date() if hasattr(row["Date"], "date") else row["Date"]
            if row_date >= cutoff:
                ohlcv.append({
                    "date": row["Date"].strftime("%Y-%m-%d"),
                    "open": round(open_, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": int(volume) if volume is not None else 0,
                })

        current_price = None
        if ohlcv:
            current_price = ohlcv[-1]["close"]

        if current_price is None:
            try:
                fast_info = getattr(stock, "fast_info", {})
                candidate = getattr(fast_info, "last_price", None) or (
                    fast_info.get("lastPrice") if hasattr(fast_info, "get") else None
                )
                if candidate is None:
                    info = _get_info(ticker)
                    candidate = info.get("currentPrice") or info.get("regularMarketPrice")
                if candidate is not None and not (isinstance(candidate, float) and isnan(candidate)):
                    current_price = round(float(candidate), 2)
            except Exception:
                pass

        return {
            "status": "success",
            "ohlcv": ohlcv,
            "week_52_high": round(max(week52_highs), 2) if week52_highs else None,
            "week_52_low": round(min(week52_lows), 2) if week52_lows else None,
            "average_volume": int(sum(r["volume"] for r in ohlcv) / len(ohlcv)) if ohlcv else 0,
            "current_price": current_price,
        }
    except Exception as e:
        logger.warning("price history missing for %s: %s", ticker, e)
        return {
            "status": "retrieval_error",
            "error_reason": str(e),
            "ohlcv": [],
            "week_52_high": None,
            "week_52_low": None,
            "average_volume": 0,
            "current_price": None,
        }


def calculate_market_correlation(ticker, ohlcv_data):
    """
    Calculate Pearson correlation between company daily returns and NIFTY 50 returns.
    
    Returns correlation coefficient (-1 to 1) with interpretation.
    """
    try:
        import numpy as np
        
        if not ohlcv_data or len(ohlcv_data) < 30:
            return {"correlation": None, "interpretation": "Insufficient data for correlation analysis"}
        
        # Get company daily returns
        closes = [bar["close"] for bar in ohlcv_data if bar.get("close")]
        if len(closes) < 30:
            return {"correlation": None, "interpretation": "Insufficient price data for correlation analysis"}
        
        # Calculate daily returns (percentage change)
        company_returns = []
        for i in range(1, len(closes)):
            if closes[i-1] > 0:
                ret = (closes[i] - closes[i-1]) / closes[i-1]
                company_returns.append(ret)
        
        if len(company_returns) < 20:
            return {"correlation": None, "interpretation": "Insufficient daily returns for correlation analysis"}
        
        # Fetch NIFTY 50 data for the same period
        try:
            nifty_hist = yf.Ticker("^NSEI").history(period="1y")
            if nifty_hist.empty or len(nifty_hist) < len(closes):
                return {"correlation": None, "interpretation": "Could not fetch NIFTY data for correlation"}
            
            nifty_hist = nifty_hist.reset_index()
            nifty_closes = [float(row["Close"]) for _, row in nifty_hist.iterrows() if row["Close"] is not None]
            
            # Align lengths - use same number of days
            min_len = min(len(nifty_closes), len(closes))
            nifty_closes = nifty_closes[-min_len:]
            
            # Calculate NIFTY daily returns
            nifty_returns = []
            for i in range(1, len(nifty_closes)):
                if nifty_closes[i-1] > 0:
                    ret = (nifty_closes[i] - nifty_closes[i-1]) / nifty_closes[i-1]
                    nifty_returns.append(ret)
            
            # Ensure same length for correlation calculation
            min_len = min(len(company_returns), len(nifty_returns))
            if min_len < 20:
                return {"correlation": None, "interpretation": "Insufficient overlapping data points"}
            
            company_returns = company_returns[-min_len:]
            nifty_returns = nifty_returns[-min_len:]
            
            # Calculate Pearson correlation
            corr_matrix = np.corrcoef(company_returns, nifty_returns)
            correlation = float(corr_matrix[0, 1])
            
            # Interpret correlation
            if correlation > 0.8:
                interpretation = "The stock has a strong positive relationship with NIFTY movements."
            elif correlation > 0.5:
                interpretation = "The stock shows moderate to strong correlation with NIFTY movements."
            elif correlation > 0.3:
                interpretation = "The stock shows moderate correlation with NIFTY movements."
            elif correlation > 0:
                interpretation = "The stock shows low positive correlation with NIFTY movements."
            elif correlation > -0.3:
                interpretation = "The stock shows low correlation with NIFTY movements."
            elif correlation > -0.5:
                interpretation = "The stock shows low negative correlation with NIFTY."
            else:
                interpretation = "The stock moves inversely to NIFTY movements."
            
            return {
                "correlation": round(correlation, 2),
                "interpretation": interpretation,
                "data_points": min_len
            }
            
        except Exception as e:
            logger.warning(f"NIFTY correlation fetch failed: {e}")
            return {"correlation": None, "interpretation": "Correlation analysis unavailable"}
            
    except Exception as e:
        logger.warning(f"Market correlation calculation failed: {e}")
        return {"correlation": None, "interpretation": "Correlation calculation error"}


def fetch_financial_metrics(ticker, info: Optional[dict] = None):
    try:
        info = info or _get_info(ticker)
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


def fetch_company_info(ticker, info: Optional[dict] = None):
    fallback = next((sector for symbol, sector in NIFTY50 if symbol == ticker), None)
    try:
        info = info or _get_info(ticker)
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


def fetch_company_website_context(ticker, max_pages=3):
    """Fetch a small amount of context from the company's own website when needed."""
    try:
        info = _get_info(ticker)
        website = info.get("website")
        if not website:
            return {"website": None, "pages": []}

        candidates = [website]
        lower = website.lower()
        for path in ["/investors", "/investor-relations", "/investor", "/businesses", "/about-us"]:
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
                resp = session.get(url, headers=headers, timeout=5)
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
    """Fetch broader market drivers — all ticker requests are parallelized."""
    try:
        stock = yf.Ticker(ticker)
        company = ticker.split(".")[0]
        info = _get_info(ticker)
        sector = (company_info or {}).get("sector") or info.get("sector")

        # Gather all symbols we need to fetch in parallel
        MACRO_SYMBOLS = {
            "nifty50_1mo":   ("^NSEI",    "1mo"),
            "nifty50_3mo":   ("^NSEI",    "3mo"),
            "banknifty_1mo": ("^NSEBANK", "1mo"),
            "banknifty_3mo": ("^NSEBANK", "3mo"),
            "usd_inr":       ("INR=X",    "latest"),
            "gold":          ("GC=F",     "latest"),
            "crude":         ("CL=F",     "latest"),
            "silver":        ("SI=F",     "latest"),
            "10y_treasury":  ("^TNX",     "latest"),
        }

        peers = [t for t, s in NIFTY50 if s == sector and t != ticker] if sector else []
        peer_symbols = peers[:5]  # limit peers to 5 to reduce requests

        def _fetch_hist(symbol, period):
            try:
                return yf.Ticker(symbol).history(period=period)
            except Exception:
                return None

        def _safe_return(symbol, period):
            hist = _fetch_hist(symbol, period)
            if hist is None or hist.empty or len(hist) < 2:
                return None
            start = float(hist["Close"].iloc[0])
            end = float(hist["Close"].iloc[-1])
            return round(((end - start) / start) * 100, 2) if start else None

        def _safe_latest(symbol):
            hist = _fetch_hist(symbol, "5d")
            if hist is None or hist.empty:
                return None
            return round(float(hist["Close"].iloc[-1]), 2)

        # Build a flat list of (key, fn) tasks
        tasks = {}
        for key, (sym, period) in MACRO_SYMBOLS.items():
            if period == "latest":
                tasks[key] = (lambda s=sym: _safe_latest(s))
            else:
                tasks[key] = (lambda s=sym, p=period: _safe_return(s, p))

        for peer in peer_symbols:
            tasks[f"peer_{peer}"] = (lambda p=peer: _safe_return(p, "1mo"))

        # Extra stock-level tasks
        def _get_calendar():
            try:
                cal = stock.calendar
                if hasattr(cal, "to_dict"):
                    return {k: v for k, v in cal.to_dict().items()}
            except Exception:
                pass
            return {}

        def _get_actions():
            try:
                act = stock.actions
                if hasattr(act, "tail") and not act.empty:
                    tail = act.tail(5).reset_index()
                    result = []
                    for _, row in tail.iterrows():
                        result.append({
                            "date": row.get("Date").strftime("%Y-%m-%d") if row.get("Date") is not None else "",
                            "dividends": float(row.get("Dividends", 0) or 0),
                            "stock_splits": float(row.get("Stock Splits", 0) or 0),
                        })
                    return result
            except Exception:
                pass
            return []

        def _get_holders():
            holders = {"major_holders": [], "institutional_holders": []}
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
            return holders

        tasks["__calendar__"] = _get_calendar
        tasks["__actions__"] = _get_actions
        tasks["__holders__"] = _get_holders

        # Execute all tasks in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=12) as executor:
            future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(future_to_key, timeout=25):
                key = future_to_key[future]
                try:
                    results[key] = future.result(timeout=5)
                except Exception as e:
                    logger.warning("market driver task %s failed: %s", key, e)
                    results[key] = None

        macro = {
            "nifty50_return_1mo":    results.get("nifty50_1mo"),
            "nifty50_return_3mo":    results.get("nifty50_3mo"),
            "banknifty_return_1mo":  results.get("banknifty_1mo"),
            "banknifty_return_3mo":  results.get("banknifty_3mo"),
            "usd_inr":               results.get("usd_inr"),
            "gold":                  results.get("gold"),
            "crude":                 results.get("crude"),
            "silver":                results.get("silver"),
            "10y_treasury":          results.get("10y_treasury"),
        }

        peer_returns = [results[f"peer_{p}"] for p in peer_symbols if results.get(f"peer_{p}") is not None]
        sector_return = round(sum(peer_returns) / len(peer_returns), 2) if peer_returns else None

        calendar = results.get("__calendar__") or {}
        actions = results.get("__actions__") or []
        holders = results.get("__holders__") or {"major_holders": [], "institutional_holders": []}

        return {
            "ticker": ticker,
            "sector": sector,
            "company": company,
            "macro": macro,
            "sector_performance": {
                "peer_count": len(peers),
                "sector_return_1mo": sector_return,
                "peer_sample_returns_1mo": peer_returns[:5],
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


def fetch_all_data(ticker, days=180, include_nifty50=False, news_limit=10):
    """
    Fetch all stock data in parallel.

    Strategy
    --------
    1. A single yfinance `.info` call is shared across all sub-fetchers via _INFO_CACHE.
    2. All independent fetchers (news, price_history, financials, analyst,
       company_info, market_drivers) run concurrently in a thread pool.
    3. Hard 55-second wall-clock budget — anything still running is cancelled
       and a partial result is returned so the pipeline never exceeds 60 s.
    """
    fetch_timestamp = datetime.now(timezone.utc).isoformat()

    # Reset per-call cache so a fresh run always gets live data
    _INFO_CACHE.clear()

    # Pre-warm the shared info cache in the main thread before spawning workers
    shared_info = _get_info(ticker)

    def _news():
        return fetch_news_articles(ticker, days=days, max_articles=news_limit)

    def _price():
        return fetch_price_history(ticker, days=days)

    def _financials():
        return fetch_financial_metrics(ticker, info=shared_info)

    def _analyst():
        return fetch_analyst_consensus(ticker, info=shared_info)

    def _company():
        return fetch_company_info(ticker, info=shared_info)

    def _market():
        return fetch_market_drivers(ticker, company_info=None)

    job_map = {
        "news":           _news,
        "price_history":  _price,
        "financials":     _financials,
        "analyst_data":   _analyst,
        "company_info":   _company,
        "market_drivers": _market,
    }

    results = {k: {} for k in job_map}

    TOTAL_BUDGET_SECONDS = 55  # leave 5 s buffer for the caller

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in job_map.items()}
        try:
            for future in as_completed(future_to_key, timeout=TOTAL_BUDGET_SECONDS):
                key = future_to_key[future]
                try:
                    results[key] = future.result(timeout=5)
                except Exception as e:
                    logger.warning("fetch_all_data task '%s' failed: %s", key, e)
                    # Mark task as failed instead of silent empty dict
                    results[key] = {
                        "status": "retrieval_error",
                        "error_reason": str(e),
                    }
        except FuturesTimeoutError:
            logger.warning("fetch_all_data hit %ds budget — returning partial data", TOTAL_BUDGET_SECONDS)
            # Collect whatever finished
            for future, key in future_to_key.items():
                if future.done() and not future.cancelled():
                    try:
                        results[key] = future.result()
                    except Exception as e:
                        results[key] = {
                            "status": "retrieval_error",
                            "error_reason": f"Timeout or error: {e}",
                        }
                else:
                    # Mark cancelled tasks as timed out
                    results[key] = {
                        "status": "timeout",
                        "error_reason": f"Task cancelled - exceeded {TOTAL_BUDGET_SECONDS}s budget",
                    }

    payload = {
        "ticker": ticker,
        "fetch_timestamp": fetch_timestamp,
        "news": results["news"],
        "price_history": results["price_history"],
        "analyst_data": results["analyst_data"],
        "company_info": results["company_info"],
        "market_drivers": results["market_drivers"],
    }

    if include_nifty50:
        payload["nifty50"] = get_nifty50_data()

    return payload


if __name__ == "__main__":
    import json
    import time
    logging.basicConfig(level=logging.INFO)
    t0 = time.time()
    data = fetch_all_data("RELIANCE.NS", days=30)
    elapsed = time.time() - t0
    print(f"\n✅ Fetched in {elapsed:.1f}s")
    print(json.dumps(data, indent=2, default=str))
