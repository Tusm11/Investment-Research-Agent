"""Pipeline - Orchestrates data flow from agents to frontend."""

import json
import logging
import re
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from typing import Optional

from agent_1.tools.nifty50 import NIFTY50
from agent_1.data_fetcher import fetch_all_data
from agent_2.agent import run_agent2
from agent_3.agent import run_agent3
from agent_4.agent import run_agent4

def classify_intent(query: str) -> dict:
    """Return default classification - Agent 4 handles its own intent routing."""
    return {
        "intent": "general",
        "modules": [],
    }

logger = logging.getLogger(__name__)

CACHE: dict = {}          # {key: {"data": {...}, "ts": float}}
CACHE_TTL = 600           # 10 minutes

def _get_cached(key: str):
    """Retrieve cached data if still valid."""
    entry = CACHE.get(key)
    if entry and _time.time() - entry["ts"] < CACHE_TTL:
        logger.info(f"Cache HIT for {key}")
        return entry["data"]
    return {}

def _set_cached(key: str, data: dict):
    """Store data in cache with timestamp."""
    CACHE[key] = {"data": data, "ts": _time.time()}
    logger.info(f"Cache SET for {key}")

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


def cache_key(entities):
    return "|".join(sorted(ticker.split(".")[0] for ticker in entities)) or "default"


def run_pipeline(question: str, ticker: Optional[str] = None, days: int = 180, news_limit: int = 12):
    """
    Orchestrate agents with optimized caching and parallel execution.
    
    Optimization:
    - Full pipeline is cached for 10 minutes per company
    - Agent 2 and 3 run in parallel after Agent 1 completes
    - Agent 4 synthesis runs sequentially after both complete
    - Cache prevents redundant API calls within TTL window
    """
    # If ticker provided, use it directly (bypass extraction)
    if ticker:
        entities = [ticker]
    else:
        entities = extract_companies(question)
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
    cached = _get_cached(key)

    agent1_output = cached.get("agent1")
    if "agent1" in agents and not agent1_output:
        try:
            logger.info(f"Fetching Agent 1 data for {primary_ticker}...")
            agent1_output = fetch_all_data(primary_ticker, days=days, news_limit=news_limit)
            agent1_output["entities"] = entities
            cached["agent1"] = agent1_output
            _set_cached(key, cached)
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

    # OPTIMIZATION: Run Agent 2 and 3 in parallel
    agent2_output = cached.get("agent2")
    agent3_output = cached.get("agent3")
    
    if ("agent2" in agents and not agent2_output) or ("agent3" in agents and not agent3_output):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            if "agent2" in agents and not agent2_output:
                logger.info("Submitting Agent 2 (analysis)...")
                futures["agent2"] = executor.submit(run_agent2, agent1_output, question)
            
            if "agent3" in agents and not agent3_output:
                logger.info("Submitting Agent 3 (market intelligence)...")
                futures["agent3"] = executor.submit(run_agent3, agent1_output, question)
            
            # Wait for both to complete
            for agent_name, future in futures.items():
                try:
                    logger.info(f"Waiting for {agent_name}...")
                    result = future.result(timeout=60)
                    if agent_name == "agent2":
                        agent2_output = result or {}
                        cached["agent2"] = agent2_output
                    elif agent_name == "agent3":
                        agent3_output = result or {}
                        cached["agent3"] = agent3_output
                except Exception as e:
                    logger.warning(f"{agent_name} failed: {e}")
                    if agent_name == "agent2":
                        agent2_output = {}
                    elif agent_name == "agent3":
                        agent3_output = {}
    
    _set_cached(key, cached)
    
    # Agent 4 synthesis (sequential after Agent 2+3)
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
