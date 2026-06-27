"""Company Memory - Single source of truth for all company data."""

from __future__ import annotations

import json
from pathlib import Path


MEMORY_PATH = Path(__file__).resolve().parent / "company_memory.json"


def _is_valid_number(value):
    if value is None:
        return False
    try:
        if isinstance(value, str) and value.strip().lower() == "nan":
            return False
        return value == value
    except Exception:
        return False


def build_company_memory(agent1_output, agent2_output, agent3_output):
    """Build unified company memory from agent outputs."""
    agent1 = agent1_output or {}
    agent2 = agent2_output or {}
    agent3 = agent3_output or {}
    
    memory = {
        "company_info": _extract_company_info(agent1, agent2),
        "financial_metrics": _extract_financial_metrics(agent1, agent2),
        "financial_facts": agent2.get("financial_facts", {}),
        "peer_comparison": agent2.get("peer_comparison", {}),
        "anomaly_detection": _extract_anomaly_detection(agent2),
        "price_data": _extract_price_data(agent1),
        "chart_metrics": _extract_chart_metrics(agent1),
        "market_stats": _extract_market_stats(agent1),
        "market_metrics": _extract_market_stats(agent1),
        "market_drivers": agent1.get("market_drivers", {}),
        "website_context": agent1.get("website_context", {}),
        "risk_metrics": _extract_risk_metrics(agent1),
        "news_articles": _extract_news_articles(agent1, agent3),
        "news": _extract_news_articles(agent1, agent3),
        "events": agent3.get("recent_events", []),
        "market_facts": agent3.get("market_facts", {}),
        "analyst_data": agent1.get("analyst_data", {}),
        "risks": _normalize_list(agent3.get("risks", [])),
        "opportunities": _normalize_list(agent3.get("opportunities", [])),
        "market_intelligence": _extract_market_intelligence(agent3),
        "chart_artifacts": agent3.get("price_story", {}),
        "rag_context": agent3.get("rag_context", ""),
    }

    if not memory["risks"]:
        memory["risks"] = _derive_risks_from_memory(memory)
    if not memory["opportunities"]:
        memory["opportunities"] = _derive_opportunities_from_memory(memory)
    
    return memory


def save_company_memory(memory, path=MEMORY_PATH):
    """Persist the normalized memory snapshot to disk."""
    path = Path(path)
    path.write_text(json.dumps(memory, indent=2, ensure_ascii=True, default=str), encoding="utf-8")
    return path


def load_company_memory(path=MEMORY_PATH):
    """Load the persisted memory snapshot if it exists."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_company_info(agent1, agent2):
    info = agent1.get("company_info", {})
    summary = info.get("business_summary", "") or ""
    return {
        "name": info.get("company_name", ""),
        "ticker": agent1.get("ticker", ""),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "summary": summary,
        "business_model": _build_business_model(summary),
        "website": info.get("website", ""),
        "employees": info.get("employees", ""),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "dividend_yield": info.get("dividendYield"),
        "peers": _extract_peer_tickers(agent2),
        "return_on_equity": info.get("returnOnEquity"),
        "operating_margins": info.get("operatingMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "free_cashflow": info.get("freeCashflow"),
    }


def _extract_financial_metrics(agent1, agent2):
    info = (agent1 or {}).get("company_info", {})
    peer = agent2.get("peer_comparison", {})
    metrics = peer.get("metrics", {})
    facts = agent2.get("financial_facts", {})

    def get_val(key):
        entry = metrics.get(key, {})
        if isinstance(entry, dict):
            return entry.get("company")
        if key in facts:
            return facts.get(key)
        return None

    def first_available(*keys):
        for key in keys:
            value = get_val(key)
            if value is not None:
                return value
        return None

    def clean_number(value):
        if value is None:
            return None
        if isinstance(value, float) and isnan(value):
            return None
        return value

    return {
        "roce": clean_number(first_available("ROCE") or info.get("returnOnEquity")),
        "operating_margin": clean_number(first_available("OPM %", "OperatingMargin", "Operating Margin")),
        "net_margin": clean_number(first_available("Net Profit", "NetProfit")),
        "debt_to_equity": clean_number(first_available("Debt to Equity", "Debt") or info.get("debtToEquity")),
        "current_ratio": clean_number(first_available("Current Ratio", "CurrentRatio") or info.get("currentRatio")),
        "cash_flow": clean_number(first_available("Cash from Operating Activity", "CashFromOperatingActivity") or info.get("freeCashflow")),
        "sales": clean_number(first_available("Sales", "Revenue", "Total Revenue") or info.get("totalRevenue")),
    }


def _extract_anomaly_detection(agent2):
    red_flags = agent2.get("red_flags", [])
    model_assessment = agent2.get("model_assessment", {}) or {}
    anomaly_score = model_assessment.get("anomaly_score")

    return {
        "anomaly_score": anomaly_score,
        "model_assessment": model_assessment,
        "red_flags_count": len(red_flags),
        "red_flags": red_flags,
    }


def _extract_price_data(agent1):
    price = agent1.get("price_history", {})
    ohlcv = price.get("ohlcv", [])
    info = agent1.get("company_info", {})
    current = price.get("current_price")
    if not _is_valid_number(current):
        current = None
    if current is None:
        for candidate in (
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
            info.get("open"),
            info.get("dayHigh"),
            info.get("dayLow"),
            info.get("previousClose"),
            info.get("regularMarketPreviousClose"),
        ):
            if not _is_valid_number(candidate):
                continue
            current = candidate
            break

    high_52w = info.get("fiftyTwoWeekHigh") or price.get("week_52_high")
    low_52w = info.get("fiftyTwoWeekLow") or price.get("week_52_low")
    if not _is_valid_number(high_52w):
        high_52w = None
    if not _is_valid_number(low_52w):
        low_52w = None
    
    return {
        "current": current,
        "open": info.get("open"),
        "day_high": info.get("dayHigh"),
        "day_low": info.get("dayLow"),
        "high_52w": high_52w,
        "low_52w": low_52w,
        "avg_volume": price.get("average_volume"),
        "ohlcv_count": len(ohlcv),
        "ohlcv": ohlcv[-252:] if ohlcv else [],
    }


def _extract_market_stats(agent1):
    info = agent1.get("company_info", {})
    analyst = agent1.get("analyst_data", {})
    
    return {
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "target_price": analyst.get("target_mean_price") or analyst.get("targetMeanPrice"),
        "recommendation": analyst.get("recommendationKey") or analyst.get("recommendation_key"),
        "analyst_count": analyst.get("numberOfAnalystOpinions") or analyst.get("number_of_analysts"),
    }


def _extract_risk_metrics(agent1):
    price = agent1.get("price_history", {})
    ohlcv = price.get("ohlcv", [])
    
    if not ohlcv or len(ohlcv) < 20:
        return {}
    
    closes = []
    for row in ohlcv:
        close = row.get("close")
        if not _is_valid_number(close):
            continue
        closes.append(float(close))
    
    returns = []
    for i in range(1, len(closes)):
        if closes[i-1] != 0:
            ret = (closes[i] - closes[i-1]) / closes[i-1]
            returns.append(ret)
    
    if len(returns) < 2:
        return {}
    
    mean_return = sum(returns) / len(returns)
    variance = sum((x - mean_return) ** 2 for x in returns) / (len(returns) - 1)
    daily_volatility = variance ** 0.5
    annualized_volatility = daily_volatility * (252 ** 0.5) * 100
    
    max_price = max(closes)
    min_price = min(closes)
    current_price = closes[-1]
    max_drawdown = ((max_price - min_price) / max_price) * 100 if max_price else 0
    
    sharpe_ratio = None
    if annualized_volatility > 0:
        annualized_return = mean_return * 252 * 100
        risk_free_rate = 6.5
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    
    return {
        "annualized_volatility": round(annualized_volatility, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio else None,
        "beta": None,
    }


def _extract_chart_metrics(agent1):
    price = agent1.get("price_history", {})
    ohlcv = price.get("ohlcv", [])
    
    if not ohlcv or len(ohlcv) < 2:
        current = price.get("current_price")
        return {
            "returns": {},
            "volatility": None,
            "distance_from_52w_high": None,
            "distance_from_52w_low": None,
            "trend": "sideways",
            "moving_averages": {"50dma": None, "200dma": None},
            "support_resistance": {"support_1": None, "support_2": None, "resistance_1": None, "resistance_2": None},
            "current_price": current,
        }
    
    closes = []
    for row in ohlcv:
        close = row.get("close")
        if not _is_valid_number(close):
            continue
        closes.append(float(close))
    if len(closes) < 2:
        current = price.get("current_price")
        if not _is_valid_number(current):
            current = None
        return {
            "returns": {},
            "volatility": None,
            "distance_from_52w_high": None,
            "distance_from_52w_low": None,
            "trend": "sideways",
            "moving_averages": {"50dma": None, "200dma": None},
            "support_resistance": {"support_1": None, "support_2": None, "resistance_1": None, "resistance_2": None},
            "current_price": current,
        }
    start_price = closes[0]
    end_price = closes[-1]
    
    returns = {"1D": None, "1M": None, "6M": None, "1Y": None, "5Y": None}
    
    if len(closes) >= 2:
        returns["1D"] = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if closes[-2] else None
    if len(closes) >= 22:
        returns["1M"] = round((closes[-1] - closes[-22]) / closes[-22] * 100, 2) if closes[-22] else None
    if len(closes) >= 126:
        returns["6M"] = round((closes[-1] - closes[-126]) / closes[-126] * 100, 2) if closes[-126] else None
    if len(closes) >= 252:
        returns["1Y"] = round((closes[-1] - closes[-252]) / closes[-252] * 100, 2) if closes[-252] else None
    if len(closes) >= 1260:
        returns["5Y"] = round((closes[-1] - closes[-1260]) / closes[-1260] * 100, 2) if closes[-1260] else None
    
    daily_returns = []
    for i in range(1, len(closes)):
        if closes[i-1] != 0:
            ret = (closes[i] - closes[i-1]) / closes[i-1] * 100
            daily_returns.append(ret)
    
    if len(daily_returns) > 1:
        mean_ret = sum(daily_returns) / len(daily_returns)
        variance = sum((x - mean_ret) ** 2 for x in daily_returns) / (len(daily_returns) - 1)
        volatility = variance ** 0.5
    else:
        volatility = 0
    
    max_price = max(closes)
    min_price = min(closes)
    drawdown = (max_price - end_price) / max_price * 100 if max_price != 0 else 0
    distance_from_low = ((end_price - min_price) / min_price * 100) if min_price else 0
    
    if end_price > start_price * 1.05:
        trend = "up"
    elif end_price < start_price * 0.95:
        trend = "down"
    else:
        trend = "sideways"
    
    dma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    dma_200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    
    return {
        "returns": returns,
        "volatility": round(volatility, 2),
        "distance_from_52w_high": round(drawdown, 2),
        "distance_from_52w_low": round(distance_from_low, 2),
        "trend": trend,
        "moving_averages": {
            "50dma": round(dma_50, 2) if dma_50 is not None else None,
            "200dma": round(dma_200, 2) if dma_200 is not None else None,
        },
        "support_resistance": {
            "support_1": round(min(closes[-30:]) if len(closes) >= 30 else min(closes), 2),
            "support_2": round(min(closes) * 0.98, 2) if min(closes) is not None else None,
            "resistance_1": round(max(closes[-30:]) if len(closes) >= 30 else max(closes), 2),
            "resistance_2": round(max(closes) * 1.02, 2) if max(closes) is not None else None,
        },
        "current_price": end_price,
    }


def _extract_news_articles(agent1, agent3):
    articles = []
    
    agent1_news = agent1.get("news", {}).get("articles", [])
    for art in agent1_news[:10]:
        articles.append({
            "headline": art.get("title") or art.get("headline", ""),
            "summary": art.get("summary") or art.get("description", ""),
            "source": art.get("source") or art.get("publisher", "") or "Web",
            "url": art.get("url", ""),
            "date": art.get("date", ""),
            "sentiment": "neutral",
        })

    if not articles:
        for event in (agent3.get("recent_events") or [])[:10]:
            title = event.get("title") or event.get("headline")
            if title:
                articles.append({
                    "headline": title,
                    "summary": event.get("summary", ""),
                    "source": event.get("source", "agent3"),
                    "url": event.get("url", ""),
                    "date": event.get("date", ""),
                    "sentiment": event.get("sentiment", "neutral"),
                })

    for art in (agent3.get("supporting_articles") or [])[:10]:
        headline = art.get("title") or art.get("headline", "")
        if headline and not any(existing.get("headline") == headline for existing in articles):
            articles.append({
                "headline": headline,
                "summary": art.get("summary", ""),
                "source": art.get("source", "Web"),
                "url": art.get("url", ""),
                "date": art.get("date", ""),
                "sentiment": "neutral",
            })
    
    return articles


def _normalize_list(value):
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    return [value]


def _extract_market_intelligence(agent3):
    report = agent3.get("market_intelligence_report", {}) or {}
    return {
        "why_market_thinks_this": _normalize_list(agent3.get("why_market_thinks_this", [])),
        "recent_developments": report.get("recent_developments", ""),
        "market_perception": report.get("market_perception", ""),
        "positive_factors": _normalize_list(report.get("positive_factors", [])),
        "risk_factors": _normalize_list(report.get("risk_factors", [])),
        "bull_case": report.get("bull_case", ""),
        "base_case": report.get("base_case", ""),
        "bear_case": report.get("bear_case", ""),
        "key_catalysts": _normalize_list(report.get("key_catalysts", [])),
        "things_you_should_know": _normalize_list(report.get("things_you_should_know", [])),
        "price_snapshot": report.get("price_snapshot", {}),
    }


def _build_business_model(summary):
    text = (summary or "").lower()
    segments = []
    if any(k in text for k in ["telecom", "digital", "jio"]):
        segments.append("telecom and digital services")
    if "retail" in text:
        segments.append("consumer retail")
    if any(k in text for k in ["refining", "petrochemical", "oil", "hydrocarbon"]):
        segments.append("refining and petrochemicals")
    if any(k in text for k in ["renewable", "new energy", "solar", "green energy"]):
        segments.append("renewable energy")
    if not segments and summary:
        segments.append("a diversified mix of large operating businesses")
    return segments


def _extract_peer_tickers(agent2):
    peer = agent2.get("peer_comparison", {}) if isinstance(agent2, dict) else {}
    peers = peer.get("peers", [])
    out = []
    for item in peers or []:
        if isinstance(item, str) and item:
            out.append(item)
        elif isinstance(item, dict):
            ticker = item.get("ticker") or item.get("symbol") or item.get("name")
            if ticker:
                out.append(ticker)
    return out


def _derive_risks_from_memory(memory):
    risks = []
    metrics = memory.get("financial_metrics", {})
    chart = memory.get("chart_metrics", {})
    market = memory.get("market_stats", {})

    roce = metrics.get("roce")
    if roce is not None and roce < 10:
        risks.append(f"Low ROCE at {roce}% suggests weak capital efficiency.")

    dte = metrics.get("debt_to_equity")
    if dte is not None and dte >= 2:
        risks.append(f"Debt/Equity at {dte} points to higher leverage risk.")

    if chart.get("trend") == "down":
        risks.append("Price trend is down, which can signal weak momentum.")

    if chart.get("volatility") is not None and chart.get("volatility") > 3:
        risks.append("Elevated volatility increases near-term uncertainty.")

    pe = market.get("pe_ratio")
    if pe is not None and pe > 30:
        risks.append(f"Rich P/E of {pe} may limit valuation upside.")

    return risks[:4]


def _derive_opportunities_from_memory(memory):
    opps = []
    metrics = memory.get("financial_metrics", {})
    chart = memory.get("chart_metrics", {})
    market = memory.get("market_stats", {})

    roce = metrics.get("roce")
    if roce is not None and roce >= 15:
        opps.append(f"Strong ROCE at {roce}% shows efficient capital use.")

    opm = metrics.get("operating_margin")
    if opm is not None and opm >= 15:
        opps.append(f"Healthy operating margin of {opm}% supports profitability.")

    if chart.get("trend") == "up":
        opps.append("Positive price trend suggests momentum is supportive.")

    pe = market.get("pe_ratio")
    if pe is not None and pe < 20:
        opps.append(f"Reasonable P/E of {pe} may leave room for rerating.")

    if memory.get("news_articles"):
        opps.append("Recent news flow provides fresh catalysts to monitor.")

    drivers = memory.get("market_drivers", {})
    macro = drivers.get("macro", {})
    if macro.get("nifty50_return_1mo") is not None and macro.get("nifty50_return_1mo") > 0:
        opps.append("Broader market momentum is positive.")
    if drivers.get("sector_performance", {}).get("sector_return_1mo") is not None and drivers.get("sector_performance", {}).get("sector_return_1mo") > 0:
        opps.append("Sector trend is supportive.")

    return opps[:4]


def _extract_risks_opportunities(agent3):
    """Extract risks and opportunities from agent3 output."""
    return {
        "risks": agent3.get("risks", []),
        "opportunities": agent3.get("opportunities", []),
    }
