"""Pipeline - Orchestrates data flow from agents to frontend."""

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Optional

from agent_1.data_fetcher import fetch_all_data
from agent_1.tools.nifty50 import NIFTY50
from agent_2.agent import run_agent2
from agent_2.final_agent2_router import route_query
from agent_3.agent import run_agent3
from agent_4.agent import run_agent4

logger = logging.getLogger(__name__)

CACHE = {}

NIFTY50_MAP = {ticker.split(".")[0]: ticker for ticker, _ in NIFTY50}

NAME_TO_TICKER = {
    "RELIANCE": "RELIANCE.NS",
    "REL": "RELIANCE.NS",
    "INFOSYS": "INFY.NS",
    "INFY": "INFY.NS",
    "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS",
    "ICICIBANK": "ICICIBANK.NS",
    "KOTAKBANK": "KOTAKBANK.NS",
    "SBIN": "SBIN.NS",
    "BHARTIARTL": "BHARTIARTL.NS",
    "LT": "LT.NS",
    "ITC": "ITC.NS",
    "WIPRO": "WIPRO.NS",
    "HCLTECH": "HCLTECH.NS",
    "TECHM": "TECHM.NS",
    "TITAN": "TITAN.NS",
    "MARUTI": "MARUTI.NS",
    "HINDUNILVR": "HINDUNILVR.NS",
    "DMART": "DMART.NS",
}

STOPWORDS = {
    "SHOW", "WHAT", "WHATS", "IS", "ARE", "CAN", "WILL", "SHOULD", "ANY", "DO", "DID",
    "THE", "FOR", "WITH", "ABOUT", "PRICE", "TREND", "MONTHS", "ANALYZE", "COMPARE",
    "LATEST", "UPDATES", "DEVELOPMENTS", "BELONG", "SECTOR", "BUSINESS",
}


def normalize(text: str) -> str:
    return re.sub(r"[^A-Z0-9 ]+", " ", (text or "").upper()).strip()


def extract_companies(query: str):
    text = normalize(query)
    companies = []

    for alias, ticker in NAME_TO_TICKER.items():
        if re.search(rf"\b{re.escape(alias)}\b", text) and ticker not in companies:
            companies.append(ticker)

    if companies:
        return companies

    words = [word for word in text.split() if word not in STOPWORDS and len(word) > 1]
    for word in words:
        if word in NIFTY50_MAP:
            return [NIFTY50_MAP[word]]

    best_match = None
    best_score = 0.0
    for word in words:
        for company, ticker in NIFTY50_MAP.items():
            score = SequenceMatcher(None, word, company).ratio()
            if score > best_score:
                best_score = score
                best_match = ticker
    if best_match and best_score >= 0.6:
        return [best_match]

    return []


def classify_intent(query: str) -> dict:
    result = route_query(query)
    return {
        "intent": result["intent"],
        "modules": result["modules"],
    }


def cache_key(entities):
    return "|".join(sorted(ticker.split(".")[0] for ticker in entities)) or "default"


def run_pipeline(question: str, ticker: Optional[str] = None, days: int = 180, news_limit: int = 12):
    entities = [ticker] if ticker else extract_companies(question)
    if not entities:
        entities = ["RELIANCE.NS"]

    primary_ticker = entities[0]
    routing = classify_intent(question)
    intent = routing["intent"]
    modules = routing["modules"]
    
    # Always build the richer company memory. Agent 2 and 3 add the structured
    # fundamentals/news/market context that Agent 4 needs to answer almost any
    # company question well.
    agents = ["agent2", "agent3"]
    if "agent1" not in agents:
        agents.insert(0, "agent1")
    
    key = cache_key(entities)
    cached = CACHE.get(key, {})

    agent1_output = cached.get("agent1")
    if "agent1" in agents and not agent1_output:
        try:
            agent1_output = fetch_all_data(primary_ticker, days=days, news_limit=news_limit)
            agent1_output["entities"] = entities
            cached["agent1"] = agent1_output
        except Exception as e:
            logger.error("Agent1 failed: %s", e)
            return {
                "query": question,
                "intent": intent,
                "entities": entities,
                "primary_ticker": primary_ticker,
                "agent1_output": {},
                "agent2_output": {},
                "agent3_output": {},
                "agent4_output": {"response": f"Data fetch failed: {e}"},
                "error": str(e),
            }

    agent2_output = cached.get("agent2")
    if "agent2" in agents and not agent2_output:
        try:
            agent2_output = run_agent2(agent1_output, question)
            cached["agent2"] = agent2_output
        except Exception as e:
            logger.warning("Agent2 failed: %s", e)
            agent2_output = {}

    agent3_output = cached.get("agent3")
    if "agent3" in agents and not agent3_output:
        try:
            agent3_output = run_agent3(agent1_output, question)
            cached["agent3"] = agent3_output
        except Exception as e:
            logger.warning("Agent3 failed: %s", e)
            agent3_output = {}

    CACHE[key] = cached
    
    agent4_output = run_agent4(question, agent1_output or {}, agent2_output or {}, agent3_output or {})

    return {
        "query": question,
        "intent": intent,
        "entities": entities,
        "primary_ticker": primary_ticker,
        "agent1_output": agent1_output or {},
        "agent2_output": agent2_output or {},
        "agent3_output": agent3_output or {},
        "agent4_output": agent4_output,
        "error": "",
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    out = run_pipeline("Is TCS financially healthy?")
    print(json.dumps({
        "query": out.get("query"),
        "intent": out.get("intent"),
        "response": out.get("agent4_output"),
    }, indent=2, default=str))
