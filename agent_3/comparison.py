import re
from agent_3.market_synthesis import get_momentum

#gets a second ticker symbol from the user's query, excluding the primary ticker. It looks for common separators and patterns in the question to identify a potential second ticker for comparison.
def _find_second_ticker(question, primary):
    # look for common separators
    q = (question or "").upper()
    tokens = re.findall(r"\b[A-Z]{2,5}\b", q)
    # prefer tokens that are not the primary ticker
    candidates = [t for t in tokens if t != (primary or "").upper()]
    if candidates:
        return candidates[0]
    # try 'vs' or 'and' patterns
    m = re.search(r"\b(?:VS|V|VERSUS|AND)\b\s*([A-Z]{2,5})", q)
    if m:
        return m.group(1)
    return None


def compare_tickers(primary_ticker, question):
    """Return a minimal comparison between primary_ticker and another ticker found in the question."""
    other = _find_second_ticker(question, primary_ticker)
    if not other:
        return {}

    a = get_momentum(primary_ticker)
    b = get_momentum(other)

    # simple comparison based on 6m return when available
    a6 = a.get("6m_return") or a.get("6m_return")
    b6 = b.get("6m_return") or b.get("6m_return")

    conclusion = "insufficient data"
    try:
        if a6 is not None and b6 is not None:
            if a6 > b6:
                conclusion = f"{primary_ticker} has stronger 6M momentum than {other}."
            elif b6 > a6:
                conclusion = f"{other} has stronger 6M momentum than {primary_ticker}."
            else:
                conclusion = "Both tickers show similar 6M momentum."
    except Exception:
        pass

    return {
        "tickers": [primary_ticker, other],
        "momentum": {primary_ticker: a, other: b},
        "conclusion": conclusion,
    }
