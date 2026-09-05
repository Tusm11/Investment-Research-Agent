import os
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def _price_stats(ohlcv):
    if not ohlcv:
        return {}
    closes = [row["close"] for row in ohlcv]
    highs = [row["high"] for row in ohlcv]
    lows = [row["low"] for row in ohlcv]
    start = closes[0]
    end = closes[-1]
    change = ((end - start) / start) * 100 if start else 0
    return {
        "start_price": start,
        "current_price": end,
        "change_percent": round(change, 2),
        "high": max(highs),
        "low": min(lows),
    }


def create_price_chart(ticker, price_data, events=None, output_dir="charts"):
    ohlcv = price_data.get("ohlcv", []) if price_data else []
    if not ohlcv:
        return {"chart_file": None, "volatility": None}

    os.makedirs(output_dir, exist_ok=True)
    dates = [datetime.strptime(row["date"], "%Y-%m-%d") for row in ohlcv]
    closes = [row["close"] for row in ohlcv]
    volumes = [row["volume"] for row in ohlcv]

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(dates, closes, color="#1f77b4", linewidth=1.5, label="Price")
    ax1.set_ylabel("Price")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))

    ax2 = ax1.twinx()
    ax2.bar(dates, volumes, alpha=0.25, color="#888888", width=0.8, label="Volume")
    ax2.set_ylabel("Volume")

    colors = {
        "EARNINGS": "green",
        "PRODUCT": "blue",
        "REGULATORY": "red",
        "DIVIDEND": "purple",
        "STRATEGIC": "orange",
        "OTHER": "gray",
    }

    for event in events or []:
        try:
            ed = datetime.strptime(event.get("date"), "%Y-%m-%d")
            cat = event.get("category", "OTHER")
            ax1.axvline(ed, color=colors.get(cat, "gray"), linestyle="--", alpha=0.7)
            ax1.text(ed, max(closes) * 0.98, cat[:3], rotation=90, fontsize=7)
        except Exception:
            continue

    ax1.set_title(f"{ticker} Price & Volume")
    fig.autofmt_xdate()
    fig.tight_layout()

    chart_file = os.path.join(output_dir, f"{ticker.replace('.', '_')}_chart.png")
    fig.savefig(chart_file, dpi=120)
    plt.close(fig)

    returns = []
    for i in range(1, len(closes)):
        if closes[i - 1]:
            returns.append((closes[i] - closes[i - 1]) / closes[i - 1])
    #volatality = round((sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * 100, 2) if returns else None
    volatility = round((sum(r ** 2 for r in returns) / len(returns)) ** 0.5 * 100, 2) if returns else None
    stats = _price_stats(ohlcv)
    #volatility is calculated as the standard deviation of daily returns, expressed as a percentage. It provides a measure of how much the stock price fluctuates over time, with higher values indicating greater risk and variability in price movements.
    return {
        "period": f"{len(ohlcv)}_days",
        **stats,
        "chart_file": chart_file,
        "volatility": volatility,
    }
