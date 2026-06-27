import re
import os
import warnings
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yfinance as yf
import trafilatura #this is used for article extraction 
from newspaper import Article, Config #this is used for article extraction and summarization
from googlenewsdecoder import gnewsdecoder #this is used to decode Google News tracking URLs

warnings.filterwarnings("ignore")


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


def extract_article_content(url):
    """
    Extract article text using newspaper3k.
    Uses trafilatura as fallback.
    """

    config = Config()
    config.browser_user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    )

    config.request_timeout = 8

    text = ""
    summary = ""

    try:

        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            headers={"User-Agent": config.browser_user_agent},
            timeout=6
        )

        article = Article(response.url, config=config)
        article.download()
        article.parse()

        text = article.text

        try:
            article.nlp()
            summary = article.summary
        except:
            pass

    except:

        try:

            html = trafilatura.fetch_url(url)

            if html:
                text = trafilatura.extract(html)

        except:
            pass

    return {
        "summary": clean_article_text(summary),
        "full_text": clean_article_text(text)
    }


def recent_news(ticker_symbol, max_articles=20):
    """
    Fetch recent news articles for a stock.
    """

    news_feed = []

    try:
        ticker = yf.Ticker(ticker_symbol)
        try:
            ticker_news = ticker.news or []
            news_feed.extend(ticker_news)
        except Exception as e:
            print(f"Yahoo news unavailable for {ticker_symbol}: {e}")
    except Exception as e:
        print(f"Ticker init failed for {ticker_symbol}: {e}")

    company_name = ticker_symbol.split(".")[0]
    google_news = fetch_google_news_links(company_name, max_articles=max_articles)

    if google_news:
        news_feed.extend(google_news)

    summary_articles = []
    raw_articles = []

    count = 0

    for item in news_feed:

        if count >= max_articles:
            break

        title = item.get("title")
        url = item.get("link")

        if not url:
            continue

        # decode Google tracking URLs

        try:

            decoded = gnewsdecoder(url)

            if decoded and decoded.get("status"):
                url = decoded["decoded_url"]

        except:
            pass

        content = extract_article_content(url)
        article_text = content.get("full_text", "") or ""
        article_summary = content.get("summary", "") or ""
        if not article_summary and title:
            article_summary = title
        if not article_text and title:
            article_text = title

        pub_time = item.get("providerPublishTime")
        doc_date = (
            datetime.fromtimestamp(pub_time).strftime("%Y-%m-%d")
            if pub_time else datetime.now().strftime("%Y-%m-%d")
        )

        summary_articles.append(
            {
                "date": doc_date,
                "headline": title,
                "summary": article_summary[:250],
                "source": "web",
                "url": url
            }
        )

        raw_articles.append(
            {
                "headline": title,
                "full_text": article_text,
                "url": url
            }
        )

        count += 1

        if count >= max_articles:
            break

    return {
        "summary": summary_articles,
        "raw_data": raw_articles
    }


if __name__ == "__main__":

    data = recent_news("DMART.NS")

    print("\nSUMMARY\n")

    for article in data["summary"]:

        print(article)
        print()
