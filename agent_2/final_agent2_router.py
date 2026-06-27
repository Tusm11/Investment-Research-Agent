def route_query(question, ticker=None):
    """Route query to determine intent and modules."""
    import re
    
    t = (question or "").lower()
    
    if "compare" in t or "versus" in t or "vs" in t:
        intent = "compare"
        modules = ["fundamentals", "peer_comparison", "events", "sentiment"]
    elif "next " in t and ("year" in t or "5" in t) or ("will" in t and "do well" in t):
        intent = "future_outlook"
        modules = ["fundamentals", "events", "sentiment", "future_outlook"]
    elif "happen" in t or "update" in t or "recent" in t or "what's" in t:
        intent = "events"
        modules = ["events"]
    elif "market think" in t or "sentiment" in t or "analyst" in t:
        intent = "market_sentiment"
        modules = ["events", "sentiment", "analyst_consensus"]
    elif "financial" in t and ("strong" in t or "health" in t):
        intent = "financial_strength"
        modules = ["fundamentals", "peer_comparison", "red_flags"]
    elif "chart" in t or "graph" in t or "price" in t:
        intent = "price_chart"
        modules = ["price_visualization"]
    elif "analyz" in t or ("what" in t and "about" in t):
        intent = "full_analysis"
        modules = ["fundamentals", "peer_comparison", "red_flags", "events", "sentiment", "future_outlook"]
    else:
        intent = "full_analysis"
        modules = ["fundamentals", "peer_comparison", "red_flags", "events", "sentiment", "future_outlook"]
    
    return {
        "intent": intent,
        "modules": modules,
    }
