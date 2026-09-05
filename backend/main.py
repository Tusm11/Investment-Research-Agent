import sys
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
import json
import sys
import math
from math import isnan
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import run_pipeline
from agent_1.tools.nifty50 import NIFTY50

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper to sanitize float values
def safe_float(val, default=None):
    """Convert to float, return default if NaN/Inf."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError):
        return default

# Custom JSON encoder for NaN/Infinity values
class SafeJSONEncoder(json.JSONEncoder):
    def encode(self, o):
        if isinstance(o, float):
            if o != o:  # NaN
                return '0.0'
            elif o == float('inf'):
                return '999999.0'
            elif o == float('-inf'):
                return '-999999.0'
        return super().encode(o)

    def iterencode(self, o, _one_shot=False):
        for chunk in super().iterencode(o, _one_shot):
            yield chunk


def sanitize_json(obj):
    """Recursively replace NaN/Infinity floats so the payload is JSON-compliant."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse that never emits NaN/Infinity (Starlette dumps with allow_nan=False)."""
    def render(self, content) -> bytes:
        return json.dumps(
            sanitize_json(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(title="Stock Market Research Agent API", json_encoder=SafeJSONEncoder, default_response_class=SafeJSONResponse)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

import company_memory

class ChatRequest(BaseModel):
    symbol: str
    question: str
    tab: str = None       # which tab the user is viewing
    context: str = None   # digest of the data currently rendered on that tab

class ChatResponse(BaseModel):
    answer: str

class CompanyResearchRequest(BaseModel):
    name: str
    ticker: str
    days: int = 180
    chat_query: str = None  # Optional chat question

@app.post("/api/company-research")
async def company_research(request: CompanyResearchRequest):
    """Company-specific research endpoint for frontend."""
    try:
        from agent_1.data_fetcher import fetch_all_data
        from agent_2.agent import run_agent2
        from agent_3.agent import run_agent3
        from agent_4.agent import run_agent4
        from company_context import CompanyContext, validate_company_data
        try:
            from backend.sector_metrics import get_sector_metrics
        except ImportError:
            from sector_metrics import get_sector_metrics
        
        name = request.name
        ticker = request.ticker
        days = request.days
        
        # PHASE 1: Validate company context
        try:
            company_ctx = CompanyContext(ticker=ticker, name=name)
        except ValueError as e:
            logger.error(f"Invalid company context: {e}")
            return {
                "success": False,
                "error": f"Invalid company identifier: {str(e)}",
                "ticker": ticker,
            }
        
        logger.info(f"Starting research for: {company_ctx}")
        
        # Run pipeline first to get data
        result = run_pipeline(f"Analyze {name}", ticker=company_ctx.ticker, days=days)
        
        # Check for pipeline-level errors
        if result.get("error"):
            logger.error(f"Pipeline error for {company_ctx.ticker}: {result.get('error')}")
            return {
                "success": False,
                "error": f"Data retrieval failed: {result.get('error')}",
                "ticker": company_ctx.ticker,
            }
        
        agent1_output = result.get("agent1_output") or {}
        agent2_output = result.get("agent2_output") or {}
        agent3_output = result.get("agent3_output") or {}
        agent4_output = result.get("agent4_output") or {}
        
        # PHASE 2: Validate data integrity for the requested company
        validation = validate_company_data(company_ctx, agent1_output)
        if validation["status"] == "mismatch":
            logger.error(f"Company data mismatch for {company_ctx.ticker}: {validation['issues']}")
            return {
                "success": False,
                "error": "Data mismatch: received data does not match requested company",
                "ticker": company_ctx.ticker,
                "validation_issues": validation["issues"],
            }
        
        # Build memory
        memory = company_memory.build_company_memory(
            agent1_output, agent2_output, agent3_output
        )
        
        # Extract company info
        info = memory.get("company_info", {})
        current_price = memory.get("price_data", {}).get("current")
        
        # PHASE 3: Validate required fields exist
        if not info.get("name"):
            logger.warning(f"Missing company name for {company_ctx.ticker}")
            info["name"] = name
        if not info.get("ticker"):
            info["ticker"] = company_ctx.ticker
        
        # Detect sector for metrics selection (after we have company info)
        sector_info = get_sector_metrics(name, info.get("sector"))
        
        target_price = agent4_output.get("target_price")
        expected_return = None
        if target_price and current_price:
            expected_return = ((target_price - current_price) / current_price) * 100
        
        # Calculate price change from price history
        price_change = 0.0
        ohlcv = memory.get("price_data", {}).get("ohlcv", [])
        if len(ohlcv) >= 2 and current_price:
            prev_close = ohlcv[-2].get("close")
            if prev_close:
                price_change = ((current_price - prev_close) / prev_close) * 100
        
        # Get sentiment score from AI analysis
        market_mood = memory.get("dashboard", {}).get("market_mood", {})
        sentiment_status = agent3_output.get("sentiment")
        
        # IMPORTANT: Only set sentiment score if sentiment analysis actually ran
        if sentiment_status:
            sentiment_score = 75 if sentiment_status == "Bullish" else 25 if sentiment_status == "Bearish" else 50
        else:
            # Sentiment analysis did not run - indicate unavailable instead of defaulting to 50
            sentiment_score = None
        
        from datetime import datetime
        import time
        
        # Timestamp for this request
        fetch_time = datetime.utcnow().isoformat() + "Z"
        
        response_data = {
            "success": True,
            "company_name": info.get("name", name),
            "ticker": info.get("ticker", ticker),
            "price": current_price,
            "price_change": price_change,
            "market_cap": memory.get("market_stats", {}).get("market_cap"),
            "pe_ratio": memory.get("market_stats", {}).get("pe_ratio"),
            "dividend_yield": info.get("dividend_yield"),
            "industry": info.get("industry", ""),
            "high_52w": memory.get("price_data", {}).get("high_52w"),
            "low_52w": memory.get("price_data", {}).get("low_52w"),
            "sector": info.get("sector", "N/A"),
            "summary": info.get("summary", ""),
            "price_history": memory.get("price_data", {}).get("ohlcv", []),
            "dashboard": memory.get("dashboard", {}),
            "analyst_data": memory.get("analyst_data", {}),
            "news_articles": memory.get("news_articles", [])[:5],
            "risks": memory.get("risks", [])[:5],
            "opportunities": memory.get("opportunities", [])[:5],
            "sentiment_score": sentiment_score,
            # Data source indicators
            "_data_quality": {
                "price_available": current_price is not None,
                "news_available": len(memory.get("news_articles", [])) > 0,
                "sentiment_analyzed": sentiment_score is not None,
                "risks_identified": len(memory.get("risks", [])) > 0,
                "peer_data_available": len(agent2_output.get("peer_comparison", {}).get("peers", [])) > 0,
                "analysis_errors": agent1_output.get("_analysis_errors", []),
            },
            # Data sources with timestamps
            "_data_sources": {
                "fetched_at": fetch_time,
                "price_data": {
                    "source": "yfinance",
                    "available": current_price is not None,
                    "timestamp": agent1_output.get("price_history", {}).get("timestamp"),
                },
                "news": {
                    "source": "NewsAPI + fallback",
                    "available": len(memory.get("news_articles", [])) > 0,
                    "count": len(memory.get("news_articles", [])),
                    "timestamp": agent1_output.get("news_articles", {}).get("timestamp"),
                },
                "analyst_consensus": {
                    "source": "yfinance targets",
                    "available": len(memory.get("analyst_data", {})) > 0,
                    "timestamp": agent1_output.get("analyst_consensus", {}).get("timestamp"),
                },
                "fundamentals": {
                    "source": "yfinance",
                    "available": len(agent2_output.get("red_flags", [])) > 0,
                    "timestamp": agent2_output.get("timestamp"),
                },
                "sentiment": {
                    "source": "AI analysis (Groq)",
                    "available": sentiment_score is not None,
                    "timestamp": agent3_output.get("timestamp"),
                },
                "risk_model": {
                    "source": "Isolation Forest",
                    "available": agent2_output.get("risk_level") is not None,
                    "timestamp": agent2_output.get("model_timestamp"),
                },
            },
            # Sector-aware metrics
            "sector_metrics": sector_info,
            # Agent 2 data
            "agent2": {
                "market_mood": market_mood,
                "important_events": memory.get("events", [])[:5],
                "key_events": memory.get("news_articles", [])[:3],
                "news_articles": memory.get("news_articles", [])[:5],
                "broader_drivers": {},
            },
            # Agent 3 data
            "agent3": {
                "overall_risk": agent2_output.get("risk_level", "Moderate"),
                "financial_observations": agent2_output.get("red_flags", [])[:5],
                "isolation_forest": agent2_output.get("model_assessment", {}),
                "statistical_findings": [f.get("explanation", str(f)) for f in agent2_output.get("red_flags", [])][:5],
                "peer_comparison": agent2_output.get("peer_comparison", {}).get("peers", [])[:5],
            },
            # Agent 4 forecast
            "price_forecast": {
                "current_price": current_price,
                "predicted_price": target_price,
                "expected_return": expected_return,
                "direction": agent4_output.get("consensus_rating", "Hold"),
                "basis": "Fundamental health analysis"
            },
        }
        
        # Handle chat query using RAG if provided
        if request.chat_query:
            from rag_assistant import rag_chat
            # CRITICAL: Pass ticker to ensure RAG knows which company to discuss
            rag_response = rag_chat(
                request.chat_query, 
                memory, 
                agent2_output,
                ticker=company_ctx.ticker  # ← Pass canonical ticker
            )
            response_data["agent4"] = {
                "response": rag_response.get("response", "I couldn't generate a response."),
                "status": rag_response.get("status", "unknown"),
                "company": rag_response.get("company"),
            }
        
        logger.info(f"Company research: {ticker} - success")
        return response_data
        
    except Exception as e:
        logger.error(f"Company research failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

    symbol: str
    question: str

class ChatResponse(BaseModel):
    answer: str

@app.get("/api/nifty50")
async def get_nifty50_dashboard():
    """Dashboard: NIFTY index, indicators, gainers/losers, sectors, companies, chart series."""
    import yfinance as yf

    # 5-minute cache — the payload takes ~30-60s to build fresh
    if _NIFTY50_CACHE["data"] is not None and (time.time() - _NIFTY50_CACHE["ts"]) < _NIFTY50_TTL:
        return _NIFTY50_CACHE["data"]

    try:
        # Fetch NIFTY 50 index (5d window; dropna so a NaN "today" row can't become the close)
        nifty = yf.Ticker("^NSEI")
        hist = nifty.history(period="5d").dropna(subset=["Close"])

        if hist.empty:
            return {"error": "Could not fetch NIFTY data"}
        
        latest = hist.iloc[-1]
        price = float(latest["Close"])
        prev_close = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else price
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
        
        # Fetch individual stocks in parallel
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        companies = []
        gainers = []
        losers = []
        
        def fetch_stock_data(symbol):
            """Fetch one stock's data: price, change, P/E."""
            try:
                stock = yf.Ticker(symbol)
                data = stock.history(period="5d").dropna(subset=["Close"])
                if not data.empty:
                    close = safe_float(float(data.iloc[-1]["Close"]))
                    if close is None:
                        logger.warning(f"No valid close price for {symbol}, skipping")
                        return None
                    prev = safe_float(float(data.iloc[-2]["Close"])) if len(data) > 1 else close
                    chg = ((close - prev) / prev * 100) if prev and prev != 0 else 0
                    chg = safe_float(chg, 0)
                    
                    return {
                        "ticker": symbol,
                        "symbol": symbol,
                        "name": stock.info.get("longName", symbol),
                        "price": close,
                        "change": chg,
                        "pe_ratio": safe_float(stock.info.get("trailingPE")),
                        "predicted_price": None,
                        "expected_return": None
                    }
            except Exception as e:
                logger.warning(f"Stock fetch failed for {symbol}: {e}")
            return None
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(fetch_stock_data, symbol): symbol for symbol, _ in NIFTY50[:50]}
            for future in as_completed(futures):
                company = future.result()
                if company:
                    companies.append(company)
                    if company["change"] > 0:
                        gainers.append(company)
                    else:
                        losers.append(company)
        
        gainers.sort(key=lambda x: x["change"], reverse=True)
        losers.sort(key=lambda x: x["change"])
        
        adv = len([c for c in companies if c["change"] > 0])
        dec = len([c for c in companies if c["change"] < 0])
        ad_ratio = adv / dec if dec > 0 else 0
        
        sector_map = {t: s for t, s in NIFTY50}
        sector_returns = {}
        for c in companies:
            ticker = c["ticker"]
            sector = sector_map.get(ticker, "Other")
            if sector not in sector_returns:
                sector_returns[sector] = []
            sector_returns[sector].append(c["change"])
        
        sector_performance = [
            {"name": s, "change": safe_float(sum(returns) / len(returns) if returns else 0, 0)}
            for s, returns in sorted(sector_returns.items())
        ]
        
        # Attach cached ML forecasts to the most-moved companies
        _enrich_with_predictions(companies)

        logger.info(f"Dashboard response: {len(companies)} companies, {len(gainers)} gainers, {len(losers)} losers")

        # Market-wide stock news (Google News RSS) for the dashboard news card
        try:
            from agent_1.tools.recent_news import fetch_google_news_links
            raw_news = fetch_google_news_links("Nifty 50 Sensex stock market", max_articles=8)
            market_news = []
            for item in raw_news:
                # Google RSS titles end with " - Publisher" — use that as the source
                parts = (item.get("title") or "").rsplit(" - ", 1)
                headline = parts[0]
                source = parts[1] if len(parts) > 1 else (_readable_source(item.get("link") or "") if item.get("link") else "Google News")
                market_news.append({"headline": headline, "url": item.get("link") or "", "source": source})
        except Exception as e:
            logger.warning(f"Market news fetch failed: {e}")
            market_news = []

        # Chart series: 5y daily + 5d intraday for the dashboard graph
        try:
            daily_hist = nifty.history(period="5y")
            intraday_hist = nifty.history(period="5d", interval="5m")
            chart_series = {
                "history": _to_bars(daily_hist),
                "intraday": _to_bars(intraday_hist, max_rows=600),
            }
        except Exception as e:
            logger.warning(f"Chart series fetch failed: {e}")
            chart_series = {"history": [], "intraday": []}

        response = {
            "nifty_price": safe_float(price),
            "nifty_change": safe_float(change_pct),
            "prev_close": safe_float(prev_close),
            "day_high": safe_float(float(latest["High"]), price),
            "day_low": safe_float(float(latest["Low"]), price),
            "advancing_stocks": adv,
            "declining_stocks": dec,
            "ad_ratio": safe_float(ad_ratio),
            "avg_return": safe_float(sum(c["change"] for c in companies) / len(companies) if companies else 0),
            "total_turnover": 5000,
            "top_gainers": gainers[:5],
            "top_losers": losers[:5],
            "sector_performance": sector_performance,
            "companies": companies,
            "chart_series": chart_series,
            "market_news": market_news,
        }
        _NIFTY50_CACHE["data"] = response
        _NIFTY50_CACHE["ts"] = time.time()
        return response

    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return {"error": str(e)}

@app.get("/api/companies")
async def get_companies():
    """Company list for the research dropdown. Frontend expects {success, companies:[{name, ticker}]}."""
    try:
        companies = [
            {"name": ticker.split(".")[0].replace("-", " "), "ticker": ticker}
            for ticker, _ in NIFTY50
        ]
        return {"success": True, "companies": companies}
    except Exception as e:
        logger.error(f"get_companies failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


_DASHBOARD_CACHE = {"ts": 0.0, "data": None}
_DASHBOARD_TTL = 300  # seconds

_PREDICTION_CACHE = {}  # ticker -> {"ts": float, "pred": dict}
_PREDICTION_TTL = 900   # 15 minutes
_PREDICTIONS_PER_REQUEST = 50

_NIFTY50_CACHE = {"ts": 0.0, "data": None}
_NIFTY50_TTL = 300  # seconds


def _to_bars(df, max_rows=None):
    """DataFrame -> [{date, close}] with NaN rows dropped."""
    bars = []
    for idx, row in df.iterrows():
        close = safe_float(float(row["Close"]))
        if close is None:
            continue
        date = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
        bars.append({"date": date, "close": close})
    return bars[-max_rows:] if max_rows else bars


def _enrich_with_predictions(companies):
    """Attach XGBoost predictions to companies (cached; newest entries first). Fallback to simple forecast if ML unavailable."""
    import time
    try:
        from prediction_service import get_prediction_service
        svc = get_prediction_service()
        if not svc.is_available():
            svc = None
    except:
        svc = None
    
    # Enriching with ML predictions
    if svc and svc.is_available():
        by_change = sorted(companies, key=lambda c: c.get("change") or 0, reverse=True)
        picked = []
        for c in by_change:
            if len(picked) >= _PREDICTIONS_PER_REQUEST:
                break
            ticker, price = c.get("ticker"), c.get("price")
            if not ticker or not price:
                continue
            cached = _PREDICTION_CACHE.get(ticker)
            if cached and (time.time() - cached["ts"]) < _PREDICTION_TTL:
                pred = cached["pred"]
            else:
                try:
                    pred = svc.predict_single_company(ticker, float(price))
                    pred["company"] = c.get("name") or ticker
                    _PREDICTION_CACHE[ticker] = {"ts": time.time(), "pred": pred}
                except Exception as e:
                    logger.warning(f"Prediction failed for {ticker}: {e}")
                    continue
            c["predicted_price"] = pred.get("predicted_price")
            c["expected_return"] = pred.get("expected_return")
            picked.append(c)
    
    # Fallback: For companies without ML prediction, use simple forecast
    # Forecast = Current Price * (1 + 0.05) if sentiment is positive, else * (1 - 0.03)
    for c in companies:
        if c.get("predicted_price") is None and c.get("price"):
            # Simple heuristic: if gaining, forecast 5% up; if losing, forecast 3% down
            change = c.get("change", 0)
            if change > 0:
                # Positive momentum - forecast 5% upside
                c["predicted_price"] = c["price"] * 1.05
                c["expected_return"] = 5.0
            else:
                # Negative or flat - forecast conservative 3% downside or neutral
                c["predicted_price"] = c["price"] * 0.97
                c["expected_return"] = -3.0


def _build_dashboard_data():
    """Assemble the payload shape expected by script.js loadDashboard()."""
    import yfinance as yf
    from datetime import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # NIFTY index series (chart + price bar) — 5y so every timeframe has real data
    nifty = yf.Ticker("^NSEI")
    daily_hist = nifty.history(period="5y")
    intraday_hist = nifty.history(period="5d", interval="5m")

    index = {"history": _to_bars(daily_hist), "intraday": _to_bars(intraday_hist, max_rows=600)}
    if not daily_hist.empty:
        closes = [c for c in (safe_float(float(v)) for v in daily_hist["Close"]) if c is not None]
        if closes:
            index["current_price"] = closes[-1]
            index["prev_close"] = closes[-2] if len(closes) > 1 else closes[-1]
            if index["prev_close"]:
                index["change_pct"] = (closes[-1] - index["prev_close"]) / index["prev_close"] * 100

    def fetch_stock(symbol):
        try:
            hist = yf.Ticker(symbol).history(period="1y")
            if hist.empty:
                return None
            closes = [c for c in (safe_float(float(v)) for v in hist["Close"]) if c is not None]
            if not closes:
                return None
            close = closes[-1]
            prev = closes[-2] if len(closes) > 1 else close
            chg = safe_float((close - prev) / prev * 100, 0) if prev else 0
            short = symbol.split(".")[0]
            volume = safe_float(float(hist["Volume"].iloc[-1])) if not hist["Volume"].empty else None
            return {
                "ticker": symbol,
                "symbol": short,
                "name": short,
                "company": short.replace("-", " "),
                "price": close,
                "change": chg or 0.0,
                "pe": None,
                "pe_ratio": None,
                "high_52w": max(closes),
                "low_52w": min(closes),
                "volume": volume,
            }
        except Exception:
            return None

    companies = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_stock, symbol) for symbol, _ in NIFTY50[:50]]
        for future in as_completed(futures):
            c = future.result()
            if c:
                companies.append(c)

    # Stable order matching NIFTY50 list
    order = {symbol: i for i, (symbol, _) in enumerate(NIFTY50[:50])}
    companies.sort(key=lambda c: order.get(c["ticker"], 999))

    adv = len([c for c in companies if c["change"] > 0])
    dec = len([c for c in companies if c["change"] < 0])
    total = adv + dec

    sector_map = {t: s for t, s in NIFTY50}
    sector_returns = {}
    for c in companies:
        sector_returns.setdefault(sector_map.get(c["ticker"], "Other"), []).append(c["change"])
    sectors = [
        {"sector": s, "change": safe_float(sum(r) / len(r), 0)}
        for s, r in sorted(sector_returns.items())
    ]

    by_change = sorted(companies, key=lambda c: c["change"], reverse=True)
    movers = {
        "gainers": [{"symbol": c["symbol"], "change": c["change"]} for c in by_change[:5]],
        "losers": [{"symbol": c["symbol"], "change": c["change"]} for c in reversed(by_change[-5:])],
    }

    # ML predictions (best effort — models fetch history per company, so cap the count)
    predictions = []
    try:
        from prediction_service import get_prediction_service
        svc = get_prediction_service()
        if svc.is_available():
            subset = [c for c in by_change if c["price"]][:10]
            predictions = svc.predict_consolidated(subset)
    except Exception as e:
        logger.warning(f"Predictions unavailable: {e}")

    indicators = {
        "advancing_stocks": adv,
        "declining_stocks": dec,
        "advance_decline_ratio": safe_float(adv / dec, 0) if dec else None,
        "market_breadth": safe_float(adv / total * 100, 0) if total else None,
        "average_daily_return": safe_float(sum(c["change"] for c in companies) / len(companies), 0) if companies else None,
        "total_turnover": None,
        "total_traded_volume": sum(c["volume"] for c in companies if c["volume"]),
    }

    return {
        "index": index,
        "indicators": indicators,
        "news": [],
        "movers": movers,
        "sectors": sectors,
        "predictions": predictions,
        "companies": companies,
    }


@app.get("/api/dashboard")
async def get_dashboard():
    """Main dashboard data. Frontend expects {success, data:{index, indicators, news, movers, sectors, predictions, companies}}."""
    import time
    try:
        if _DASHBOARD_CACHE["data"] is None or (time.time() - _DASHBOARD_CACHE["ts"]) > _DASHBOARD_TTL:
            _DASHBOARD_CACHE["data"] = _build_dashboard_data()
            _DASHBOARD_CACHE["ts"] = time.time()
        return {"success": True, "data": _DASHBOARD_CACHE["data"]}
    except Exception as e:
        logger.error(f"Dashboard failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


class ReportRequest(BaseModel):
    name: str
    ticker: str


@app.post("/api/generate-report")
async def generate_report(request: ReportRequest):
    """Structured report data for the frontend renderer."""
    try:
        detail = await get_company_research(request.ticker)
        if not detail.get("success"):
            return {"success": False, "detail": detail.get("error", "Pipeline failed")}

        from datetime import datetime
        forecast = {
            "current_price": detail.get("price"),
            "predicted_price": detail.get("target_price"),
            "expected_return": detail.get("expected_return"),
            "direction": detail.get("analyst_rating", "Hold").upper().replace("BUY", "UP").replace("SELL", "DOWN"),
            "model": "Fundamental health analysis (Agent 4)",
        }
        highlights = (detail.get("positive_factors") or [])[:5]

        return {
            "success": True,
            "cover": {
                "title": "Investment Research Report",
                "subtitle": "AI-Generated Company Analysis",
                "company": detail.get("name", request.name),
                "ticker": detail.get("symbol", request.ticker),
            },
            "generated_date": datetime.utcnow().strftime("%B %d, %Y"),
            "executive_summary": {
                "company": detail.get("name", request.name),
                "sector": detail.get("sector"),
                "current_price": detail.get("price"),
                "change": detail.get("price_change") or 0,
                "assessment": detail.get("analyst_rating", "Hold"),
                "highlights": highlights,
            },
            "company_overview": {
                "market_cap": detail.get("market_cap"),
                "pe_ratio": detail.get("pe_ratio"),
                "dividend_yield": detail.get("dividend_yield"),
                "summary": detail.get("business_summary") or "No summary available.",
            },
            "risk_analysis": {
                "overall_risk": detail.get("risk_level", "Moderate"),
                "financial_observations": detail.get("risk_factors", [])[:6],
                "isolation_forest": {
                    "status": detail.get("risk_detail") and "Anomaly model assessed" or "N/A",
                    "explanation": detail.get("risk_detail") or "No analysis available.",
                },
                "peer_comparison": detail.get("peers", [])[:5],
            },
            "price_forecast": forecast,
            "final_assessment": {
                "overall": detail.get("analyst_rating", "Hold"),
                "strengths": highlights[:4],
                "areas_to_watch": (detail.get("risk_factors") or [])[:4],
                "conclusion": detail.get("business_summary") or "",
            },
        }
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return {"success": False, "detail": str(e)}


_COMPANY_MEMORY_CACHE = {}  # symbol -> {"memory", "agent2", "ts"}
_MEMORY_TTL = 1800  # 30 minutes


def _compute_financials(symbol):
    """Annual statements (last 4 FYs) + computed ratios for the Financials tab."""
    import yfinance as yf
    import numpy as np
    import math
    try:
        t = yf.Ticker(symbol)
        income, balance, cashflow = t.income_stmt, t.balance_sheet, t.cashflow

        def rows(df, wanted, calc_func=None):
            """Extract rows with fallback calculations for missing values."""
            out = {}
            if df.empty:
                return out
            cols = list(df.columns[:4])
            periods = [str(c.year) + "FY" if hasattr(c, "year") else str(c) for c in cols]
            for label, *keys in wanted:
                vals = []
                for col_idx, col in enumerate(cols):
                    v = None
                    for k in keys:
                        v = df[col].get(k)
                        if v is not None and not (isinstance(v, float) and np.isnan(v)):
                            break
                        v = None
                    
                    # Try calculation fallback if no direct value found
                    if v is None and calc_func:
                        v = calc_func(label, df[col], col_idx, cols)
                    
                    # Use safe_float to handle NaN/Inf
                    vals.append(safe_float(round(float(v) / 1e7, 1) if v is not None and abs(float(v)) > 1e6 else (float(v) if v is not None else None)))
                out[label] = vals
            return {"periods": periods, "rows": out}

        income_data = rows(income, [
            ("Revenue", "Total Revenue", "Operating Revenue"),
            ("Operating Expenses", "Operating Expense", "Total Expenses"),
            ("Operating Profit", "Operating Income", "EBIT"),
            ("Other Income", "Other Non Operating Income Expenses"),
            ("Interest", "Interest Expense", "Net Interest Income"),
            ("Depreciation", "Depreciation And Amortization", "Depreciation"),
            ("Profit Before Tax", "Pretax Income"),
            ("Tax", "Tax Provision"),
            ("Net Profit", "Net Income"),
        ])
        
        # Helper to calculate missing balance sheet items
        def calc_bs(label, row, col_idx, cols):
            """Calculate missing balance sheet values."""
            if label == "Operating Expenses":
                rev = row.get("Total Revenue") or row.get("Operating Revenue")
                op = row.get("Operating Income") or row.get("EBIT")
                if rev and op:
                    return rev - op
            elif label == "Tax":
                pbt = row.get("Pretax Income")
                ni = row.get("Net Income")
                if pbt and ni:
                    return max(0, pbt - ni)
            elif label == "Total Liabilities":
                assets = row.get("Total Assets")
                equity = row.get("Stockholders Equity") or row.get("Common Stock Equity")
                if assets and equity:
                    return assets - equity
            elif label == "Borrowings":
                # Try to find in total debt or long-term debt
                return None  # Already has fallback keys
            elif label == "Current Assets":
                assets = row.get("Total Assets")
                ppe = row.get("Property Plant And Equipment") or row.get("Gross PPE")
                if assets and ppe:
                    return max(0, assets - ppe)
            return None
        
        balance_data = rows(balance, [
            ("Total Assets", "Total Assets"),
            ("Current Assets", "Current Assets"),
            ("Total Liabilities", "Total Liabilities Net Minority Interest"),
            ("Current Liabilities", "Current Liabilities"),
            ("Total Debt", "Total Debt"),
            ("Stockholders Equity", "Stockholders Equity", "Common Stock Equity"),
            ("Cash", "Cash And Cash Equivalents"),
            ("Borrowings", "Long Term Debt", "Short Term Debt"),
            ("Investments", "Financial Assets"),
            ("Fixed Assets", "Property Plant And Equipment", "Gross PPE"),
        ], calc_bs)
        cashflow_data = rows(cashflow, [
            ("Operating Cash Flow", "Operating Cash Flow", "Total Cash From Operating Activities"),
            ("Capital Expenditure", "Capital Expenditure", "Capex"),
            ("Investing Cash Flow", "Investing Cash Flow"),
            ("Financing Cash Flow", "Financing Cash Flow"),
            ("Free Cash Flow", "Free Cash Flow"),
            ("Change In Cash", "Changes In Cash"),
        ])

        # Ratios from the latest column
        ratios = {}
        try:
            inc, bal = income.iloc[:, 0], balance.iloc[:, 0]
            rev = inc.get("Total Revenue")
            op = inc.get("Operating Income") or inc.get("EBIT")
            ni = inc.get("Net Income")
            assets = bal.get("Total Assets")
            debt = bal.get("Total Debt")
            eq = bal.get("Stockholders Equity")
            cl = bal.get("Current Liabilities")
            ca = bal.get("Current Assets")
            
            def pct(a, b):
                if not a or not b:
                    return None
                try:
                    a, b = float(a), float(b)
                    if b == 0 or not (math.isfinite(a) and math.isfinite(b)):
                        return None
                    result = round(a / b * 100, 2)
                    return safe_float(result)
                except:
                    return None
            
            ratios = {
                "net_profit_margin": pct(ni, rev),
                "operating_margin": pct(op, rev),
                "roe": pct(ni, eq),
                "roce": pct(op, (debt or 0) + (eq or 0)) if (debt is not None or eq is not None) else None,
                "debt_to_equity": safe_float(round(float(debt) / float(eq), 2)) if debt and eq else None,
                "current_ratio": safe_float(round(float(ca) / float(cl), 2)) if ca and cl else None,
            }

            # Report ratios: CAGR (3Y/5Y), interest coverage, PEG
            def _cagr_from(keys, years):
                try:
                    if len(income.columns) <= years:
                        return None
                    def val(col):
                        for k in keys:
                            v = income[col].get(k)
                            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                                return float(v)
                        return None
                    newest, oldest = val(income.columns[0]), val(income.columns[years])
                    if newest and oldest and oldest > 0 and newest > 0:
                        result = round(((newest / oldest) ** (1 / years) - 1) * 100, 2)
                        return safe_float(result)
                except Exception:
                    pass
                return None

            ratios["revenue_cagr_3y"] = _cagr_from(["Total Revenue"], 3)
            ratios["revenue_cagr_5y"] = _cagr_from(["Total Revenue"], 5)
            ratios["profit_cagr_3y"] = _cagr_from(["Net Income"], 3)
            ratios["profit_cagr_5y"] = _cagr_from(["Net Income"], 5)

            interest = inc.get("Interest Expense")
            if op and interest:
                try:
                    result = round(float(op) / abs(float(interest)), 2)
                    ratios["interest_coverage"] = safe_float(result)
                except:
                    ratios["interest_coverage"] = None

            pe_val = None
            try:
                pe_val = safe_float(t.info.get("trailingPE"))
            except Exception:
                pass
            if pe_val and ratios.get("profit_cagr_3y") and ratios["profit_cagr_3y"] > 0:
                ratios["peg"] = safe_float(round(float(pe_val) / ratios["profit_cagr_3y"], 2))
        except Exception:
            pass

        return {"income": income_data, "balance_sheet": balance_data, "cashflow": cashflow_data, "ratios": ratios}
    except Exception as e:
        logger.warning(f"Financials computation failed for {symbol}: {e}")
        # Return empty financials instead of None — frontend can handle it
        return {"income": {}, "balance_sheet": {}, "cashflow": {}, "ratios": {}}


def _compute_shareholding(symbol):
    """Shareholding pattern for the Shareholding tab (yfinance holders data)."""
    import yfinance as yf
    try:
        t = yf.Ticker(symbol)
        info = t.info
        summary = {
            "institutions_pct": safe_float(info.get("heldByInstitutions")),
            "insiders_pct": safe_float(info.get("heldByInsiders")),
            "float_pct": safe_float(info.get("floatShares") / info.get("sharesOutstanding") * 100) if info.get("floatShares") and info.get("sharesOutstanding") else None,
            "shares_outstanding": safe_float(info.get("sharesOutstanding")),
        }

        def holders(df, limit=5):
            out = []
            if df is None or df.empty:
                return out
            for _, row in df.head(limit).iterrows():
                out.append({
                    "name": str(row.get("Holder") or row.get("holder") or ""),
                    "shares": safe_float(row.get("Shares") or row.get("shares")),
                    "pct": safe_float(row.get("pctHeld") or row.get("pct")) * 100 if safe_float(row.get("pctHeld") or row.get("pct")) else None,
                    "value": safe_float(row.get("Value") or row.get("value")),
                })
            return out

        inst = holders(t.institutional_holders)
        mutual = holders(t.mutualfund_holders)
        return {
            "summary": summary,
            "institutional_holders": inst,
            "mutual_fund_holders": mutual,
        }
    except Exception as e:
        logger.warning(f"Shareholding computation failed for {symbol}: {e}")
        return None


def _compute_roe(ticker):
    """ROE = Net Income / Stockholders Equity * 100, from yfinance statements."""
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        ni = t.income_stmt.iloc[:, 0].get("Net Income") if not t.income_stmt.empty else None
        eq = t.balance_sheet.iloc[:, 0].get("Stockholders Equity") if not t.balance_sheet.empty else None
        if ni and eq:
            return round(float(ni) / float(eq) * 100, 2)
    except Exception:
        pass
    return None


def _readable_source(url, fallback="Google News"):
    """Derive a publication name from an article URL (e.g. business-standard.com)."""
    try:
        host = url.split("/")[2].replace("www.", "")
        parts = host.split(".")
        name = parts[-2] if len(parts) >= 2 else host
        return name.replace("-", " ").title()
    except Exception:
        return fallback


def _fetch_peer_details(peer_tickers, limit=6):
    """Turn peer ticker strings into {name, pe, price} dicts for the frontend."""
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor

    def fetch_one(sym):
        try:
            info = yf.Ticker(sym).info
            return {
                "name": info.get("shortName") or info.get("longName") or sym.split(".")[0],
                "pe": safe_float(info.get("trailingPE")),
                "price": safe_float(info.get("currentPrice") or info.get("regularMarketPrice")),
                "ticker": sym,
            }
        except Exception:
            return {"name": sym.split(".")[0], "pe": None, "price": None, "ticker": sym}

    tickers = [t for t in peer_tickers if isinstance(t, str)][:limit]
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(fetch_one, tickers))


@app.get("/api/company/{symbol}/financials")
async def get_financials(symbol: str):
    """Fetch multi-year P&L, Balance Sheet, Cash Flow, and computed ratios with smart calculations."""
    try:
        import yfinance as yf
        from backend.financial_calculators import (
            get_field, to_cr, calc_operating_profit, calc_opm, calc_pbt, calc_tax, calc_eps,
            calc_total_liabilities, calc_reserves, calc_other_liabilities, calc_other_assets,
            calc_roe, calc_roce, calc_de_ratio, calc_current_ratio
        )
        
        full_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        ticker = yf.Ticker(full_symbol)
        
        # Get current price and P/E for EPS calculation (top-down: Price / P/E)
        current_price = safe_float(ticker.info.get("currentPrice")) or safe_float(ticker.info.get("regularMarketPrice"))
        pe_ratio = safe_float(ticker.info.get("trailingPE"))
        shares_out = safe_float(ticker.info.get("sharesOutstanding"))
        # Don't convert - keep in actual shares, EPS = NI/Shares
        
        def fetch_statements(df, row_keys):
            """Extract statement rows, calculate missing fields."""
            if df.empty:
                return {"periods": [], "rows": {}}
            cols = list(df.columns[:4])  # Changed from 5 to 4 to skip empty 2022 column
            periods = [str(c.year) if hasattr(c, "year") else str(c) for c in cols]
            rows = {}
            for label, *keys in row_keys:
                vals = []
                for col_idx, col in enumerate(cols):
                    row = df[col]
                    is_latest = (col_idx == 0)  # First column is latest year
                    # Direct lookup
                    v = get_field(row, *keys)
                    # Smart fallbacks for common missing fields
                    if v is None:
                        if label == "Operating Profit":
                            v = calc_operating_profit(row)
                        elif label == "Operating Expenses":
                            rev = get_field(row, "Total Revenue")
                            op_profit = calc_operating_profit(row)
                            if rev and op_profit:
                                v = rev - op_profit
                        elif label == "Other Income":
                            v = get_field(row, "Other Non Operating Income Expenses", "Special Income Charges")
                        elif label == "Profit Before Tax":
                            op_profit = calc_operating_profit(row)
                            rev = get_field(row, "Total Revenue")
                            v = calc_pbt(row, op_profit, rev)
                        elif label == "Tax":
                            pbt = get_field(row, "Pretax Income") or calc_pbt(row, None, None)
                            ni = get_field(row, "Net Income")
                            v = calc_tax(row, pbt, ni)
                        elif label == "EPS":
                            ni = get_field(row, "Net Income")
                            shares = get_field(row, "Diluted Average Shares", "Basic Average Shares")
                            # Use top-down for latest year only: Price / P/E
                            v = calc_eps(row, ni, shares, current_price=current_price, pe_ratio=pe_ratio, is_latest_year=is_latest)
                        elif label == "Borrowings":
                            # Try Total Debt fields first
                            v = get_field(row, "Total Debt", "Long Term Debt", "Current Debt", 
                                         "Short Term Borrowings", "Long Term Borrowings")
                            # Fallback: if nothing found, try to calculate from balance sheet
                            if v is None:
                                # Try Total Liabilities - Equity approach
                                total_assets = get_field(row, "Total Assets")
                                total_equity = get_field(row, "Stockholders Equity", "Common Stock Equity")
                                if total_assets and total_equity:
                                    total_liab = total_assets - total_equity
                                    current_liab = get_field(row, "Current Liabilities")
                                    if current_liab:
                                        # Borrowings ≈ Total Debt ≈ Long-term liabilities + Short-term debt
                                        v = max(0, total_liab - current_liab)  # Non-current portion often has borrowings
                        elif label == "Other Liabilities":
                            total_liab = get_field(row, "Total Liabilities Net Minority Interest")
                            curr_liab = get_field(row, "Current Liabilities")
                            non_curr_liab = get_field(row, "Total Non Current Liabilities Net Minority Interest")
                            v = calc_other_liabilities(row, total_liab, curr_liab, non_curr_liab)
                        elif label == "Total Liabilities":
                            total_assets = get_field(row, "Total Assets")
                            v = calc_total_liabilities(row, total_assets)
                        elif label == "CWIP":
                            v = get_field(row, "Construction In Progress", "Capital Work In Progress")
                            if v is None:
                                v = 0  # CWIP can be 0 if no construction in progress
                        elif label == "Investments":
                            # Try multiple financial asset fields
                            v = get_field(row, "Financial Assets", "Long Term Equity Investment", 
                                         "Non Current Financial Assets", "Investments In Subsidiaries")
                            # If still empty, it's often a small line item - use 0 as fallback
                            if v is None:
                                v = 0  # Investments can legitimately be 0 or minimal
                        elif label == "Other Assets":
                            # Direct lookup
                            v = get_field(row, "Other Non Current Assets", "Other Assets", 
                                         "Other Current Assets", "Deferred Tax Assets")
                            # Fallback: calculate from components
                            if v is None:
                                total_assets = get_field(row, "Total Assets")
                                current_assets = get_field(row, "Current Assets")
                                if total_assets and current_assets:
                                    # Other Assets = Total - Current
                                    v = max(0, total_assets - current_assets)
                    vals.append(to_cr(v) if label != "EPS" else v)  # EPS should not be converted to crores
                rows[label] = vals
            return {"periods": periods, "rows": rows}
        
        income = ticker.income_stmt
        balance = ticker.balance_sheet
        cashflow = ticker.cashflow
        
        # P&L with calculation support
        p_l = fetch_statements(income, [
            ("Revenue", "Total Revenue", "Operating Revenue"),
            ("Operating Expenses", "Operating Expense"),
            ("Operating Profit", "EBIT", "Operating Income"),
            ("Other Income", "Other Non Operating Income Expenses"),
            ("Interest", "Interest Expense", "Net Interest Income"),
            ("Depreciation", "Depreciation And Amortization In Income Statement", "Depreciation", "Reconciled Depreciation"),
            ("Profit Before Tax", "Pretax Income"),
            ("Tax", "Tax Provision"),
            ("Net Profit", "Net Income"),
            ("EPS", "Diluted EPS", "Basic EPS"),
        ])
        
        # Balance Sheet with calculation support
        bs = fetch_statements(balance, [
            ("Equity Share Capital", "Capital Stock", "Common Stock"),
            ("Reserves", "Retained Earnings", "Additional Paid In Capital"),
            ("Borrowings", "Total Debt", "Long Term Debt", "Current Debt"),
            ("Other Liabilities", "Other Current Liabilities"),
            ("Total Liabilities", "Total Liabilities Net Minority Interest"),
            ("Fixed Assets", "Gross PPE", "Net PPE"),
            ("CWIP", "Construction In Progress"),
            ("Investments", "Financial Assets"),
            ("Other Assets", "Other Non Current Assets"),
            ("Total Assets", "Total Assets"),
        ])
        
        # Cash Flow
        cf = fetch_statements(cashflow, [
            ("Operating Cash Flow", "Operating Cash Flow"),
            ("Investing Cash Flow", "Investing Cash Flow"),
            ("Financing Cash Flow", "Financing Cash Flow"),
            ("Net Cash Flow", "Free Cash Flow", "Changes In Cash"),
        ])
        
        # Ratios with smart calculations
        ratios = {}
        try:
            inc, bal = income.iloc[:, 0], balance.iloc[:, 0]
            rev = get_field(inc, "Total Revenue")
            op = calc_operating_profit(inc)
            ni = get_field(inc, "Net Income")
            assets = get_field(bal, "Total Assets")
            debt = get_field(bal, "Total Debt", "Long Term Debt")
            eq = get_field(bal, "Stockholders Equity", "Common Stock Equity")
            cl = get_field(bal, "Current Liabilities")
            ca = get_field(bal, "Current Assets")
            shares = get_field(inc, "Diluted Average Shares", "Basic Average Shares")
            
            # Net Profit Margin
            if ni and rev:
                ratios["net_profit_margin"] = safe_float(round(ni / rev * 100, 2))
            
            # Operating Margin
            if op and rev:
                ratios["operating_margin"] = safe_float(round(op / rev * 100, 2))
            
            # ROE
            if ni and eq:
                ratios["roe"] = safe_float(calc_roe(ni, eq))
            
            # ROCE
            if op and assets and cl:
                ratios["roce"] = safe_float(calc_roce(op, assets, cl))
            elif op and eq and debt:
                # Alternative: ROCE = EBIT / (Equity + Debt)
                capital = eq + debt
                if capital > 0:
                    ratios["roce"] = safe_float(round(op / capital * 100, 2))
            
            # Debt to Equity
            if debt and eq:
                ratios["debt_to_equity"] = safe_float(calc_de_ratio(debt, eq))
            
            # Current Ratio
            if ca and cl:
                ratios["current_ratio"] = safe_float(calc_current_ratio(ca, cl))
        except Exception as e:
            logger.debug(f"Ratio calc failed: {e}")
        
        return {
            "p_l": p_l,
            "balance_sheet": bs,
            "cash_flow": cf,
            "ratios": ratios
        }
    except Exception as e:
        logger.warning(f"Financials fetch failed for {symbol}: {e}")
        return {"error": str(e), "p_l": {}, "balance_sheet": {}, "cash_flow": {}, "ratios": {}}

@app.get("/api/company/{symbol}/price-history")
async def get_price_history(symbol: str):
    """Fetch intraday and historical daily price data for charting."""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        
        full_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        ticker = yf.Ticker(full_symbol)
        
        # Get intraday data (last 1 day)
        intraday = []
        try:
            intra_df = ticker.history(period="1d", interval="15m")
            intraday = [
                {"date": idx.isoformat(), "close": float(row["Close"])}
                for idx, row in intra_df.iterrows()
                if not isnan(row["Close"])
            ]
        except:
            pass
        
        # Get historical daily data (5 years)
        history = []
        try:
            hist_df = ticker.history(period="5y")
            history = [
                {"date": idx.isoformat(), "close": float(row["Close"])}
                for idx, row in hist_df.iterrows()
                if not isnan(row["Close"])
            ]
        except:
            pass
        
        return {"chart_series": {"intraday": intraday, "history": history}}
    
    except Exception as e:
        logger.warning(f"Price history failed for {symbol}: {e}")
        return {"chart_series": {"intraday": [], "history": []}}


@app.get("/api/company/{symbol}")
async def get_company_research(symbol: str):
    """Company research: use pipeline with proper error handling."""
    try:
        from company_context import CompanyContext
        from pipeline import run_pipeline
        
        # Ensure symbol has .NS suffix
        full_symbol = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
        
        # Validate company context
        try:
            company_ctx = CompanyContext(ticker=full_symbol, name=symbol)
        except ValueError as e:
            return {
                "success": False,
                "error": f"Invalid ticker: {str(e)}",
                "symbol": symbol
            }
        
        # Run pipeline (uses caching, parallel agents); 366d so the price-trend chart can offer a 1Y view
        result = run_pipeline(f"Analyze {symbol}", ticker=full_symbol, days=366)
        
        if result.get("error"):
            return {
                "success": False,
                "error": f"Pipeline failed: {result.get('error')}",
                "symbol": symbol
            }
        
        agent1_output = result.get("agent1_output", {})
        agent2_output = result.get("agent2_output", {})
        agent3_output = result.get("agent3_output", {})
        agent4_output = result.get("agent4_output", {})
        
        # Build company memory
        memory = company_memory.build_company_memory(
            agent1_output, agent2_output, agent3_output
        )
        
        # Extract data
        info = memory.get("company_info", {})
        price_data = memory.get("price_data", {})
        current_price = price_data.get("current")
        
        # Sentiment handling (None if no analysis)
        sentiment_status = agent3_output.get("sentiment")
        sentiment_score = None
        if sentiment_status:
            sentiment_score = 75 if sentiment_status == "Bullish" else 25 if sentiment_status == "Bearish" else 50
        
        # Target price - from analyst data in agent1, not agent4
        target_price = memory.get("market_stats", {}).get("target_price")
        if not target_price:
            # Fallback: check agent1 analyst_data directly
            target_price = agent1_output.get("analyst_data", {}).get("target_mean_price")
        expected_return = None
        if target_price and current_price:
            expected_return = ((target_price - current_price) / current_price) * 100
        
        from datetime import datetime

        # ── News articles (Google News RSS + article scraping via agent1) ──
        raw_articles = agent1_output.get("news", {}).get("articles", []) or []
        news_articles = []
        for art in raw_articles[:8]:
            headline = art.get("title") or art.get("headline") or ""
            if not headline:
                continue
            url = art.get("url") or ""
            news_articles.append({
                "headline": headline,
                "summary": (art.get("summary") or art.get("description") or "")[:300],
                "url": url,
                "source": (art.get("source") or "").strip() not in ("", "web") and art.get("source") or (_readable_source(url) if url else "Google News"),
                "date": art.get("date") or "",
            })

        # ── Catalysts: linked news items with descriptions ──
        catalysts = [
            {"title": a["headline"], "summary": a["summary"], "url": a["url"], "source": a["source"]}
            for a in news_articles[:5]
        ]
        if not catalysts:
            for c in (agent3_output.get("catalysts") or [])[:5]:
                catalysts.append({
                    "title": c if isinstance(c, str) else str(c),
                    "summary": "", "url": "", "source": "",
                })

        # ── Risk explanation from the anomaly model + red flags ──
        model_assessment = agent2_output.get("model_assessment", {}) or {}
        anomaly_score = model_assessment.get("anomaly_score")
        red_flags = agent2_output.get("red_flags", []) or []
        risk_parts = []
        if anomaly_score is not None:
            if model_assessment.get("is_anomaly"):
                risk_parts.append(
                    f"Isolation Forest flagged an unusual financial pattern for this stock (anomaly score {anomaly_score:.2f}); treat reported figures with extra caution."
                )
            else:
                risk_parts.append(
                    f"Isolation Forest found the financial profile within normal ranges compared to its own history (anomaly score {anomaly_score:.2f}, where higher means more unusual)."
                )
        explained_flags = [f for f in red_flags if isinstance(f, dict) and (f.get("explanation") or f.get("metric"))]
        if explained_flags:
            concerns = "; ".join(
                (f.get("metric") and f"{f.get('metric')}: {f.get('explanation')}") or f.get("explanation") or ""
                for f in explained_flags[:3]
            )
            risk_parts.append(f"Key concerns identified: {concerns}.")
        risk_detail = " ".join(risk_parts) or model_assessment.get("risk_explanation") or None

        # ── Risk factors as display strings (frontend renders them verbatim) ──
        risk_factors = []
        for r in (agent3_output.get("risks") or red_flags or [])[:6]:
            if isinstance(r, str):
                risk_factors.append(r)
            elif isinstance(r, dict):
                metric, value, explanation = r.get("metric"), r.get("value"), r.get("explanation")
                if metric and explanation:
                    risk_factors.append(f"{metric}: {explanation}")
                elif metric and value:
                    risk_factors.append(f"{metric}: {value}")
                elif explanation:
                    risk_factors.append(explanation)
                elif metric:
                    risk_factors.append(metric)

        # ── Real metric values for the Data Sources panel ──
        fetch_time = datetime.utcnow().isoformat() + "Z"
        roe_value = info.get("return_on_equity") if info.get("return_on_equity") is not None else _compute_roe(symbol)
        if model_assessment.get("is_anomaly") or (anomaly_score or 0) >= 0.7:
            risk_level_value = "High"
        elif (anomaly_score or 0) >= 0.3:
            risk_level_value = "Moderate"
        elif anomaly_score is not None:
            risk_level_value = "Low"
        else:
            risk_level_value = "Moderate"

        analyst_data = memory.get("analyst_data", {}) or {}
        mood = memory.get("dashboard", {}).get("market_mood", {}) or {}

        price_detail = None
        if current_price is not None:
            price_detail = f"₹{current_price:,.2f}"
            high, low = price_data.get("high_52w"), price_data.get("low_52w")
            if high and low:
                price_detail += f" · 52W ₹{high:,.0f}–₹{low:,.0f}"

        analyst_rec = analyst_data.get("recommendation_key") or analyst_data.get("recommendation")
        analyst_tgt = analyst_data.get("target_mean_price") or analyst_data.get("price_target")
        analyst_cnt = analyst_data.get("number_of_analysts") or analyst_data.get("analysts_count")
        analyst_detail = None
        if analyst_tgt or analyst_rec:
            parts = []
            if analyst_rec:
                parts.append(str(analyst_rec).replace("_", " ").upper())
            if analyst_tgt:
                parts.append(f"Target ₹{analyst_tgt:,.0f}")
            if analyst_cnt:
                parts.append(f"{analyst_cnt} analysts")
            analyst_detail = " · ".join(parts)

        fund_parts = []
        if info.get("pe_ratio"):
            fund_parts.append(f"P/E {info['pe_ratio']:.1f}x")
        if roe_value is not None:
            fund_parts.append(f"ROE {roe_value:.1f}%")
        if info.get("dividend_yield"):
            fund_parts.append(f"Yield {info['dividend_yield']:.2f}%")
        if red_flags:
            fund_parts.append(f"{len(red_flags)} flags checked")
        fundamentals_detail = " · ".join(fund_parts) or None

        news_count = len(agent1_output.get("news", {}).get("articles", []))
        sentiment_detail = None
        if sentiment_score is not None:
            sentiment_detail = f"{sentiment_status} ({sentiment_score}/100)"
        elif mood.get("overall_sentiment"):
            sentiment_detail = f"AI mood from news flow: {mood.get('overall_sentiment')}"

        risk_detail_line = None
        if anomaly_score is not None:
            risk_detail_line = f"Anomaly score {anomaly_score:.2f} · {'Unusual pattern flagged' if model_assessment.get('is_anomaly') else 'Normal pattern'} · {risk_level_value} risk"

        # ── Tab data: Financials / Shareholding / Peer metrics ──
        # Build financials from agent2's financial_facts (real data from health analysis)
        financials_facts = agent2_output.get("financial_facts", {})
        financials = {
            "ratios": {
                "net_profit_margin": safe_float(financials_facts.get("NetProfit")),
                "operating_margin": safe_float(financials_facts.get("OperatingMargin")),
                "roe": safe_float(financials_facts.get("ROCE")),  # Using ROCE as ROE proxy
                "roce": safe_float(financials_facts.get("ROCE")),
                "debt_to_equity": safe_float(financials_facts.get("Debt")),
                "current_ratio": safe_float(financials_facts.get("CurrentRatio")),
            },
            "income": {},
            "balance_sheet": {},
            "cashflow": {}
        }
        shareholding = _compute_shareholding(symbol)
        peer_metrics = agent2_output.get("peer_comparison", {}).get("metrics", {}) or {}

        # Cache memory so the tab AI assistant can answer from the same live data
        _COMPANY_MEMORY_CACHE[symbol.strip().upper()] = {
            "memory": memory, "agent2": agent2_output, "ts": time.time(),
        }

        # ── Analyst + news-sentiment breakdown for People's Perspective ──
        mkt_facts = agent3_output.get("market_facts", {}) or {}
        analyst_breakdown = {
            "recommendation": mkt_facts.get("recommendation"),
            "target": mkt_facts.get("target_price"),
            "analyst_count": mkt_facts.get("analyst_count"),
            "upside_downside_percent": mkt_facts.get("upside_downside_percent"),
            "buy": mkt_facts.get("buy"),
            "hold": mkt_facts.get("hold"),
            "sell": mkt_facts.get("sell"),
        }
        news_sentiment_counts = {
            "positive": mkt_facts.get("articles_positive") or 0,
            "negative": mkt_facts.get("articles_negative") or 0,
            "neutral": mkt_facts.get("articles_neutral") or 0,
        }

        # ── Forecast explainability (LLM with deterministic fallback) ──
        try:
            from agent_4.agent import explain_forecast
            forecast_explanation = explain_forecast(
                memory, current_price, target_price, expected_return,
                agent4_output.get("consensus_rating", "Hold")
            )
        except Exception as e:
            logger.warning(f"Forecast explanation failed: {e}")
            forecast_explanation = None

        # ── Peers with live name + P/E ──
        raw_peers = agent2_output.get("peer_comparison", {}).get("peers", []) or []
        if raw_peers and isinstance(raw_peers[0], dict):
            peers = raw_peers
        else:
            try:
                peers = _fetch_peer_details(raw_peers)
            except Exception as e:
                logger.warning(f"Peer detail fetch failed: {e}")
                peers = [{"name": t.split(".")[0], "pe": None, "price": None, "ticker": t} for t in raw_peers[:6]]

        # Real day change from the last two daily closes in the OHLCV series
        price_change = None
        try:
            ohlcv = price_data.get("ohlcv") or []
            closes = [row.get("close") for row in ohlcv if row.get("close") is not None]
            if len(closes) >= 2 and current_price:
                # If current_price matches the last close, use the prior close as reference
                ref = closes[-2] if abs(closes[-1] - current_price) < 1e-6 else closes[-1]
                if ref:
                    price_change = round((current_price - ref) / ref * 100, 2)
        except Exception as e:
            logger.warning(f"Price change computation failed for {symbol}: {e}")

        response = {
            "success": True,
            "name": info.get("name", symbol),
            "symbol": symbol,
            "price": current_price,
            "price_change": price_change,
            "market_cap": info.get("market_cap"),
            "pe_ratio": info.get("pe_ratio"),
            "roe": roe_value,
            "dividend_yield": info.get("dividend_yield"),
            "high_52w": price_data.get("high_52w"),
            "low_52w": price_data.get("low_52w"),
            "business_summary": info.get("summary", ""),
            "sector": info.get("sector", ""),
            "market_intelligence": agent3_output.get("market_intelligence_report", {}).get("market_perception", "") or agent3_output.get("market_intelligence_report", ""),
            "catalysts": catalysts,
            "news_articles": news_articles,
            "sentiment_score": sentiment_score,
            "positive_factors": agent3_output.get("opportunities", []) or agent2_output.get("fundamental_signals", {}).get("strengths", []),
            "risk_factors": risk_factors,
            "risk_level": risk_level_value,
            "risk_detail": risk_detail,
            "peers": peers,
            "price_history": price_data.get("ohlcv") or [],
            "current_price": current_price,
            "target_price": target_price,
            "expected_return": expected_return,
            "analyst_rating": agent4_output.get("consensus_rating", "Hold"),
            "forecast_explanation": forecast_explanation,
            "financials": financials,
            "shareholding": shareholding,
            "peer_metrics": peer_metrics,
            "analyst_breakdown": analyst_breakdown,
            "news_sentiment_counts": news_sentiment_counts,
            # Add missing metadata for frontend
            "_data_quality": {
                "price_available": current_price is not None,
                "news_available": len(agent1_output.get("news", {}).get("articles", [])) > 0,
                "sentiment_analyzed": sentiment_score is not None,
                "risks_identified": len(agent2_output.get("risks", [])) > 0,
                "peer_data_available": len(agent2_output.get("peer_comparison", {}).get("peers", [])) > 0,
            },
            "_data_sources": {
                "fetched_at": fetch_time,
                "price_data": {
                    "source": "yfinance",
                    "available": current_price is not None,
                    "timestamp": agent1_output.get("price_history", {}).get("timestamp") or fetch_time,
                    "detail": price_detail,
                },
                "news": {
                    "source": "Google News RSS",
                    "available": news_count > 0,
                    "timestamp": agent1_output.get("news", {}).get("timestamp") or fetch_time,
                    "count": news_count,
                    "detail": f"{news_count} articles scraped (headlines + summaries)" if news_count else None,
                },
                "analyst_consensus": {
                    "source": "yfinance targets",
                    "available": bool(analyst_data),
                    "timestamp": agent1_output.get("analyst_consensus", {}).get("timestamp") or fetch_time,
                    "detail": analyst_detail,
                },
                "fundamentals": {
                    "source": "yfinance + AI",
                    "available": bool(fundamentals_detail),
                    "timestamp": agent2_output.get("timestamp") or fetch_time,
                    "detail": fundamentals_detail,
                },
                "sentiment": {
                    "source": "Groq LLM",
                    "available": sentiment_detail is not None,
                    "timestamp": agent3_output.get("timestamp") or fetch_time,
                    "detail": sentiment_detail,
                },
                "risk_model": {
                    "source": "Isolation Forest",
                    "available": anomaly_score is not None,
                    "timestamp": agent2_output.get("model_timestamp") or fetch_time,
                    "detail": risk_detail_line,
                },
            }
        }
        logger.info(f"Company {symbol}: success")
        return response
    except Exception as e:
        logger.error(f"Company research failed for {symbol}: {e}", exc_info=True)
        return {"success": False, "error": str(e), "symbol": symbol}

@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Chat about a company, grounded in the cached live data and the tab the user is viewing."""
    from rag_assistant import rag_chat
    symbol = request.symbol.strip().upper()
    entry = _COMPANY_MEMORY_CACHE.get(symbol)
    if not entry or (time.time() - entry["ts"]) > _MEMORY_TTL:
        memory = company_memory.load_company_memory()
        if not memory:
            return ChatResponse(
                answer="I don't have this company's data loaded yet. Open its research page first (that loads the data I answer from), then ask me again."
            )
        entry = {"memory": memory, "agent2": {}, "ts": time.time()}

    tab_context = None
    if request.tab:
        tab_context = (
            f"Active tab: {request.tab}\n"
            f"Data currently rendered on the user's screen:\n{request.context or '(not provided)'}"
        )

    result = rag_chat(
        request.question,
        entry["memory"],
        entry.get("agent2") or {},
        ticker=symbol,
        tab_context=tab_context,
    )
    return ChatResponse(answer=result.get("response", "I couldn't generate a response."))


def _generate_exec_summary(detail, ratios):
    """One focused Groq call over already-computed metrics; deterministic fallback."""
    digest = {
        "company": detail.get("name"),
        "sector": detail.get("sector"),
        "price": detail.get("price"),
        "pe": detail.get("pe_ratio"),
        "roe": detail.get("roe"),
        "dividend_yield": detail.get("dividend_yield"),
        "risk_level": detail.get("risk_level"),
        "risk_notes": detail.get("risk_factors"),
        "positives": detail.get("positive_factors"),
        "analyst_rating": detail.get("analyst_rating"),
        "target_price": detail.get("target_price"),
        "expected_return_pct": detail.get("expected_return"),
        "ratios": ratios,
    }
    prompt = (f"You are an equity research analyst. Write a 3-4 sentence executive summary of this company "
              f"combining its financial health and market outlook. Reference concrete numbers. No advice language. "
              f"Company data: {json.dumps(digest, default=str)}")
    try:
        import os
        from langchain_groq import ChatGroq
        llm = ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), temperature=0, max_tokens=4096)
        text = llm.invoke(prompt).content.strip()
        if "<think>" in text:
            text = text.split("</think>")[-1].strip()
        if len(text) > 60:
            return text
    except Exception as e:
        logger.warning(f"Exec summary LLM failed, using fallback: {e}")
    r = ratios or {}
    ret = detail.get("expected_return")
    return (f"{detail.get('name')} operates in the {detail.get('sector') or 'its'} sector with a current price of "
            f"₹{detail.get('price') or 'N/A'}. Profitability metrics show ROE of {r.get('roe') or 'N/A'}% and an "
            f"operating margin of {r.get('operating_margin') or 'N/A'}%, while carrying a {detail.get('risk_level') or 'Moderate'} risk "
            f"profile. Analyst consensus stands at {detail.get('analyst_rating') or 'Hold'}"
            + (f" with a target of ₹{detail.get('target_price'):,.0f} implying {ret:.1f}% expected return." if ret is not None and detail.get('target_price') else ".")
            + " Overall, the data suggests a balanced risk-reward profile based on the metrics above.")


def _build_report_html(detail, exec_summary):
    """Compile the full report from the SAME response dict the live tabs render."""
    import html as _h

    def esc(v):
        return _h.escape(str(v)) if v is not None else "N/A"

    f = detail.get("financials") or {}
    ratios = f.get("ratios") or {}
    chg = detail.get("price_change")
    chg_txt = f"{chg:+.2f}%" if isinstance(chg, (int, float)) else "N/A"
    chg_cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"

    def stmt_table(title, d, years=3):
        if not d or not d.get("periods"):
            return ""
        periods = d["periods"][:years]
        rows = "".join(
            f"<tr><td>{esc(label)}</td>" + "".join(f"<td class='num'>{v if v is not None else 'N/A'}</td>" for v in vals[:years]) + "</tr>"
            for label, vals in d["rows"].items()
        )
        return (f"<h2>{esc(title)} <span class='unit'>(last {years} years, ₹ Crore)</span></h2>"
                f"<table><tr><th></th>" + "".join(f"<th>{esc(p)}</th>" for p in periods) + f"</tr>{rows}</table>")

    ratio_rows = [
        ("Revenue CAGR (3Y)", ratios.get("revenue_cagr_3y"), "%"),
        ("Revenue CAGR (5Y)", ratios.get("revenue_cagr_5y"), "%"),
        ("Net Profit CAGR (3Y)", ratios.get("profit_cagr_3y"), "%"),
        ("Net Profit CAGR (5Y)", ratios.get("profit_cagr_5y"), "%"),
        ("PEG Ratio", ratios.get("peg"), ""),
        ("Operating Profit Margin", ratios.get("operating_margin"), "%"),
        ("Net Profit Margin", ratios.get("net_profit_margin"), "%"),
        ("Interest Coverage Ratio", ratios.get("interest_coverage"), "x"),
        ("ROE", ratios.get("roe"), "%"),
        ("ROCE", ratios.get("roce"), "%"),
        ("Debt / Equity", ratios.get("debt_to_equity"), "x"),
        ("Current Ratio", ratios.get("current_ratio"), "x"),
    ]
    ratio_html = "".join(
        f"<tr><td>{esc(label)}</td><td class='num'>{v if v is not None else 'N/A'}{suffix if v is not None else ''}</td></tr>"
        for label, v, suffix in ratio_rows
    )

    def fmt_num(v, fmt):
        return fmt.format(float(v)) if isinstance(v, (int, float)) else "N/A"

    peers = detail.get("peers") or []
    peer_html = "".join(
        f"<tr><td>{esc(p.get('name'))}</td><td class='num'>{'₹' + fmt_num(p.get('price'), ',.0f')}</td>"
        f"<td class='num'>{fmt_num(p.get('pe'), '.1f') + 'x' if p.get('pe') is not None else 'N/A'}</td></tr>"
        for p in peers
    ) or "<tr><td colspan='3'>N/A</td></tr>"

    catalysts = detail.get("catalysts") or []
    cat_html = "".join(
        f"<li>{esc(c.get('title') if isinstance(c, dict) else c)}"
        + (f" — <span class='muted'>{esc(c.get('source'))}</span>" if isinstance(c, dict) and c.get("source") else "")
        + (f"<br><span class='muted'>{esc(c.get('summary'))}</span>" if isinstance(c, dict) and c.get("summary") else "")
        + "</li>"
        for c in catalysts
    ) or "<li>No recent catalysts identified</li>"

    nsc = detail.get("news_sentiment_counts") or {}
    ab = detail.get("analyst_breakdown") or {}
    fx = detail.get("forecast_explanation") or {}
    rec_txt = (ab.get("recommendation") or "").replace("_", " ").upper()
    rec_txt = rec_txt if rec_txt and rec_txt != "NONE" else "N/A"

    snapshot = [
        ("Market Cap", detail.get("market_cap")), ("P/E Ratio", detail.get("pe_ratio")),
        ("ROE", detail.get("roe")), ("Dividend Yield", detail.get("dividend_yield")),
        ("52W High", detail.get("high_52w")), ("52W Low", detail.get("low_52w")),
    ]
    snapshot_html = "".join(f"<div class='stat'><div class='label'>{esc(k)}</div><div class='value'>{esc(v)}</div></div>" for k, v in snapshot)

    from datetime import datetime as _dt
    gen_time = _dt.now().strftime("%d %b %Y, %H:%M IST")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Research Report — {esc(detail.get('name'))}</title>
<style>
body{{font-family:'Segoe UI',Arial,sans-serif;max-width:900px;margin:0 auto;padding:36px;color:#0f172a;line-height:1.55}}
h1{{font-size:28px;margin-bottom:4px}} h2{{font-size:19px;border-bottom:2px solid #003ec8;padding-bottom:6px;margin-top:32px}}
.unit{{font-size:12px;color:#64748b;font-weight:normal}}
table{{width:100%;border-collapse:collapse;margin:12px 0}} td,th{{border:1px solid #cbd5e1;padding:8px;text-align:left;font-size:14px}}
th{{background:#f1f5f9}} .num{{text-align:right;font-family:Consolas,monospace}}
.up{{color:#00A86B;font-weight:700}} .down{{color:#E5484D;font-weight:700}}
.stat-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:14px 0}}
.stat{{border:1px solid #e2e8f0;border-radius:8px;padding:10px}} .stat .label{{font-size:11px;color:#64748b;text-transform:uppercase;font-weight:600}} .stat .value{{font-size:18px;font-weight:700;margin-top:4px}}
.header{{border-bottom:3px solid #003ec8;padding-bottom:14px;margin-bottom:10px}}
.brand{{font-size:12px;color:#64748b;letter-spacing:1px;text-transform:uppercase}}
.muted{{color:#64748b;font-size:13px}}
footer{{margin-top:40px;border-top:1px solid #cbd5e1;padding-top:14px;font-size:12px;color:#64748b}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:13px;font-weight:700}}
</style></head><body>

<div class="header">
  <div class="brand">Generated by Stock Market Research Agent</div>
  <h1>{esc(detail.get('name'))} <span style="font-size:16px;color:#64748b">({esc(detail.get('symbol'))})</span></h1>
  <p>{esc(detail.get('sector'))} ·
     Current Price: <b>₹{esc(detail.get('price'))}</b>
     <span class="{chg_cls}">{('▲ ' + chg_txt) if isinstance(chg, (int, float)) and chg >= 0 else ('▼ ' + chg_txt) if isinstance(chg, (int, float)) else ''}</span></p>
  <p class="muted">Report generated: {gen_time}</p>
</div>

<h2>Executive Summary</h2>
<p>{esc(exec_summary)}</p>

<h2>Snapshot Metrics</h2>
<div class="stat-grid">{snapshot_html}</div>

<h2>Business Summary</h2>
<p>{esc(detail.get('business_summary'))}</p>

<h2>Financial Health</h2>
<p><span class="badge" style="background:#f1f5f9">{esc(detail.get('risk_level'))} risk</span></p>
<p>{esc(detail.get('risk_detail'))}</p>
<table><tr><th>Ratio</th><th>Value</th></tr>{ratio_html}</table>

<h2>Financials Snapshot</h2>
{stmt_table("Profit & Loss", f.get('income') or {})}
{stmt_table("Balance Sheet", f.get('balance_sheet') or {})}
{stmt_table("Cash Flow", f.get('cashflow') or {})}

<h2>Peer Comparison</h2>
<table><tr><th>Company</th><th>Price</th><th>P/E</th></tr>{peer_html}</table>

<h2>Market Intelligence</h2>
<p><b>Sentiment:</b> {esc(detail.get('sentiment_score')) if detail.get('sentiment_score') is not None else 'AI-derived'} /100 ·
   <b>Analyst rating:</b> {esc(rec_txt)}{(' (' + esc(ab.get('analyst_count')) + ' analysts)') if ab.get('analyst_count') else ''} ·
   <b>Articles:</b> {nsc.get('positive', 0)} positive / {nsc.get('negative', 0)} negative / {nsc.get('neutral', 0)} neutral</p>
<ul>{cat_html}</ul>

<h2>12-Month Price Forecast</h2>
<table><tr><th>Current Price</th><th>Target</th><th>Expected Return</th><th>Direction</th></tr>
<tr><td class="num">₹{esc(detail.get('current_price'))}</td><td class="num">₹{fmt_num(detail.get('target_price'), ',.0f')}</td>
<td class="num">{(('%+.1f%%' % detail['expected_return']) if isinstance(detail.get('expected_return'), (int, float)) else 'N/A')}</td>
<td>{esc(detail.get('analyst_rating'))}</td></tr></table>
<p class="muted">{esc(fx.get('summary')) if fx.get('summary') else ''}</p>

<footer>
  <p><b>Disclaimer:</b> For academic/demonstration purposes only, not investment advice.</p>
  <p><b>Data sources:</b> yFinance, Google News RSS, Groq LLM, Isolation Forest model · Generated: {gen_time}</p>
</footer>
</body></html>"""


# ── Static frontend + path-based company URLs (refresh-safe tabs) ──
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PUBLIC_DIR = ROOT / "public"


@app.post("/api/download-report")
async def download_report(request: ReportRequest):
    """Full HTML research report compiled from the same live data as the tabs."""
    from fastapi.responses import Response
    try:
        detail = await get_company_research(request.ticker)
        if not detail.get("success"):
            return {"success": False, "detail": detail.get("error", "Pipeline failed")}

        exec_summary = _generate_exec_summary(detail, (detail.get("financials") or {}).get("ratios") or {})
        html_doc = _build_report_html(detail, exec_summary)

        from datetime import date as _date
        filename = f"{request.ticker.split('.')[0]}_research_report_{_date.today().isoformat()}.html"
        logger.info(f"Report generated for {request.ticker}: {filename}")
        return Response(
            content=html_doc,
            media_type="text/html",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.error(f"Report download failed: {e}", exc_info=True)
        return {"success": False, "detail": str(e)}


@app.get("/company/{symbol}")
@app.get("/company/{symbol}/{tab}")
async def company_page(symbol: str, tab: str = "overview"):
    """Serve the single live company page for path-based, refresh-safe tab URLs."""
    return FileResponse(PUBLIC_DIR / "company.html")


app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8502)
