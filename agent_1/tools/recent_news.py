import re
import os
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yfinance as yf
import trafilatura #this is used for article extraction 
from newspaper import Article, Config #this is used for article extraction and summarization
from googlenewsdecoder import gnewsdecoder #this is used to decode Google News tracking URLs

# Configure logging
logger = logging.getLogger(__name__)

# Suppress all yfinance warnings and errors
warnings.filterwarnings("ignore")
yf.set_tz_cache_location(os.path.join(Path(os.getenv("TEMP", ".")), "py-yfinance-cache"))

# Suppress yfinance logger output
logging.getLogger('yfinance').setLevel(logging.ERROR)
logging.getLogger('yfinance').propagate = False


def _prepare_network():
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY"):
        os.environ.pop(key, None)
        os.environ.pop(key.lower(), None)

    cache_dir = Path(os.getenv("TEMP", ".")) / "py-yfinance-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


_prepare_network()


def clean_article_text(text):
    """
    Removes unwanted boilerplate and UI artifacts.
    """

    if not text:
        return ""

    lines = text.split("\n")
    filtered_lines = []

    patterns = [
        "sebi registration",
        "compliance officer",
        "terms of use",
        "privacy policy",
        "copyright",
        "all rights reserved",
        "subscribe",
        "download the app",
        "follow us on"
    ]

    for line in lines:
        line = line.strip()

        if not line:
            continue

        lower_line = line.lower()

        if any(pattern in lower_line for pattern in patterns):
            continue

        filtered_lines.append(line)

    return "\n".join(filtered_lines)


def fetch_google_news_links(company, max_articles=20):
    """
    Google News RSS fallback.
    """

    articles = []

    try:
        url = (
            f"https://news.google.com/rss/search?"
            f"q={quote_plus(company + ' stock news')}&hl=en-IN&gl=IN&ceid=IN:en"
        )

        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )

        if response.status_code == 200:

            items = re.findall(
                r"<item>(.*?)</item>",
                response.text,
                re.DOTALL
            )

            for item in items[:max_articles]:

                title_match = re.search(
                    r"<title>(.*?)</title>",
                    item
                )

                link_match = re.search(
                    r"<link>(.*?)</link>",
                    item
                )

                if title_match and link_match:

                    articles.append(
                        {
                            "title": title_match.group(1),
                            "link": link_match.group(1),
                            "providerPublishTime":
                                int(datetime.now().timestamp())
                        }
                    )

    except Exception as e:
        print(f"Google News fallback error: {e}")

    return articles


def extract_article_content(url, timeout=6):
    """
    Extract article text using newspaper3k with short timeout.
    Uses trafilatura as fallback.
    Fails gracefully on 403, 404, redirects, etc.
    """
    config = Config()
    config.browser_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    config.request_timeout = timeout

    text = ""
    summary = ""

    try:
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            headers={"User-Agent": config.browser_user_agent},
            timeout=timeout,
            allow_redirects=True
        )
        response.raise_for_status()

        article = Article(response.url, config=config)
        article.download()
        article.parse()
        text = article.text

        try:
            article.nlp()
            summary = article.summary
        except:
            pass

    except requests.exceptions.Timeout:
        logger.debug("Article fetch timeout (>%ds): %s", timeout, url)
        return {"summary": "", "full_text": ""}
    except requests.exceptions.ConnectionError:
        logger.debug("Article fetch connection error: %s", url)
        return {"summary": "", "full_text": ""}
    except requests.exceptions.HTTPError as e:
        logger.debug("Article fetch HTTP error (%s): %s", e.response.status_code, url)
        return {"summary": "", "full_text": ""}
    except Exception as e:
        logger.debug("Newspaper3k fallback (%s): %s", type(e).__name__, url)
        # Try trafilatura as fallback
        try:
            html = trafilatura.fetch_url(url, timeout=timeout)
            if html:
                text = trafilatura.extract(html)
        except Exception as tf_err:
            logger.debug("Trafilatura also failed: %s", type(tf_err).__name__)
            return {"summary": "", "full_text": ""}

    return {
        "summary": clean_article_text(summary),
        "full_text": clean_article_text(text)
    }


def _decode_url(item):
    """Decode Google News tracking URL and return (title, real_url, pub_time)."""
    title = item.get("title")
    url = item.get("link")
    pub_time = item.get("providerPublishTime")
    if not url:
        return None
    try:
        decoded = gnewsdecoder(url)
        if decoded and decoded.get("status"):
            url = decoded["decoded_url"]
    except Exception:
        pass
    return title, url, pub_time


def _fetch_one_article(item):
    """Decode URL then fetch + extract article content. Returns structured dict or None."""
    result = _decode_url(item)
    if result is None:
        return None
    title, url, pub_time = result

    content = extract_article_content(url)
    article_text = content.get("full_text", "") or ""
    article_summary = content.get("summary", "") or ""
    if not article_summary and title:
        article_summary = title
    if not article_text and title:
        article_text = title

    doc_date = (
        datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d")
        if pub_time else datetime.now().strftime("%Y-%m-%d")
    )

    return {
        "summary_entry": {
            "date": doc_date,
            "headline": title,
            "summary": article_summary[:250],
            "source": "web",
            "url": url,
        },
        "raw_entry": {
            "headline": title,
            "full_text": article_text,
            "url": url,
        },
    }


def recent_news(ticker_symbol, max_articles=10):
    """
    Fetch recent news articles for a stock.
    Article extraction is parallelised across up to 6 threads.
    Each article has a hard 6-second timeout so slow pages can't block.
    Total budget: 20 seconds max per stock.
    """

    news_feed = []

    try:
        ticker = yf.Ticker(ticker_symbol)
        try:
            ticker_news = ticker.news or []
            news_feed.extend(ticker_news)
        except Exception as e:
            logger.debug("Yahoo news unavailable for %s: %s", ticker_symbol, e)
    except Exception as e:
        logger.debug("Ticker init failed for %s: %s", ticker_symbol, e)

    company_name = ticker_symbol.split(".")[0]
    google_news = fetch_google_news_links(company_name, max_articles=max_articles)

    if google_news:
        news_feed.extend(google_news)

    # Deduplicate and cap
    seen_urls: set = set()
    candidates = []
    for item in news_feed:
        url = item.get("link", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            candidates.append(item)
        if len(candidates) >= max_articles:
            break

    summary_articles = []
    raw_articles = []

    # Parallel article extraction with per-article 6s timeout
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_item = {executor.submit(_fetch_one_article, item): item for item in candidates}
        try:
            for future in as_completed(future_to_item, timeout=20):
                try:
                    result = future.result(timeout=6)
                    if result:
                        summary_articles.append(result["summary_entry"])
                        raw_articles.append(result["raw_entry"])
                except Exception as e:
                    logger.debug("Article extraction failed: %s", type(e).__name__)
        except FuturesTimeoutError:
            logger.debug("News fetch hit 20s budget for %s — returning partial results (%d articles)", ticker_symbol, len(summary_articles))
            # Collect whatever finished
            for future in future_to_item:
                if future.done() and not future.cancelled():
                    try:
                        result = future.result()
                        if result:
                            summary_articles.append(result["summary_entry"])
                            raw_articles.append(result["raw_entry"])
                    except Exception:
                        pass

    return {
        "summary": summary_articles,
        "raw_data": raw_articles,
    }


if __name__ == "__main__":

    data = recent_news("DMART.NS")

    print("\nSUMMARY\n")

    for article in data["summary"]:

        print(article)
        print()
