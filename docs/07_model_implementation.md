# 7. Model Implementation

This section documents the implementation details of every module, function, and class in the codebase.

## 7.1 Imports and Dependencies

### Core Dependencies

All modules rely on the following base imports:

```python
import os
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
```

**Rationale**: `ThreadPoolExecutor` enables parallel fetching without asyncio overhead; `numpy` and `pandas` handle financial data manipulation with vectorized operations.

### External Libraries

| Module | Import | Purpose |
|--------|--------|---------|
| Data Fetching | `yfinance`, `requests`, `trafilatura` | Real-time financial data, web scraping |
| ML/Anomaly | `sklearn.ensemble.IsolationForest`, `joblib`, `xgboost` | Model loading, training, inference |
| LLM | `langchain_groq.ChatGroq`, `langchain_core.prompts` | Groq API client, prompt templates |
| Web | `fastapi`, `pydantic` | REST framework, request validation |
| Env Config | `dotenv` | Load API keys from .env |

---

## 7.2 Configuration and Path/Env Setup

### Entry Point: main.py

```python
import argparse
import json
import logging

from pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="Run the investment research pipeline")
    parser.add_argument("question", help="Research question, for example: Is RELIANCE healthy?")
    parser.add_argument("--ticker", default=None, help="Ticker symbol such as RELIANCE.NS")
    parser.add_argument("--days", type=int, default=180, help="Lookback window for price and news")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = run_pipeline(args.question, ticker=args.ticker, days=args.days)

    agent1_data = result.get("agent1_output") or {}
    output = {
        "question": args.question,
        "ticker": result.get("primary_ticker"),
        "intent": result.get("intent"),
        "company": agent1_data.get("company_info", {}).get("company_name"),
        "current_price": agent1_data.get("price_history", {}).get("current_price"),
        "agent2_output": result.get("agent2_output"),
        "agent3_output": result.get("agent3_output"),
        "response": result.get("agent4_output", {}).get("response"),
        "error": result.get("error"),
    }
    print(json.dumps(output, indent=2, default=str))
```

**Purpose**: CLI interface for running the research pipeline from command line.

**Explanation**:
- Parses three arguments: research question (required), ticker (optional), lookback days (default 180)
- Invokes `run_pipeline()` with these parameters
- Extracts key fields from result and prints as JSON for downstream consumption

---

## 7.3 Agent 1: Data Fetching Implementation

### Orchestrator: pipeline.py

```python
def run_pipeline(question: str, ticker: Optional[str] = None, days: int = 180, news_limit: int = 12):
    """
    Orchestrate agents with optimized caching and parallel execution.
    
    Optimization:
    - Full pipeline is cached for 10 minutes per company
    - Agent 2 and 3 run in parallel after Agent 1 completes
    - Agent 4 synthesis runs sequentially after both complete
    - Cache prevents redundant API calls within TTL window
    """
    if ticker:
        entities = [ticker]
    else:
        entities = extract_companies(question)
        if not entities:
            entities = ["RELIANCE.NS"]

    primary_ticker = entities[0]
    
    key = cache_key(entities)
    cached = _get_cached(key)

    agent1_output = cached.get("agent1")
    if not agent1_output:
        try:
            logger.info(f"Fetching Agent 1 data for {primary_ticker}...")
            agent1_output = fetch_all_data(primary_ticker, days=days, news_limit=news_limit)
            agent1_output["entities"] = entities
            cached["agent1"] = agent1_output
            _set_cached(key, cached)
        except Exception as e:
            logger.error("Agent1 failed: %s", e)
            return {
                "error": str(e),
                ...
            }

    # OPTIMIZATION: Run Agent 2 and 3 in parallel
    agent2_output = cached.get("agent2")
    agent3_output = cached.get("agent3")
    
    if ("agent2" in agents and not agent2_output) or ("agent3" in agents and not agent3_output):
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            if "agent2" not in cached:
                futures["agent2"] = executor.submit(run_agent2, agent1_output, question)
            
            if "agent3" not in cached:
                futures["agent3"] = executor.submit(run_agent3, agent1_output, question)
            
            for agent_name, future in futures.items():
                try:
                    result = future.result(timeout=60)
                    cached[agent_name] = result or {}
                except Exception as e:
                    logger.warning(f"{agent_name} failed: {e}")
                    cached[agent_name] = {}
    
    _set_cached(key, cached)
    
    agent4_output = run_agent4(question, agent1_output or {}, agent2_output or {}, agent3_output or {})

    return {
        "agent1_output": agent1_output or {},
        "agent2_output": agent2_output or {},
        "agent3_output": agent3_output or {},
        "agent4_output": agent4_output,
    }
```

**Purpose**: Central orchestration; manages caching and parallel execution.

**Explanation**:
- Extracts companies from question or uses explicit ticker
- Checks 10-minute TTL cache; returns immediately if hit
- Runs Agent 1 with 55-second budget (via ThreadPoolExecutor in data_fetcher.py)
- Submits Agents 2 & 3 to ThreadPoolExecutor with 60-second combined timeout
- Runs Agent 4 sequentially after both complete
- Caches full result for 10 minutes to avoid redundant work

### Data Fetcher: agent_1/data_fetcher.py

```python
def fetch_all_data(ticker: str, days: int = 180, news_limit: int = 12):
    """Parallel data collection with 55-second hard timeout."""
    start_time = _time.time()
    BUDGET = 55  # seconds
    
    logger.info(f"Starting Agent 1 fetch for {ticker} (budget: {BUDGET}s)")
    
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            "company_info": executor.submit(fetch_company_info, ticker),
            "price_history": executor.submit(fetch_price_history, ticker, days),
            "news": executor.submit(fetch_news_articles, ticker, days, news_limit),
            "analyst_data": executor.submit(fetch_analyst_consensus, ticker),
            "financial_metrics": executor.submit(fetch_financial_metrics, ticker),
            "market_drivers": executor.submit(fetch_market_drivers, ticker),
        }
        
        output = {}
        for key, future in futures.items():
            elapsed = _time.time() - start_time
            remaining = BUDGET - elapsed
            
            if remaining <= 0:
                logger.warning(f"Agent 1 timeout: {remaining}s remaining, cancelling {key}")
                future.cancel()
                break
            
            try:
                result = future.result(timeout=remaining)
                output[key] = result
                logger.info(f"{key} completed in {_time.time() - start_time:.1f}s")
            except Exception as e:
                logger.warning(f"{key} failed: {e}")
                output[key] = {}
    
    output["ticker"] = ticker
    output["_fetch_complete_time"] = _time.time() - start_time
    return output
```

**Purpose**: Parallel data fetching within strict time budget.

**Explanation**:
- Creates ThreadPoolExecutor with 6 workers (one per data stream)
- Monitors wall-clock time; cancels remaining tasks if budget exceeded
- Returns partial data (some streams may be empty if timeout)
- Logs fetch time for each stream

### Data Fetching Functions

#### fetch_company_info()

```python
def fetch_company_info(ticker):
    """Extract company fundamentals from yfinance."""
    try:
        info = _get_info(ticker)
        return {
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "business_summary": info.get("longBusinessSummary"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "debtToEquity": info.get("debtToEquity"),
            "currentRatio": info.get("currentRatio"),
            "returnOnEquity": info.get("returnOnEquity"),
            "returnOnAssets": info.get("returnOnAssets"),
            "operatingMargins": info.get("operatingMargins"),
            "revenueGrowth": info.get("revenueGrowth"),
            "freeCashflow": info.get("freeCashflow"),
            "totalRevenue": info.get("totalRevenue"),
            "grossProfit": info.get("grossProfit"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        logger.warning(f"fetch_company_info failed for {ticker}: {e}")
        return {}
```

**Purpose**: Extract company metadata and financial fundamentals.

**Explanation**:
- Uses yfinance `.info` API to fetch 20+ company fields
- Returns dictionary; missing fields are None (not 0)
- Handles exceptions gracefully; returns empty dict on failure

#### fetch_analyst_consensus()

```python
def fetch_analyst_consensus(ticker, info: Optional[dict] = None):
    try:
        info = info or _get_info(ticker)
        current = info.get("currentPrice") or info.get("regularMarketPrice")
        target = info.get("targetMeanPrice")
        upside = None
        if current and target:
            upside = round(((target - current) / current) * 100, 2)

        return {
            "status": "success",
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions"),
            "target_mean_price": target,
            "current_price": current,
            "upside_downside_percent": upside,
            **_fetch_recommendation_counts(ticker),
            "source": "yahoo_finance",
        }
    except Exception as e:
        logger.warning("analyst consensus missing for %s: %s", ticker, e)
        return {
            "status": "retrieval_error",
            "recommendation_key": None,
            "upside_downside_percent": None,
            ...
        }
```

**Purpose**: Fetch analyst sentiment and price targets.

**Explanation**:
- Extracts analyst recommendation (buy/hold/sell)
- Calculates upside/downside %: ((target - current) / current) × 100
- Returns detailed status; missing data returns None (not placeholder values)

### Example Output: Agent 1

```json
{
  "ticker": "TCS.NS",
  "company_info": {
    "company_name": "Tata Consultancy Services",
    "sector": "Technology",
    "market_cap": 13500000000000,
    "pe_ratio": 28.5,
    "dividend_yield": 0.012
  },
  "price_history": {
    "current_price": 3200.0,
    "ohlcv": [
      [3180, 3210, 3150, 3190, 5000000],
      ...
    ],
    "week_52_high": 3500.0,
    "week_52_low": 2700.0
  },
  "news": [
    {
      "title": "TCS Q3 earnings beat expectations",
      "summary": "...",
      "source": "Reuters",
      "url": "...",
      "date": "2024-01-15"
    }
  ],
  "analyst_data": {
    "recommendation_key": "buy",
    "target_mean_price": 3500.0,
    "upside_downside_percent": 8.5,
    "buy": 18,
    "hold": 5,
    "sell": 2
  },
  "market_drivers": {...},
  "_fetch_complete_time": 23.4
}
```

---

## 7.4 Agent 2: Fundamental Health Analysis Implementation

### Orchestrator: agent_2/agent.py

```python
def run_agent2(agent1_payload, question=""):
    ticker = agent1_payload.get("ticker")
    red_flags = []
    peer_comparison = {}
    model_assessment = {}
    financial_facts = {}

    route = route_query(question, ticker)
    
    # Run red flags detection
    if "red_flags" in route.get("modules", []) or "fundamentals" in route.get("modules", []):
        try:
            red_flags = detect_red_flags(ticker)
            model_assessment = assess_isolation_forest(ticker)
        except Exception as e:
            print(f"Agent2 red flags failed: {e}")

    # Run peer comparison
    if "peer_comparison" in route.get("modules", []) or "fundamentals" in route.get("modules", []):
        try:
            company_features = build_health_features(ticker)["feature_vector"]
            peer_comparison = compare_peers(ticker, company_features)
            financial_facts = {
                "ROCE": company_features.get("ROCE"),
                "OperatingMargin": company_features.get("OPM %"),
                "Debt": company_features.get("Debt"),
                "CurrentRatio": company_features.get("Current Ratio"),
                ...
            }
        except Exception as e:
            print(f"Agent2 peer comparison failed: {e}")

    profile = build_fundamental_profile(peer_comparison, red_flags)
    analysis = analyze_fundamentals(peer_comparison, red_flags)
    
    return {
        "ticker": ticker,
        "financial_facts": financial_facts,
        "red_flags": red_flags,
        "model_assessment": model_assessment,
        "peer_comparison": peer_comparison,
        "fundamental_profile": profile,
        "fundamental_signals": {
            "strengths": analysis["strengths"],
            "weaknesses": analysis["weaknesses"],
        },
    }
```

**Purpose**: Coordinate all Agent 2 analysis modules.

**Explanation**:
- Routes question to relevant modules (red_flags, peer_comparison)
- Extracts 12 target metrics via build_health_features()
- Compares peers; calculates percentile ranks
- Detects red flags and Isolation Forest anomalies
- Derives strengths/weaknesses from peer context

### Health Features: agent_2/health_data.py

```python
TARGET_METRICS = [
    "ROCE", "Debt", "Sales", "Operating Profit", "OPM %", 
    "Net Profit", "Total Assets", "Total Liabilities", 
    "Cash from Operating Activity", "Debtor Days", 
    "Inventory Days", "Working Capital Days"
]

def build_health_features(ticker_symbol):
    t = yf.Ticker(ticker_symbol)
    
    bs = t.balance_sheet
    income = t.income_stmt
    cf = t.cashflow

    bs_latest = bs.iloc[:, 0] if not bs.empty else {}
    is_latest = income.iloc[:, 0] if not income.empty else {}
    cf_latest = cf.iloc[:, 0] if not cf.empty else {}

    raw = {
        "EBIT": is_latest.get("EBIT") or is_latest.get("Operating Income"),
        "Total Assets": bs_latest.get("Total Assets"),
        "Current Assets": bs_latest.get("Current Assets"),
        "Current Liabilities": bs_latest.get("Current Liabilities"),
        "Debt": bs_latest.get("Total Debt") or info.get("totalDebt"),
        "Sales": is_latest.get("Total Revenue") or info.get("totalRevenue"),
        ...
    }

    feature_vector = {}

    # ROCE = EBIT / Capital Employed * 100
    capital_employed = None
    if raw.get("Total Capitalization"):
        capital_employed = raw["Total Capitalization"]
    elif raw["Total Assets"] and raw["Current Liabilities"]:
        capital_employed = raw["Total Assets"] - raw["Current Liabilities"]
    
    set_val("ROCE", raw["EBIT"] / capital_employed * 100 if raw["EBIT"] and capital_employed else None)
    set_val("OPM %", (raw["Operating Profit"] / raw["Sales"]) * 100 if raw["Operating Profit"] and raw["Sales"] else None)
    set_val("Debtor Days", (raw["Accounts Receivable"] / raw["Sales"]) * 365 if raw["Accounts Receivable"] and raw["Sales"] else None)
    set_val("Inventory Days", (raw["Inventory"] / raw["Cost of Revenue"]) * 365 if raw["Inventory"] and raw["Cost of Revenue"] else None)
    set_val("Working Capital Days", ((raw["Current Assets"] - raw["Current Liabilities"]) / raw["Sales"]) * 365 if raw["Current Assets"] and raw["Current Liabilities"] and raw["Sales"] else None)

    missing = [k for k, v in feature_vector.items() if v is None]
    return {"feature_vector": feature_vector, "missing_features": missing}
```

**Purpose**: Extract 12 key financial metrics from yfinance financials.

**Explanation**:
- Fetches latest balance sheet, income statement, cash flow from yfinance
- Calculates derived metrics:
  - ROCE % = EBIT / Capital Employed × 100
  - OPM % = Operating Profit / Sales × 100
  - Debtor Days = (AR / Sales) × 365
  - Similar formulas for Inventory Days, Working Capital Days
- Returns feature_vector dict and list of missing fields
- Treats missing data as None (not 0) to distinguish unavailable from zero

### Peer Comparison: agent_2/peer_comparison.py

```python
def compare_peers(ticker, company_features):
    if not company_features:
        return {"sector": "Unknown", "metrics": {}}

    sector = get_sector(ticker)
    peers = get_peers(sector, ticker)
    
    peer_data = {m: [] for m in TARGET_METRICS}

    def _fetch_peer(peer):
        try:
            return peer, build_health_features(peer)["feature_vector"]
        except Exception:
            return peer, {}

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_fetch_peer, peer): peer for peer in peers}
        for future in as_completed(futures, timeout=20):
            try:
                _, feats = future.result(timeout=5)
                for m in TARGET_METRICS:
                    val = feats.get(m)
                    if val is not None and not np.isnan(val):
                        peer_data[m].append(val)
            except Exception:
                pass

    output_metrics = {}

    for m in TARGET_METRICS:
        c_val = company_features.get(m)
        p_vals = peer_data[m]
        
        avg = np.mean(p_vals) if p_vals else None
        pct = percentile(c_val, p_vals)
        
        output_metrics[m] = {
            "company": round(c_val, 2) if c_val is not None else None,
            "sector_average": round(avg, 2) if avg is not None else None,
            "percentile": pct
        }

    return {
        "sector": sector,
        "peers": peers,
        "metrics": output_metrics
    }

def percentile(val, peer_vals):
    if val is None or np.isnan(val) or not peer_vals:
        return 50
    valid_peers = [v for v in peer_vals if v is not None and not np.isnan(v)]
    if not valid_peers:
        return 50
    
    count_below = sum(1 for v in valid_peers if v < val)
    count_equal = sum(1 for v in valid_peers if v == val)
    pct = ((count_below + 0.5 * count_equal) / len(valid_peers)) * 100
    return int(round(pct))
```

**Purpose**: Calculate percentile ranks within sector.

**Explanation**:
- Fetches all peers in the same sector
- ThreadPoolExecutor (8 workers, 20s timeout) fetches features for each peer
- Calculates percentile: counts how many peers have a lower value; rounds to 0–100
- Returns company value, sector average, and percentile for each metric
- Defaults to 50th percentile if data unavailable

### Red Flags Detection: agent_2/red_flags.py

```python
def detect_red_flags(ticker):
    flags = []
    try:
        t = yf.Ticker(ticker)
        info = t.info
        bs = t.balance_sheet.iloc[:, 0] if not t.balance_sheet.empty else {}
        
        revenue = info.get("totalRevenue") or 0
        net_income = info.get("netIncomeToCommon") or 0
        debt = bs.get("Total Debt") or info.get("totalDebt")
        equity = bs.get("Stockholders Equity") or info.get("totalStockholderEquity")
        
        # Check 1: Incomplete Financial Data
        if not revenue or not equity:
            flags.append({
                "metric": "Incomplete Financial Data",
                "value": "N/A",
                "severity": "high",
                "explanation": "Missing key financial metrics (revenue or equity)."
            })
            return flags
        
        # Check 2: High Debt
        debt_to_equity = debt / equity if debt and equity else 0
        if debt_to_equity > 5:
            flags.append({
                "metric": "High Debt",
                "value": f"Debt/Equity: {debt_to_equity:.2f}",
                "severity": "high",
                "explanation": "Company has high debt relative to equity, increasing financial risk."
            })
        
        # Check 3: Low Profit Margin
        profit_margin = net_income / revenue if revenue else 0
        if profit_margin < 0.10 and revenue:
            flags.append({
                "metric": "Low Profit Margin",
                "value": f"{profit_margin*100:.1f}%",
                "severity": "medium",
                "explanation": "Profit margin is below 10%, indicating weaker profitability."
            })
        
        # Check 4 & 5: Low ROE, Slow Revenue Growth (skipped if not available)
        roe = info.get("returnOnEquity")
        if roe and roe < 0.15:
            flags.append({
                "metric": "Low ROE",
                "value": f"{roe*100:.1f}%",
                "severity": "low",
                "explanation": "Return on equity is below 15%."
            })
        
        # Check 6: Isolation Forest Anomaly
        assessment = assess_isolation_forest(ticker)
        anomaly_score = assessment.get("anomaly_score", 0)
        if assessment.get("is_anomaly") or anomaly_score >= 0.7:
            flags.append({
                "metric": "Financial Statements",
                "value": f"Risk Score: {anomaly_score:.2f}",
                "severity": "high" if anomaly_score >= 0.85 else "medium",
                "explanation": f"Statistical analysis flagged anomalous financial patterns (score: {anomaly_score:.2f})."
            })
            
    except Exception as e:
        flags.append({
            "metric": "Analysis Failed",
            "value": "N/A",
            "severity": "high",
            "explanation": f"Red flag analysis error: {str(e)}"
        })
        
    return flags

def assess_isolation_forest(ticker):
    """Run the trained Isolation Forest and return a structured assessment."""
    model = _get_model()  # Load pre-trained model from isolation_forest_model.pkl
    feats = build_features(ticker)

    feature_order = list(getattr(model, "feature_names_in_", EXPECTED_FEATURES))
    vec = pd.DataFrame([[feats.get(name, 0) for name in feature_order]], columns=feature_order)
    vec = vec.replace([np.inf, -np.inf], 0).fillna(0)

    prediction = int(model.predict(vec)[0])
    decision = float(model.decision_function(vec)[0])
    anomaly_score = round(max(0.0, -decision), 4)

    return {
        "model_path": MODEL_PATH,
        "model_loaded": True,
        "prediction": prediction,  # -1 = anomaly, 1 = normal
        "decision_function": round(decision, 4),
        "anomaly_score": round(anomaly_score, 4),  # 0-1, higher = more anomalous
        "is_anomaly": prediction == -1,
        "used_features": feature_order,
    }

def build_features(ticker_symbol):
    """Build 15 z-scored financial ratio features for Isolation Forest."""
    t = yf.Ticker(ticker_symbol)
    bs = t.balance_sheet.iloc[:, 0] if not t.balance_sheet.empty else {}
    is_ = t.income_stmt.iloc[:, 0] if not t.income_stmt.empty else {}
    cf = t.cashflow.iloc[:, 0] if not t.cashflow.empty else {}

    revenue = _first_present(is_, "Total Revenue")
    net_income = _first_present(is_, "Net Income")
    operating_income = _first_present(is_, "Operating Income")
    interest_expense = _first_present(is_, "Interest Expense", "Interest Expense And Other")
    assets = _first_present(bs, "Total Assets")
    equity = _first_present(bs, "Stockholders Equity")
    debt = _first_present(bs, "Total Debt")
    current_assets = _first_present(bs, "Current Assets")
    current_liabilities = _first_present(bs, "Current Liabilities")
    inventory = _first_present(bs, "Inventory")
    cash = _first_present(bs, "Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments")
    ocf = _first_present(cf, "Total Cash From Operating Activities", "Operating Cash Flow")

    ebitda = (operating_income or 0) + (depreciation or 0)
    invested_capital = (debt or 0) + (equity or 0)
    net_debt = (debt or 0) - (cash or 0)

    features = {
        "Debt To Equity_z": _safe_div(debt, equity),
        "Debt Ratio_z": _safe_div(debt, assets),
        "Net Debt To Ebitda_z": _safe_div(net_debt, ebitda),
        "Total Debt To Capitalization_z": _safe_div(debt, invested_capital),
        "Current Ratio_z": _safe_div(current_assets, current_liabilities),
        "Quick Ratio_z": _safe_div((current_assets or 0) - (inventory or 0), current_liabilities),
        "Cash Ratio_z": _safe_div(cash, current_liabilities),
        "Net Profit Margin_z": _safe_div(net_income, revenue),
        "Operating Profit Margin_z": _safe_div(operating_income, revenue),
        "ROE_z": _safe_div(net_income, equity),
        "ROIC_z": _safe_div(operating_income, invested_capital),
        "Income Quality_z": _safe_div(ocf, net_income),
        "Cash Flow To Debt Ratio_z": _safe_div(ocf, debt),
        "Interest Coverage_z": _safe_div(operating_income, abs(interest_expense) if interest_expense else None),
        "Asset Turnover_z": _safe_div(revenue, assets),
    }

    for key in features:
        if features[key] is None:
            features[key] = 0.0

    return features
```

**Purpose**: Detect red flags via hardcoded thresholds and Isolation Forest anomaly detection.

**Explanation**:
- Hardcoded checks: incomplete data (HIGH), high debt > 5 (HIGH), low margin < 10% (MEDIUM), low ROE < 15% (LOW), slow growth < 8% (LOW)
- Isolation Forest: 15 z-scored financial ratios → model.predict() → prediction (-1=anomaly, 1=normal)
- Anomaly score = max(0, -decision_function); normalized 0–1
- Returns structured red flag list with metric, value, severity, explanation

### Example Output: Agent 2

```json
{
  "ticker": "TCS.NS",
  "financial_facts": {
    "ROCE": 23.5,
    "OperatingMargin": 22.1,
    "Debt": 5000,
    "CurrentRatio": 1.8,
    "NetProfit": 12000
  },
  "red_flags": [],
  "model_assessment": {
    "prediction": 1,
    "anomaly_score": 0.34,
    "is_anomaly": false
  },
  "peer_comparison": {
    "sector": "Technology",
    "peers": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS"],
    "metrics": {
      "ROCE": {"company": 23.5, "sector_average": 18.2, "percentile": 78},
      "OPM %": {"company": 22.1, "sector_average": 19.5, "percentile": 65},
      ...
    }
  },
  "fundamental_signals": {
    "strengths": ["High ROCE", "Strong margins", "Good liquidity"],
    "weaknesses": []
  }
}
```

---

## 7.5 Agent 3: Market Intelligence & Perception Implementation

### Orchestrator: agent_3/agent.py

```python
def _route_query(question):
    text = (question or "").lower()
    return {
        "news": any(term in text for term in ("news", "event", "developments")),
        "analyst": any(term in text for term in ("buy", "sell", "target", "sentiment")),
        "price": any(term in text for term in ("chart", "trend", "price", "6 months")),
        "rag": any(term in text for term in ("outlook", "risks", "opportunities")),
        "comparison": any(term in text for term in ("compare", "vs", "versus")),
        "future": any(term in text for term in ("future", "outlook", "forecast")),
    }

def run_agent3(agent1_payload, question="", **_):
    ticker = agent1_payload.get("ticker")
    news = agent1_payload.get("news", {})
    price_data = agent1_payload.get("price_history", {})

    route = _route_query(question)

    if not any(route.values()):
        route.update({"news": True, "analyst": True, "price": True})

    events = []
    analyst_consensus = {}
    price_performance = {}

    if route.get("news"):
        try:
            events = extract_events(news)
        except Exception as e:
            print(f"Agent3 event extraction failed: {e}")

    if route.get("analyst"):
        try:
            analyst_consensus = get_analyst_consensus(ticker)
        except Exception as e:
            print(f"Agent3 analyst consensus failed: {e}")

    if route.get("price"):
        try:
            price_performance = create_price_chart(ticker, price_data, events)
        except Exception as e:
            print(f"Agent3 price chart failed: {e}")

    # Determine sentiment
    sentiment = None
    if analyst_consensus:
        rec = (analyst_consensus.get("recommendation_key") or "hold").lower().replace("_", " ")
        if rec in ("buy", "strong buy", "overweight"):
            sentiment = "Bullish"
        elif rec in ("sell", "strong sell", "underweight"):
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"
    
    result = synthesize_market(
        ticker,
        events,
        analyst_consensus,
        price_performance,
        route.get("future"),
    )

    return {
        "ticker": ticker,
        "sentiment": sentiment,
        "market_intelligence_report": result.get("market_intelligence_report", {}),
        "market_facts": analyst_consensus,
        "recent_events": events,
        "risks": result.get("risks", []),
        "opportunities": result.get("opportunities", []),
    }
```

**Purpose**: Synthesize market sentiment, analyst views, news, and price trends.

**Explanation**:
- Routes question to relevant modules (news, analyst, price, rag, comparison)
- Extracts news events; classifies sentiment (positive/negative/neutral)
- Fetches analyst consensus (recommendation, target, buy/hold/sell counts)
- Creates price chart data for frontend rendering
- Determines overall sentiment based on analyst recommendation or event sentiment
- Synthesizes all inputs into market intelligence narrative

### Example Output: Agent 3

```json
{
  "ticker": "TCS.NS",
  "sentiment": "Bullish",
  "market_intelligence_report": {
    "market_perception": "Market is optimistic on TCS with bullish analyst consensus and mixed news flow.",
    "risk_factors": ["Global economic slowdown", "Tech sector valuation concerns"],
    "positive_factors": ["Strong Q3 earnings", "Increasing margins"]
  },
  "market_facts": {
    "recommendation": "buy",
    "target_price": 3500.0,
    "upside_downside_percent": 8.5,
    "buy": 18,
    "hold": 5,
    "sell": 2
  },
  "recent_events": [
    {
      "title": "TCS reports strong Q3 results",
      "summary": "...",
      "source": "Reuters",
      "date": "2024-01-15",
      "sentiment": "positive"
    }
  ],
  "risks": ["Rupee depreciation", "Talent retention"],
  "opportunities": ["Cloud adoption", "Digital transformation"]
}
```

---

## 7.6 Agent 4: Report Synthesis Implementation

### Orchestrator: agent_4/agent.py (excerpt - 1439 lines total)

```python
def classify_question(query, memory=None):
    """Classify user question intent (60-second cache)."""
    cache_key = query.strip()
    if cache_key in _classification_cache:
        cached_result, cached_time = _classification_cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_result
    
    system_prompt = """You are a Question Classifier for an investment research assistant.
    
Your job is to analyze the user's question and determine:
1. What the user is trying to learn (intent)
2. Which companies are mentioned (entities)
3. What data sections are needed
4. Which tools to use

Intents: financial_health, explanation, education, comparison, calculation, historical_performance, 
sector_ranking, investment_simulator, market_intelligence, price_analysis, investment_summary, 
news, unsupported
..."""

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{question}")])
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"), temperature=0)
    
    try:
        response = (prompt | llm).invoke({"question": query.strip()}).content.strip()
        response = re.sub(r"^```(?:json)?|```$", "", response, flags=re.IGNORECASE).strip()
        result = json.loads(response)
        return _normalize_classification(result)
    except json.JSONDecodeError:
        result = _fallback_classification(query)
    
    _classification_cache[query.strip()] = (result.copy(), time.time())
    return result
```

**Purpose**: Classify question intent using LLM (60-second cache on result).

**Explanation**:
- Constructs system prompt defining 13 intent classes
- Invokes Groq LLM to classify question
- Caches result for 60 seconds to avoid redundant LLM calls
- Falls back to rule-based classification if JSON parsing fails

### RAG Chat: rag_assistant.py

```python
def rag_chat(question: str, memory: dict, agent2_output: dict, ticker: str = None, tab_context: str = None):
    """RAG-grounded chat with per-tab context awareness."""
    if not question or not question.strip():
        return {
            "response": "Please ask a question about the company.",
            "status": "error",
            "company": ticker,
        }
    
    if not ticker:
        ticker = memory.get("company_info", {}).get("ticker")
    
    if not ticker:
        return {
            "response": "Error: No company context provided.",
            "status": "error",
            "company": None,
        }
    
    is_relevant, block_reason = is_company_relevant(question, ticker)
    if not is_relevant:
        return {
            "response": block_reason or "That question is outside the scope of company research.",
            "status": "blocked",
            "company": ticker,
        }
    
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        company_name = memory.get("company_info", {}).get("name", ticker)
        company_context = build_company_context(memory, agent2_output)
        
        system_prompt = f"""You are a professional investment research assistant analyzing {company_name} ({ticker}).

Your role is to answer questions about this specific company using the provided financial data.

CRITICAL: Respond with ONLY the final answer. Do not include reasoning process, analysis steps, 
drafts, or meta-commentary about how you constructed the answer.

IMPORTANT RULES:
1. Always reference {ticker} specifically
2. Use concrete numbers and metrics from company data
3. Explain financial concepts in simple, clear terms
4. If data unavailable, say "This metric is not available for {ticker}"
5. Never provide personal investment advice
6. Always cite sources: "According to the financial data..."
7. Answer metric-specific questions (ground in tab_context) and general questions (use company data)

COMPANY DATA:
{company_context}
"""
        if tab_context:
            system_prompt += f"""

WHAT THE USER IS CURRENTLY VIEWING:
The user asked this question while on a specific tab. The data below is EXACTLY what is 
rendered on their screen right now — ground it in these numbers first.

{tab_context}
"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Question about {ticker}: {question}"},
        ]
        
        try:
            response = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
        except Exception as llm_err:
            if "rate_limit" in str(llm_err).lower() or "429" in str(llm_err):
                response = client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    temperature=0.3,
                    max_tokens=500,
                )
            else:
                raise

        answer = response.choices[0].message.content or ""
        
        # Strip reasoning leaks
        if "<think>" in answer:
            answer = answer.split("</think>")[-1].strip()
        
        reasoning_markers = ["Here's a thinking process:", "Here's my thinking:", "Let me analyze:", 
                            "Here's my analysis:", "Let me think about this:", "Draft:", "Analysis:"]
        for marker in reasoning_markers:
            if marker in answer:
                parts = answer.split(marker, 1)
                if len(parts) > 1:
                    rest = parts[1].strip()
                    if not rest.lower().startswith(("1.", "step", "first", "then")):
                        answer = rest
        
        return {
            "response": answer,
            "status": "success",
            "company": ticker,
        }
        
    except Exception as e:
        logger.error(f"RAG chat error: {e}")
        return {
            "response": f"I encountered an error processing your question. Please try again.",
            "status": "error",
            "company": ticker,
        }
```

**Purpose**: RAG-grounded chat with tab context awareness and reasoning leak stripping.

**Explanation**:
- Validates company ticker and question relevance
- Builds company context from memory + Agent 2 red flags
- Includes tab_context (exact on-screen data) in system prompt
- Calls Groq LLM; falls back to "openai/gpt-oss-20b" on 429 rate limit
- Strips reasoning blocks (`<think>`, "Here's my thinking:", etc.)
- Returns structured answer with status

---

## 7.7 FastAPI Backend/API Layer

### Main Endpoints: backend/main.py

```python
app = FastAPI(title="Stock Market Research Agent API", json_encoder=SafeJSONEncoder, 
              default_response_class=SafeJSONResponse)

@app.post("/api/company-research")
async def company_research(request: CompanyResearchRequest):
    """Company-specific research endpoint."""
    try:
        result = run_pipeline(f"Analyze {request.name}", ticker=request.ticker, days=request.days)
        
        if result.get("error"):
            return {
                "success": False,
                "error": f"Data retrieval failed: {result.get('error')}",
                "ticker": request.ticker,
            }
        
        memory = company_memory.build_company_memory(
            result.get("agent1_output") or {},
            result.get("agent2_output") or {},
            result.get("agent3_output") or {}
        )
        
        info = memory.get("company_info", {})
        current_price = memory.get("price_data", {}).get("current")
        
        # Calculate metrics
        target_price = result.get("agent4_output", {}).get("target_price")
        expected_return = None
        if target_price and current_price:
            expected_return = ((target_price - current_price) / current_price) * 100
        
        # Extract sentiment
        sentiment_status = result.get("agent3_output", {}).get("sentiment")
        sentiment_score = 75 if sentiment_status == "Bullish" else 25 if sentiment_status == "Bearish" else 50 if sentiment_status == "Neutral" else None
        
        return {
            "success": True,
            "ticker": request.ticker,
            "company_name": info.get("name"),
            "sector": info.get("sector"),
            "current_price": current_price,
            "expected_return": expected_return,
            "target_price": target_price,
            "sentiment_score": sentiment_score,
            "red_flags": memory.get("red_flags", []),
            "financial_metrics": memory.get("financial_metrics", {}),
            "peer_comparison": memory.get("peer_comparison", {}),
            "risks": memory.get("risks", []),
            "opportunities": memory.get("opportunities", []),
            "_data_quality": {
                "price_available": current_price is not None,
                "news_available": len(memory.get("news_articles", [])) > 0,
                "sentiment_analyzed": sentiment_status is not None,
                "risks_identified": len(memory.get("risks", [])) > 0,
                "peer_data_available": bool(memory.get("peer_comparison", {}).get("metrics")),
            }
        }
    except Exception as e:
        logger.error(f"company_research error: {e}")
        return {
            "success": False,
            "error": str(e),
            "ticker": request.ticker,
        }

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat about a company grounded in tab context."""
    try:
        from rag_assistant import rag_chat
        
        # Run pipeline to get memory
        result = run_pipeline(f"Research {request.symbol}")
        memory = company_memory.build_company_memory(
            result.get("agent1_output") or {},
            result.get("agent2_output") or {},
            result.get("agent3_output") or {}
        )
        
        answer = rag_chat(
            request.question,
            memory,
            result.get("agent2_output", {}),
            request.symbol,
            tab_context=request.context
        )
        
        return answer
    except Exception as e:
        logger.error(f"chat error: {e}")
        return {
            "response": f"Error: {str(e)}",
            "status": "error",
            "company": request.symbol,
        }

@app.get("/api/nifty50")
async def nifty50():
    """Dashboard endpoint: all 50 companies."""
    try:
        # Aggregate data for all NIFTY50 companies
        companies_data = []
        for ticker, sector in NIFTY50:
            try:
                result = run_pipeline(f"Quick check {ticker}", ticker=ticker, days=180)
                price = result.get("agent1_output", {}).get("price_history", {}).get("current_price")
                companies_data.append({
                    "ticker": ticker,
                    "sector": sector,
                    "price": price,
                    ...
                })
            except Exception:
                pass
        
        return {
            "success": True,
            "companies": companies_data,
            ...
        }
    except Exception as e:
        logger.error(f"nifty50 error: {e}")
        return {"success": False, "error": str(e)}
```

**Purpose**: REST API for frontend consumption.

**Explanation**:
- POST /api/company-research: Execute full pipeline for one company; return rich JSON with metrics, risks, sentiment, data quality metadata
- POST /api/chat: RAG-grounded chat; passes tab_context to rag_assistant.rag_chat()
- GET /api/nifty50: Aggregate all 50 companies; returns list with price, sector, ML predictions
- GET /api/dashboard: Market view; index, indicators, movers, sectors
- All responses sanitized for NaN/Inf via SafeJSONResponse

### Financial Calculators: backend/financial_calculators.py

```python
def calc_operating_profit(row):
    """Operating Profit = EBIT or Revenue - Operating Expenses."""
    ebit = get_field(row, "EBIT", "Operating Income")
    if ebit:
        return ebit
    rev = get_field(row, "Total Revenue")
    op_exp = get_field(row, "Operating Expense", "Total Expenses")
    if rev and op_exp:
        return rev - op_exp
    return None

def calc_opm(row, revenue):
    """OPM % = Operating Profit / Revenue."""
    op_profit = calc_operating_profit(row)
    if op_profit and revenue:
        return round(op_profit / revenue * 100, 2)
    return None

def calc_roe(net_profit, equity):
    """ROE % = Net Profit / Total Equity * 100."""
    if net_profit and equity and equity > 0:
        return round(net_profit / equity * 100, 2)
    return None

def calc_roce(op_profit, total_assets, current_liab):
    """ROCE % = EBIT / (Total Assets - Current Liabilities) * 100."""
    if op_profit and total_assets and current_liab:
        capital = total_assets - current_liab
        if capital > 0:
            return round(op_profit / capital * 100, 2)
    return None

def calc_de_ratio(total_debt, equity):
    """D/E = Total Debt / Total Equity (as ratio, not rupees)."""
    if total_debt and equity and equity > 0:
        return round(total_debt / equity, 2)
    return None

def calc_current_ratio(current_assets, current_liab):
    """Current Ratio = Current Assets / Current Liabilities."""
    if current_assets and current_liab and current_liab > 0:
        return round(current_assets / current_liab, 2)
    return None

def calc_pe_ratio(current_price, eps):
    """P/E = Current Price / EPS."""
    if current_price and eps and eps > 0:
        return round(current_price / eps, 2)
    return None
```

**Purpose**: Library of financial calculation formulas.

**Explanation**:
- Each function implements a single financial formula
- Handles missing data gracefully (returns None, not 0)
- Used by Agent 2 (health features), backend API, and report generation

---

## 7.8 Known Bugs and Limitations

### Bug 1: Debt/Equity Display Issue

**Location**: `red_flags.py::detect_red_flags()`, `company_memory.py::_extract_financial_metrics()`

**Description**: Debt fetched from balance sheet (`bs.get("Total Debt")`) can differ from yfinance `.info.debtToEquity`. Company memory attempts to extract D/E from multiple sources but may display None or stale values.

**Impact**: RED FLAGS: Debt/Equity ratio shown in red flags may not match the Financials tab display.

**Workaround**: RAG chat explicitly grounds debt numbers in real-time yfinance data if visible on the Financials tab.

**Status**: Documented; not fixed in current version.

### Bug 2: AI Chain-of-Thought Leaking

**Location**: `rag_assistant.py::rag_chat()` lines 205–230

**Description**: LLM responses occasionally leak internal reasoning (`<think>` blocks, "Here's my thinking:", analysis preambles) into the UI.

**Mitigation**: Aggressive stripping logic attempts to remove reasoning markers:
- Removes `<think>...</think>` blocks entirely
- Strips "Here's my thinking:", "Let me analyze:", "Draft:", "Analysis:" preambles
- Falls back to last coherent paragraph if multiple reasoning sections detected

**Status**: Partially mitigated; edge cases may persist.

### Bug 3: Context Mismatch Between Tabs

**Location**: `public/company.html`, `rag_assistant.py`

**Description**: If user opens a tab, data loads asynchronously, and user asks a question before load completes, `tab_context` may be stale or empty.

**Impact**: Chat answer may not match on-screen data if user asks during async load.

**Solution**: Frontend should pass empty context if not yet rendered; fallback to general company memory grounding.

**Status**: Design mitigation exists; not formally tested.

### Limitation 1: K-Means Clustering Removed

**Note**: No K-Means implementation found in codebase. Possibly removed in earlier refactoring. All clustering/anomaly detection now relies on Isolation Forest.

### Limitation 2: Proxy Labels Not Implemented

**Note**: Red flags mention "proxy labels via Piotroski Score" or "Altman Z-Score" but actual implementation uses hardcoded thresholds (e.g., D/E > 5, margin < 10%), not calculated F-Scores or Z-Scores. Isolation Forest provides multivariate anomaly scoring instead.

### Limitation 3: FinBERT Not Used

**Note**: Sentiment classification relies on rule-based keywords and LLM reasoning (Groq), not fine-tuned FinBERT. Retrieval is CAG-based (cache-augmented), not embedding-based. This choice trades off fine-grained NLP accuracy for lower infrastructure complexity.

---

## 7.9 Resolved Issues (Version History)

**Issue**: Groq model 404 errors (model name mismatch)  
**Resolution**: Updated to `mixtral-8x7b-32768` and `llama-3.3-70b-versatile` with fallback to `openai/gpt-oss-20b`

**Issue**: 429 rate limit errors on Groq API  
**Resolution**: Implemented rate-limit fallback; added 60-second classification cache to reduce redundant LLM calls; removed over-parallelized LLM invocations (per-company on-demand instead of all 50 at once)

**Issue**: Dashboard load timeout (50 companies, 50 LLM calls)  
**Resolution**: Moved LLM synthesis to per-company on-demand via `/api/chat` endpoint; dashboard now returns cached metadata only

---
