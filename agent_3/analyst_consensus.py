import yfinance as yf
#gets analyst consensus data for a given stock ticker using the yfinance library. It retrieves recommendation, number of analysts, price target, current price, and calculates the upside potential. It also fetches the latest buy/hold/sell recommendations from analysts and returns this information in a structured dictionary format.
def get_analyst_consensus(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info

        rec = info.get("recommendationKey") or info.get("recommendation_key") or "hold"
        analysts = info.get("numberOfAnalystOpinions") or 0
        target = info.get("targetMeanPrice")
        current = info.get("currentPrice") or info.get("regularMarketPrice")

        upside = None
        if target and current and current != 0:
            upside = round(((target - current) / current) * 100, 2)

        rec_trend = t.recommendations_summary
        buy = hold = sell = 0
        if rec_trend is not None and not rec_trend.empty:
            latest = rec_trend.iloc[0]
            buy  = int(latest.get("strongBuy", 0)) + int(latest.get("buy", 0))
            hold = int(latest.get("hold", 0))
            sell = int(latest.get("sell", 0)) + int(latest.get("strongSell", 0))

        return {
            "recommendation": rec.lower(),
            "analysts_count": analysts,
            "buy": buy,
            "hold": hold,
            "sell": sell,
            "price_target": target,
            "current_price": current,
            "upside": upside,
        }
    except Exception as e:
        print(f"Analyst consensus fetch failed: {e}")
        return {}


def format_analyst_consensus(analyst_data):
    if not analyst_data:
        return {}

    rec = (analyst_data.get("recommendation_key") or analyst_data.get("recommendation") or "hold").lower()
    analysts = analyst_data.get("number_of_analysts") or analyst_data.get("analysts_count") or 0
    target = analyst_data.get("target_mean_price") or analyst_data.get("price_target")
    current = analyst_data.get("current_price")

    upside = None
    if target and current and current != 0:
        upside = round(((target - current) / current) * 100, 2)

    return {
        "recommendation": rec,
        "analysts_count": analysts,
        "buy": analyst_data.get("buy", 0),
        "hold": analyst_data.get("hold", 0),
        "sell": analyst_data.get("sell", 0),
        "price_target": target,
        "current_price": current,
        "upside": upside,
    }
