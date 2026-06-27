import os
import logging
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)


def fetch_from_newsapi(ticker, days=180, max_articles=10):
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        return []

    company = ticker.split(".")[0]
    end = datetime.utcnow()
    start = end - timedelta(days=days)

    try:
        session = requests.Session()
        session.trust_env = False
        resp = session.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": f"{company} stock",
                "from": start.strftime("%Y-%m-%d"),
                "to": end.strftime("%Y-%m-%d"),
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": max_articles,
                "apiKey": api_key,
            },
            timeout=10,
        )
        if resp.status_code!=200: #log non-200 responses and return empty list
            logger.warning("NewsAPI returned non-200 status for %s: %s - %s", ticker, resp.status_code, resp.text)
            return []

        articles = []
        for item in resp.json().get("articles", []):
            articles.append({
                "date": (item.get("publishedAt") or "")[:10],
                "title": item.get("title"),
                "summary": item.get("description") or "",
                "source": (item.get("source") or {}).get("name", "NewsAPI"),
                "url": item.get("url"),
            })
        return articles
    except Exception as e:
        logger.warning("NewsAPI fetch failed: %s", e)
        return []
