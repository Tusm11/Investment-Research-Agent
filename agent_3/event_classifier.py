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
_finbert_ready = False


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
    global _kmeans, _finbert_ready
    if _kmeans is not None:
        return _kmeans

    if os.path.exists(_centroid_path):
        _kmeans = joblib.load(_centroid_path)
        _finbert_ready = True
        return _kmeans

    if os.getenv("FINBERT_EVENTS", "0") != "1":
        return None

    try:
        from sklearn.cluster import KMeans
        from transformers import AutoTokenizer, AutoModel
        import torch

        model_name = "ProsusAI/finbert"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModel.from_pretrained(model_name)
        model.eval()

        vectors = []
        for cat in CATEGORIES:
            seed = " ".join(SEED_TEXTS[cat])
            inputs = tokenizer(seed, return_tensors="pt", truncation=True, max_length=128)
            with torch.no_grad():
                outputs = model(**inputs)
            vectors.append(outputs.last_hidden_state[:, 0, :].numpy()[0])

        km = KMeans(n_clusters=len(CATEGORIES), random_state=42, n_init=10)
        km.fit(np.array(vectors))
        joblib.dump(km, _centroid_path)
        _kmeans = km
        _finbert_ready = True
        return _kmeans
    except Exception as e:
        print(f"FinBERT event model unavailable: {e}")
        return None


def _finbert_category(text):
    km = _load_finbert_kmeans()
    if km is None:
        return _keyword_category(text)

    try:
        from transformers import AutoTokenizer, AutoModel
        import torch

        tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
        model = AutoModel.from_pretrained("ProsusAI/finbert")
        model.eval()
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=128)
        with torch.no_grad():
            outputs = model(**inputs)
        vec = outputs.last_hidden_state[:, 0, :].numpy()
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

    try:
        _load_finbert_kmeans()
    except Exception as e:
        print(f"Event model load failed, using keyword fallback: {e}")

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
