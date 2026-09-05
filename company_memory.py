"""Company Memory - Single source of truth for all company data."""

from __future__ import annotations

import json
import math
from pathlib import Path


MEMORY_PATH = Path(__file__).resolve().parent / "company_memory.json" #redirects the company data into the .json file in the same directory as this script


def _is_valid_number(value): #checks if the value is a valid number (not None, not NaN)
    if value is None:
        return False
    try:
        if isinstance(value, str) and value.strip().lower() == "nan":
            return False
        return value == value
    except Exception:
        return False


def build_company_memory(agent1_output, agent2_output, agent3_output): #builds a collected memory of company data from the outputs of three agents
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
        "market_drivers": agent1.get("market_drivers", {}),
        "website_context": agent1.get("website_context", {}),
        "risk_metrics": _extract_risk_metrics(agent1),
        "news_articles": _extract_news_articles(agent1, agent3),
        "events": agent3.get("recent_events", []),
        "market_facts": agent3.get("market_facts", {}),
        "analyst_data": agent1.get("analyst_data", {}),
        "risks": _normalize_list(agent3.get("risks", [])),
        "opportunities": _normalize_list(agent3.get("opportunities", [])),
        "market_intelligence": _extract_market_intelligence(agent3),
        "chart_artifacts": agent3.get("price_story", {}),
        "rag_context": agent3.get("rag_context", ""),
        "dashboard": {
            "business_fundamentals": _extract_business_fundamentals(agent1, agent2),
            "market_mood": _extract_market_mood(agent1, agent2, agent3),
            "price_story": _extract_price_story(agent1),
            "financial_stability": _extract_financial_stability(agent2),
        },
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
    return path #indent=2 makes the JSON file more readable, ensure_ascii=True ensures that non-ASCII characters are escaped, and default=str allows serialization of non-standard types by converting them to strings.


def load_company_memory(path=MEMORY_PATH): #loads the selected memory snapshot from disk if it exists, otherwise returns an empty dictionary
    """Load the persisted memory snapshot if it exists."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_company_info(agent1, agent2): #extracts basic company information from agent1 and agent2 outputs
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


def _extract_financial_metrics(agent1, agent2):#extracts key financial metrics from agent1 and agent2 outputs
    info = (agent1 or {}).get("company_info", {})
    peer = agent2.get("peer_comparison", {})
    metrics = peer.get("metrics", {})
    facts = agent2.get("financial_facts", {})
 
    def get_val(key):#helper function to retrieve a value for a given key from metrics or facts
        entry = metrics.get(key, {})
        if isinstance(entry, dict):
            return entry.get("company")
        if key in facts:
            return facts.get(key)
        return None

    def first_available(*keys):#helper function to return the first available value for a list of keys
        for key in keys:
            value = get_val(key)
            if value is not None:
                return value
        return None

    def clean_number(value):#helper function to clean and validate a number, returning None for invalid values like None or NaN
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    return { #returns a dictionary of cleaned financial metrics
        "roce": clean_number(first_available("ROCE") or info.get("returnOnEquity")),
        "operating_margin": clean_number(first_available("OPM %", "OperatingMargin", "Operating Margin")),
        "net_margin": clean_number(first_available("Net Profit", "NetProfit")),
        "debt_to_equity": clean_number(first_available("Debt to Equity", "Debt") or info.get("debtToEquity")),
        "current_ratio": clean_number(first_available("Current Ratio", "CurrentRatio") or info.get("currentRatio")),
        "cash_flow": clean_number(first_available("Cash from Operating Activity", "CashFromOperatingActivity") or info.get("freeCashflow")),
        "sales": clean_number(first_available("Sales", "Revenue", "Total Revenue") or info.get("totalRevenue")),
    }


def _extract_anomaly_detection(agent2): #extracts anomaly detection results from agent2 output
    red_flags = agent2.get("red_flags", [])
    model_assessment = agent2.get("model_assessment", {}) or {}
    anomaly_score = model_assessment.get("anomaly_score")

    return {
        "anomaly_score": anomaly_score,
        "model_assessment": model_assessment,
        "red_flags_count": len(red_flags),
        "red_flags": red_flags,
    }


def _extract_price_data(agent1):#extracts price data and related metrics from agent1 output
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

    high_52w = info.get("fiftyTwoWeekHigh") or price.get("week_52_high") #gets the 52-week high and low prices from either agent1's company info or price history
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


def _extract_market_stats(agent1):#extracts market statistics and analyst data from agent1 output
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


def _extract_risk_metrics(agent1):#extracts risk metrics such as annualized volatility, max drawdown, and Sharpe ratio from agent1's price history
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
    for i in range(1, len(closes)):#calculates daily returns based on closing prices
        if closes[i-1] != 0:
            ret = (closes[i] - closes[i-1]) / closes[i-1]
            returns.append(ret)
    
    if len(returns) < 2:
        return {}
    
    mean_return = sum(returns) / len(returns)#calculates the mean of daily returns
    variance = sum((x - mean_return) ** 2 for x in returns) / (len(returns) - 1)#calculates the variance of daily returns
    daily_volatility = variance ** 0.5#calculates the standard deviation (volatility) of daily returns
    annualized_volatility = daily_volatility * (252 ** 0.5) * 100#annualizes the daily volatility to get annualized volatility in percentage terms
    
    max_price = max(closes) #finds the maximum and minimum closing prices to calculate max drawdown
    min_price = min(closes) 
    current_price = closes[-1]#gets the current price (most recent closing price)
    max_drawdown = ((max_price - min_price) / max_price) * 100 if max_price else 0
    #its necessary to check if max_price is not zero to avoid division by zero error. If max_price is zero, max_drawdown is set to 0.
    #sharpe ratio is calculated using the annualized return, risk-free rate, and annualized volatility. The risk-free rate is assumed to be 6.5%. If the annualized volatility is greater than zero, the Sharpe ratio is computed; otherwise, it remains None.
    sharpe_ratio = None #calculates the Sharpe ratio if annualized volatility is greater than zero
    if annualized_volatility > 0: #sharpe ration is a measure of risk-adjusted return, calculated as (annualized return - risk-free rate) / annualized volatility. The risk-free rate is assumed to be 6.5% no matter what the actual risk-free rate is, which may not be accurate in all market conditions.
        annualized_return = mean_return * 252 * 100
        risk_free_rate = 6.5
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
    
    return {
        "annualized_volatility": round(annualized_volatility, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio else None,
        "beta": None,
    }


def _extract_chart_metrics(agent1):#extracts chart metrics such as returns, volatility, trend, moving averages, and support/resistance levels from agent1's price history
    price = agent1.get("price_history", {})
    ohlcv = price.get("ohlcv", [])
    
    # Store full OHLCV for chart rendering
    chart_metrics = {
        "ohlcv_full": ohlcv if ohlcv else [],
    }
    
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
    
    returns = {"1D": None, "1M": None, "6M": None, "1Y": None, "5Y": None, "MAX": None}
    
    if len(closes) >= 2:#calculates returns over different time periods based on closing prices
        returns["1D"] = round((closes[-1] - closes[-2]) / closes[-2] * 100, 2) if closes[-2] else None
    if len(closes) >= 22:
        returns["1M"] = round((closes[-1] - closes[-22]) / closes[-22] * 100, 2) if closes[-22] else None
    if len(closes) >= 126:
        returns["6M"] = round((closes[-1] - closes[-126]) / closes[-126] * 100, 2) if closes[-126] else None
    if len(closes) >= 252:
        returns["1Y"] = round((closes[-1] - closes[-252]) / closes[-252] * 100, 2) if closes[-252] else None
    if len(closes) >= 1260:
        returns["5Y"] = round((closes[-1] - closes[-1260]) / closes[-1260] * 100, 2) if closes[-1260] else None
    # MAX return: from first available price to current
    if len(closes) >= 2:
        returns["MAX"] = round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else None
    
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
    
    if end_price > start_price * 1.05:#determines the trend based on the start and end prices and is multiplied by 1.05 to account for a 5% threshold for an upward trend, and by 0.95 for a downward trend. If the end price is within 5% of the start price, the trend is considered sideways.
        trend = "up" #this is done to avoid classifying minor fluctuations as a trend, and to focus on more significant price movements.
    elif end_price < start_price * 0.95:
        trend = "down"
    else:
        trend = "sideways"
    
    dma_50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None #calculates the 50-day and 200-day moving averages based on the closing prices. If there are fewer than 50 or 200 closing prices, the respective moving average is set to None.
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
        "ohlcv_full": chart_metrics["ohlcv_full"],
    }


def _extract_news_articles(agent1, agent3):# extracts news articles from agent1 and agent3 outputs, prioritizing agent1's news if available, and falling back to agent3's recent events and supporting articles if necessary
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
            title = event.get("title") or event.get("headline") #gets the title or headline of the event, and if it exists, appends it to the articles list with relevant details such as summary, source, URL, date, and sentiment.
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
    if not value:#if the value is None or empty, return an empty list
        return []
    if isinstance(value, list):
        return [item for item in value if item]
    return [value]


def _extract_market_intelligence(agent3): #extracts market intelligence report and related insights from agent3 output, normalizing lists and providing default values for missing fields
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


def _build_business_model(summary): #builds a list of business segments based on keywords found in the company summary, returning a default segment if none are identified
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


def _extract_peer_tickers(agent2):#extracts peer tickers from agent2 output, handling both string and dictionary formats, and returning a list of valid tickers
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


def _derive_risks_from_memory(memory):#derives a list of potential risks based on financial metrics, chart trends, and market statistics from the company memory, returning a maximum of four identified risks
    risks = []
    metrics = memory.get("financial_metrics", {})
    chart = memory.get("chart_metrics", {})
    market = memory.get("market_stats", {})

    roce = metrics.get("roce") #these ranges are based on 
    if roce is not None and roce < 10:
        risks.append(f"Low ROCE at {roce}% suggests weak capital efficiency.")

    dte = metrics.get("debt_to_equity")
    if dte is not None and dte >= 1.2:
        risks.append(f"Debt/Equity at {dte} points to higher leverage risk.")

    if chart.get("trend") == "down":
        risks.append("Price trend is down, which can signal weak momentum.")

    if chart.get("volatility") is not None and chart.get("volatility") > 3:
        risks.append("Elevated volatility increases near-term uncertainty.")

    pe = market.get("pe_ratio")
    if pe is not None and pe > 35:
        risks.append(f"Rich P/E of {pe} may limit valuation upside.")

    return risks[:4]

#erives a list of potential opportunities based on financial metrics, chart trends, and market statistics from the company memory, returning a maximum of four identified opportunities
def _derive_opportunities_from_memory(memory):
    opps = []
    metrics = memory.get("financial_metrics", {})
    chart = memory.get("chart_metrics", {})
    market = memory.get("market_stats", {})

    roce = metrics.get("roce")
    if roce is not None and roce >= 10:
        opps.append(f"Strong ROCE at {roce}% shows efficient capital use.")

    opm = metrics.get("operating_margin")
    if opm is not None and opm >= 15:
        opps.append(f"Healthy operating margin of {opm}% supports profitability.")

    if chart.get("trend") == "up":
        opps.append("Positive price trend suggests momentum is supportive.")

    pe = market.get("pe_ratio")
    if pe is not None and pe < 35:
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

#extracts risks and opportunities from agent3 output, returning them as a dictionary with default empty lists if not present
def _extract_risks_opportunities(agent3):
    """Extract risks and opportunities from agent3 output."""
    return {
        "risks": agent3.get("risks", []),
        "opportunities": agent3.get("opportunities", []),
    }


def _extract_business_fundamentals(agent1, agent2):
    """Extract business fundamentals summary for dashboard."""
    info = agent1.get("company_info", {})
    peer = agent2.get("peer_comparison", {})
    metrics = agent2.get("financial_facts", {})
    red_flags = agent2.get("red_flags", [])
    
    roce = metrics.get("ROCE")
    debt = metrics.get("Debt")
    opm = metrics.get("OperatingMargin")
    
    strengths = []
    watch_items = []
    
    # Strengths
    if roce and roce >= 10:
        strengths.append("Acceptable ROCE performance")
    if roce and roce >= 15:
        strengths.append("Strong capital efficiency")
    if opm and opm >= 10:
        strengths.append("Healthy operating margins")
    if debt and isinstance(debt, (int, float)) and debt < 1:
        strengths.append("Conservative debt levels")
    if info.get("business_summary"):
        summary = info.get("business_summary", "").lower()
        if any(k in summary for k in ["diversified", "multiple", "various"]):
            strengths.append("Diversified business model")
    
    # Watch items
    if roce and roce < 10:
        watch_items.append("Low ROCE - below 10%")
    if debt and isinstance(debt, (int, float)) and debt > 2:
        watch_items.append("High debt levels")
    if opm and opm < 10:
        watch_items.append("Low operating margins")
    for flag in red_flags[:3]:
        watch_items.append(flag.get("explanation", flag.get("metric", "Financial concern")))
    
    if not strengths:
        strengths.append("Stable financial position")
    
    return {
        "overall": "Moderate" if roce and 10 <= roce < 15 else ("Strong" if roce and roce >= 15 else "Weak"),
        "strengths": strengths[:4],
        "watch_items": watch_items[:4],
        "summary": f"{info.get('company_name', 'This company')} has {'strong financial fundamentals' if strengths and not watch_items else 'acceptable financial fundamentals with some areas to monitor'}.",
    }


def _extract_market_mood(agent1, agent2, agent3):
    """Extract market mood summary for dashboard."""
    # ponytail: rules-based sentiment for page load speed. AI sentiment only in chat (RAG)
    analyst = agent1.get("analyst_data", {})
    news = agent3.get("recent_events", [])
    chart = agent1.get("price_history", {})
    info = agent1.get("company_info", {})
    
    recommendation = analyst.get("recommendation_key") or analyst.get("recommendationKey", "hold")
    
    positive_signals = []
    risk_factors = []
    
    if recommendation in ["buy", "strong_buy"]:
        positive_signals.append("Analyst consensus is positive")
    elif recommendation in ["sell", "underperform"]:
        risk_factors.append("Analyst consensus is negative")
    
    # Check news sentiment
    positive_count = sum(1 for n in news if (n.get("sentiment") or "").lower() == "positive")
    negative_count = sum(1 for n in news if (n.get("sentiment") or "").lower() == "negative")
    
    if positive_count > negative_count:
        positive_signals.append("Positive news sentiment")
    elif negative_count > positive_count:
        risk_factors.append("Negative news sentiment")
    
    # Price trend
    ohlcv = chart.get("ohlcv", [])
    if len(ohlcv) >= 2:
        trend = "up" if ohlcv[-1].get("close", 0) > ohlcv[-2].get("close", 0) else "down" if ohlcv[-1].get("close", 0) < ohlcv[-2].get("close", 0) else "sideways"
        if trend == "up":
            positive_signals.append("Positive price momentum")
        elif trend == "down":
            risk_factors.append("Negative price momentum")
    
    overall_sentiment = "Positive" if positive_signals and not risk_factors else ("Negative" if risk_factors and not positive_signals else "Mixed")
    
    summary_parts = []
    if positive_signals and not risk_factors:
        summary_parts.append("Market sentiment is constructive")
    elif risk_factors and not positive_signals:
        summary_parts.append("Market sentiment is cautious")
    else:
        summary_parts.append("Market sentiment is mixed")
    
    if analyst.get("target_mean_price"):
        current = analyst.get("current_price") or info.get("currentPrice")
        target = analyst.get("target_mean_price")
        if current and target:
            upside = ((target - current) / current) * 100 if current else 0
            summary_parts.append(f"Analyst target implies {upside:.1f}% upside")
    
    return {
        "overall_sentiment": overall_sentiment,
        "positive_factors": positive_signals[:3],
        "areas_to_watch": risk_factors[:3],
        "market_focus": [],
        "status": "Positive" if positive_signals and not risk_factors else ("Negative" if risk_factors and not positive_signals else "Mixed"),
        "positive_signals": positive_signals[:3],
        "risks": risk_factors[:3],
        "summary": ". ".join(summary_parts) + ".",
    }

#price story gets the current price, 52-week high and low, calculates the percentage below the 52-week high, determines the price trend, and identifies support and resistance levels based on recent closing prices. It returns a summary of these metrics for dashboard display.
def _extract_price_story(agent1):
    """Extract price story summary for dashboard."""
    price = agent1.get("price_history", {})
    info = agent1.get("company_info", {})
    chart = _extract_chart_metrics(agent1) if agent1 else {}
    
    current = price.get("current_price") or info.get("currentPrice") or info.get("regularMarketPrice")
    high_52w = info.get("fiftyTwoWeekHigh") or price.get("week_52_high")
    low_52w = info.get("fiftyTwoWeekLow") or price.get("week_52_low")
    
    if current and high_52w and high_52w != 0:
        below_high = ((high_52w - current) / high_52w) * 100
    else:
        below_high = None
    
    ohlcv = price.get("ohlcv", [])
    trend = "sideways"
    if len(ohlcv) >= 2:
        if ohlcv[-1].get("close", 0) > ohlcv[-2].get("close", 0):
            trend = "up"
        elif ohlcv[-1].get("close", 0) < ohlcv[-2].get("close", 0):
            trend = "down"
    
    support = min(c.get("close", 0) for c in ohlcv[-30:]) if len(ohlcv) >= 30 else None
    resistance = max(c.get("close", 0) for c in ohlcv[-30:]) if len(ohlcv) >= 30 else None
    
    summary_parts = []
    if below_high is not None:
        summary_parts.append(f"₹{current:,.2f} is {below_high:.1f}% below 52-week high")
    summary_parts.append(f"Price trend is {trend}")
    
    if support and resistance:
        summary_parts.append(f"Support: ₹{support:,.2f}, Resistance: ₹{resistance:,.2f}")
    
    return {
        "summary": ". ".join(summary_parts) + ".",
        "trend": trend,
        "support": support,
        "resistance": resistance,
        "current_price": current,
        "distance_from_52w_high": round(below_high, 2) if below_high else None,
    }

#extracts financial stability assessment based on key metrics such as ROCE, debt levels, current ratio, cash flow, and any red flags identified. It provides a status, summary, and reasoning for the assessment to be displayed on the dashboard.
def _extract_financial_stability(agent2):
    """Extract financial stability assessment for dashboard."""
    metrics = agent2.get("financial_facts", {})
    peer = agent2.get("peer_comparison", {})
    red_flags = agent2.get("red_flags", [])
    
    roce = metrics.get("ROCE")
    debt = metrics.get("Debt")
    current_ratio = metrics.get("CurrentRatio")
    cash_flow = metrics.get("CashFromOperatingActivity")
    
    reasons = []
    
    if roce and roce >= 15:
        reasons.append("Strong returns on capital")
    elif roce and roce < 10:
        reasons.append("Weak returns on capital")
    
    if debt and isinstance(debt, (int, float)) and debt < 1:
        reasons.append("Low debt levels")
    elif debt and isinstance(debt, (int, float)) and debt > 2:
        reasons.append("High debt levels")
    
    if current_ratio and isinstance(current_ratio, (int, float)) and current_ratio >= 1.5:
        reasons.append("Strong liquidity position")
    elif current_ratio and isinstance(current_ratio, (int, float)) and current_ratio < 1.2:
        reasons.append("Liquidity concerns")
    
    if cash_flow and isinstance(cash_flow, (int, float)) and cash_flow > 0:
        reasons.append("Healthy cash generation")
    elif cash_flow and isinstance(cash_flow, (int, float)) and cash_flow < 0:
        reasons.append("Negative cash flow")
    
    for flag in red_flags[:2]:
        reasons.append(flag.get("explanation", flag.get("metric", "Financial concern")))
    
    if not reasons:
        reasons.append("Stable financial profile")
    
    if any("weak" in r.lower() or "high" in r.lower() or "concern" in r.lower() for r in reasons):
        status = "Watch"
        summary = "Financial stability requires monitoring"
    elif any("strong" in r.lower() or "healthy" in r.lower() for r in reasons):
        status = "Strong"
        summary = "Financially stable with solid fundamentals"
    else:
        status = "Moderate"
        summary = "Financially stable with some areas to watch"
    
    return {
        "status": status,
        "summary": summary,
        "reasoning": reasons,
    }
