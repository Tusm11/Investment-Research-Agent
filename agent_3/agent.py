import os

from dotenv import load_dotenv
from agent_3.event_classifier import extract_events
from agent_3.analyst_consensus import get_analyst_consensus
from agent_3.price_chart import create_price_chart
from agent_3.market_synthesis import synthesize_market
from agent_3.comparison import compare_tickers

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agent_1", ".env"))


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


def run_agent3(agent1_payload, question="", **_):
    ticker = agent1_payload.get("ticker")
    news = agent1_payload.get("news", {})
    price_data = agent1_payload.get("price_history", {})

    route = _route_query(question)

    events = []
    analyst_consensus = {}
    price_performance = {}
    rag_context = ""
    comparison_result = {}

    if route.get("news"):
        try:
            events = extract_events(news)
        except Exception as e:
            print(f"Agent3 event extraction failed: {e}")

    if route.get("analyst"):
        try:
            analyst_consensus = get_analyst_consensus(ticker)
        except Exception as e:
            print(f"Agent3 analyst consensus failed: {e}")

    if route.get("price"):
        try:
            events_for_chart = events if events else []
            price_performance = create_price_chart(ticker, price_data, events_for_chart)
        except Exception as e:
            print(f"Agent3 price chart failed: {e}")

    if route.get("rag"):
        try:
            from agent_3.rag import query_rag
            rag_query = f"Sector outlook, risks, opportunities for {ticker}. {question}"
            rag_context = query_rag(rag_query)
        except Exception as e:
            print(f"Agent3 RAG failed: {e}")

    if route.get("comparison"):
        try:
            comparison_result = compare_tickers(ticker, question)
        except Exception as e:
            print(f"Agent3 comparison failed: {e}")

    # simple sentiment heuristics (kept lightweight)
    sentiment = ""
    if route.get("analyst"):
        sentiment = "Bullish"
    if route.get("news") and not route.get("analyst"):
        sentiment = "Mixed"

    try:
        result = synthesize_market(
            ticker,
            events,
            analyst_consensus,
            price_performance,
            rag_context,
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
        "rag_context": rag_context,
        "market_facts": {
            "recommendation": analyst_consensus.get("recommendation_key") or analyst_consensus.get("recommendation"),
            "target_price": analyst_consensus.get("target_mean_price"),
            "analyst_count": analyst_consensus.get("number_of_analysts") or analyst_consensus.get("analysts_count"),
            "upside_downside_percent": analyst_consensus.get("upside_downside_percent"),
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
