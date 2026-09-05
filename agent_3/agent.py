import os

from dotenv import load_dotenv
from agent_3.event_classifier import extract_events
from agent_3.analyst_consensus import get_analyst_consensus
from agent_3.price_chart import create_price_chart
from agent_3.market_synthesis import synthesize_market
from agent_3.comparison import compare_tickers

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

#route_query function analyzes the research question to determine which aspects of market intelligence are relevant, returning a dictionary indicating whether to focus on news, analyst consensus, price performance, risks and opportunities, comparisons, or future outlook.
def _route_query(question):
    text = (question or "").lower()
    return {
        "news": any(term in text for term in ("news", "event", "events", "developments", "happening")),
        "analyst": any(term in text for term in ("buy", "sell", "hold", "analyst", "target", "sentiment")),
        "price": any(term in text for term in ("chart", "trend", "price", "history", "6 months", "6 month")),
        "rag": any(term in text for term in ("outlook", "risks", "opportunities", "sector")),
        "comparison": any(term in text for term in ("compare", "vs", "versus")),
        "future": any(term in text for term in ("future", "outlook", "forecast", "will it")),
    }

#run_agent3 function processes the output from Agent 1, extracting relevant market intelligence based on the research question. It gathers news events, analyst consensus, price performance, and comparisons, synthesizes this information into a market intelligence report, and formats the output with supporting articles and key insights for further analysis.
def run_agent3(agent1_payload, question="", **_): # **_ allows for additional unused keyword arguments which can be passed without causing errors
    ticker = agent1_payload.get("ticker")
    news = agent1_payload.get("news", {})
    price_data = agent1_payload.get("price_history", {})

    route = _route_query(question)

    # Company-specific analysis must always populate the core intelligence
    # sections; keyword routing only adds extras like comparison/future outlook.
    if not any(route.values()):
        route.update({"news": True, "analyst": True, "price": True})

    events = []
    analyst_consensus = {}
    price_performance = {}
    comparison_result = {}

    if route.get("news"):
        try:
            events = extract_events(news)
        except Exception as e:
            print(f"Agent3 event extraction failed: {e}")
            events = []

    if route.get("analyst"):
        try:
            analyst_consensus = get_analyst_consensus(ticker)
        except Exception as e:
            print(f"Agent3 analyst consensus failed: {e}")
            analyst_consensus = {}

    if route.get("price"):
        try:
            events_for_chart = events if events else []
            price_performance = create_price_chart(ticker, price_data, events_for_chart)
        except Exception as e:
            print(f"Agent3 price chart failed: {e}")
            price_performance = {}

    if route.get("comparison"):
        try:
            comparison_result = compare_tickers(ticker, question)
        except Exception as e:
            print(f"Agent3 comparison failed: {e}")
            comparison_result = {}

    # Determine sentiment based on actual data (not defaults)
    sentiment = None
    if analyst_consensus:
        rec = (analyst_consensus.get("recommendation_key") or analyst_consensus.get("recommendation") or "hold").lower().replace("_", " ")
        if rec in ("buy", "strong buy", "overweight"):
            sentiment = "Bullish"
        elif rec in ("sell", "strong sell", "underweight"):
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
    
    if events and not sentiment:
        positive_count = sum(1 for e in events if (e.get("sentiment") or "").lower() == "positive")
        negative_count = sum(1 for e in events if (e.get("sentiment") or "").lower() == "negative")
        if positive_count > negative_count:
            sentiment = "Bullish"
        elif negative_count > positive_count:
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
    
    # If we have no data to determine sentiment, leave it as None
    # (This will be different from the hardcoded 50)

    try:
        result = synthesize_market(
            ticker,
            events,
            analyst_consensus,
            price_performance,
            "",
            question,
            need_future=route.get("future", False)
        )
    except Exception as e:
        print(f"Agent3 synthesis failed: {e}")
        result = {"intelligence_report": "Market intelligence unavailable."}

    intelligence_report = result.get("intelligence_report")
    if not isinstance(intelligence_report, dict):
        intelligence_report = {}

    # Build supporting articles from agent1 payload (top 3)
    supporting_articles = []
    try:
        articles = (agent1_payload or {}).get("news", {}).get("articles", [])
        for art in (articles or [])[:5]:
            supporting_articles.append({
                "title": art.get("title") or art.get("headline"),
                "source": art.get("source") or art.get("publisher") or "web",
                "url": art.get("url"),
                "summary": art.get("summary") or "",
            })
    except Exception:
        supporting_articles = []

    if not supporting_articles:
        for event in events[:5]:
            title = event.get("title") or event.get("headline")
            if title:
                supporting_articles.append({
                    "title": title,
                    "source": "agent3",
                    "url": "",
                    "summary": event.get("summary", ""),
                    "date": event.get("date", ""),
                })

    # Map existing intelligence report into new schema
    return {
        "ticker": ticker,
        "sentiment": sentiment,
        "market_intelligence_report": intelligence_report,
        "price_story": price_performance,
        "market_facts": {
            "recommendation": analyst_consensus.get("recommendation_key") or analyst_consensus.get("recommendation"),
            "target_price": analyst_consensus.get("target_mean_price") or analyst_consensus.get("price_target"),
            "analyst_count": analyst_consensus.get("number_of_analysts") or analyst_consensus.get("analysts_count"),
            "upside_downside_percent": analyst_consensus.get("upside_downside_percent"),
            "buy": analyst_consensus.get("buy"),
            "hold": analyst_consensus.get("hold"),
            "sell": analyst_consensus.get("sell"),
            "articles_positive": sum(1 for e in events if (e.get("sentiment") or "").lower() == "positive"),
            "articles_negative": sum(1 for e in events if (e.get("sentiment") or "").lower() == "negative"),
            "articles_neutral": sum(1 for e in events if (e.get("sentiment") or "").lower() == "neutral"),
        },
        "why_market_thinks_this": intelligence_report.get("market_perception") and [intelligence_report.get("market_perception")] or [],
        "recent_events": events,
        "risks": intelligence_report.get("risk_factors", []),
        "opportunities": intelligence_report.get("positive_factors", []),
        "catalysts": intelligence_report.get("key_catalysts", []),
        "future_outlook": intelligence_report.get("base_case") or intelligence_report.get("bull_case") or intelligence_report.get("bear_case") or "",
        "supporting_articles": supporting_articles,
    }
