import os
import yfinance as yf
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agent_1", ".env"))


def format_events(events):
    """Format events for prompt."""
    if not events:
        return "No recent events"
    lines = []
    for event in events[:8]:
        title = event.get("title", "")
        category = event.get("category", "OTHER")
        lines.append(f"- {category}: {title}")
    return "\n".join(lines) if lines else "No events"


def format_analyst(data):
    """Format analyst data for prompt."""
    if not data:
        return "No analyst data"
    rec = data.get("recommendation", "hold").upper()
    count = data.get("analysts_count", data.get("analysts", 0))
    target = data.get("price_target") or data.get("target_mean_price")
    current = data.get("current_price")
    upside = "N/A"
    if target and current and current != 0:
        try:
            upside = f"{round(((float(target) - float(current)) / float(current)) * 100, 1)}%"
        except Exception:
            upside = "N/A"
    return f"Recommendation: {rec} | Analysts: {count} | Target: {target} | Current: {current} | Upside: {upside}"


def format_price(data):
    """Format price data for prompt."""
    if not data:
        return "No price data"
    ret_1m = data.get("1m_return") or data.get("1mo_return") or "N/A"
    ret_3m = data.get("3m_return") or data.get("3mo_return") or "N/A"
    ret_6m = data.get("6m_return") or data.get("6mo_return") or "N/A"
    vol = data.get("volatility", "N/A")
    return f"1M: {ret_1m}% | 3M: {ret_3m}% | 6M: {ret_6m}% | Volatility: {vol}%"


def default_intelligence():
    return {
        "recent_developments": "Analysis unavailable",
        "market_perception": "Unable to process",
        "positive_factors": [],
        "risk_factors": [],
        "bull_case": "N/A",
        "bear_case": "N/A",
        "key_catalysts": []
    }


def _build_momentum(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="6mo")
        if hist.empty:
            return {}

        prices = hist["Close"]
        current = float(prices.iloc[-1])

        def ret(days):
            if len(prices) >= days:
                return round(((current - float(prices.iloc[-days])) / float(prices.iloc[-days])) * 100, 2)
            return None

        returns = prices.pct_change().dropna()
        volatility = round(float(returns.std()) * 100, 2) if not returns.empty else None

        return {
            "1m_return": ret(21),
            "3m_return": ret(63),
            "6m_return": ret(126),
            "current_price": round(current, 2),
            "volatility": volatility,
        }
    except Exception as e:
        print(f"Momentum fetch failed: {e}")
        return {}


def get_momentum(ticker):
    """Public wrapper to fetch simple momentum stats for a ticker."""
    return _build_momentum(ticker)


def synthesize_market(ticker, events, analyst_consensus, price_performance, rag_context, question, need_future):
    momentum = _build_momentum(ticker) if price_performance else {}
    event_titles = [event.get("title") or event.get("headline") for event in events if event]
    event_titles = [title for title in event_titles if title]

    analyst = format_analyst(analyst_consensus)
    price = format_price(momentum)
    developments = format_events(events)

    positive_factors = []
    risk_factors = []

    if analyst_consensus.get("upside_downside_percent") not in (None, ""):
        upside = analyst_consensus.get("upside_downside_percent")
        if upside >= 0:
            positive_factors.append(f"Analyst upside near {upside}%")
        else:
            risk_factors.append(f"Analyst downside near {abs(upside)}%")

    if momentum.get("3m_return") is not None:
        if momentum["3m_return"] >= 0:
            positive_factors.append(f"3M return {momentum['3m_return']}%")
        else:
            risk_factors.append(f"3M return {momentum['3m_return']}%")

    if event_titles:
        positive_factors.append(event_titles[0])

    # Only add placeholders if we have no real data
    if not positive_factors and not analyst_consensus and not momentum:
        positive_factors = []
    if not risk_factors and not analyst_consensus and not momentum:
        risk_factors = []

    report = {
        "recent_developments": developments,
        "market_perception": analyst,
        "positive_factors": positive_factors[:3] if positive_factors else [],
        "risk_factors": risk_factors[:3] if risk_factors else [],
        "bull_case": "Momentum improves if recent strength continues." if need_future else "Bull case not requested.",
        "base_case": "The stock looks stable based on the current inputs.",
        "bear_case": "Weak momentum or negative upside can keep pressure on the stock." if need_future else "Bear case not requested.",
        "key_catalysts": event_titles[:3] if event_titles else [],
        "things_you_should_know": [question or "No extra notes."],
        "price_snapshot": price,
    }

    return {"intelligence_report": report}
