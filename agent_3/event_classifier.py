import os
import joblib
import numpy as np

CATEGORIES = ["EARNINGS", "PRODUCT", "REGULATORY", "DIVIDEND", "STRATEGIC", "OTHER"]
SEED_TEXTS = {
    "EARNINGS": ["earnings", "quarter", "profit", "revenue", "results", "ebitda"],
    "PRODUCT": ["product", "launch", "platform", "service", "innovation"],
    "REGULATORY": ["sebi", "regulator", "approval", "penalty", "compliance", "investigation"],
    "DIVIDEND": ["dividend", "payout", "interim", "final dividend"],
    "STRATEGIC": ["acquisition", "merger", "partnership", "expansion", "investment", "deal"],
    "OTHER": ["market", "stock", "shares", "trading"],
}

_centroid_path = os.path.join(os.path.dirname(__file__), "event_kmeans.pkl")
_kmeans = None


def _keyword_category(text):
    lower = text.lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, words in SEED_TEXTS.items():
        for word in words:
            if word in lower:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "OTHER"


def _load_finbert_kmeans():
    return None


def _finbert_category(text):
    km = _load_finbert_kmeans()
    if km is None:
        return _keyword_category(text)

    try:
        vec = np.array([0.0] * 768).reshape(1, -1)
        cluster = int(km.predict(vec)[0])
        return CATEGORIES[cluster % len(CATEGORIES)]
    except Exception:
        return _keyword_category(text)


def _sentiment(text):
    lower = text.lower()
    pos = sum(w in lower for w in ["beat", "growth", "gain", "surge", "strong", "upgrade"])
    neg = sum(w in lower for w in ["miss", "fall", "drop", "weak", "cut", "downgrade", "penalty"])
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def extract_events(news_articles):
    events = []
    articles = news_articles.get("articles", []) if isinstance(news_articles, dict) else news_articles

    for article in articles:
        title = article.get("title") or article.get("headline") or ""
        summary = article.get("summary") or ""
        text = f"{title}. {summary}".strip()
        if not text:
            continue

        category = _finbert_category(text)

        events.append({
            "date": article.get("date"),
            "category": category,
            "title": title,
            "summary": summary[:200],
            "sentiment": _sentiment(text),
            "price_impact": None,
        })

    return events
