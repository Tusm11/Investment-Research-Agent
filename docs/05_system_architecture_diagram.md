# 5. System Architecture Diagram

## 5.1 Architecture Overview

The system follows a layered, agent-oriented architecture with explicit data handoffs and caching at each stage.

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE LAYER                        │
│  Dashboard (all 50 cos)  │  Company Research (tabs)  │  Chat     │
└─────────────────────────┬───────────────────────────┬────────────┘
                          │                           │
                    ┌─────▼─────────────────────────────▼────────┐
                    │      FASTAPI BACKEND (main.py)             │
                    │  Endpoints: /api/company-research          │
                    │             /api/nifty50                   │
                    │             /api/chat                      │
                    │             /api/generate-report           │
                    └──────────────────┬──────────────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────────────┐
                    │   PIPELINE ORCHESTRATOR (pipeline.py)    │
                    │  - Extract companies (fuzzy match)       │
                    │  - Check cache (10min TTL)               │
                    │  - Route to agents                       │
                    │  - Collect outputs                       │
                    └──┬──────────────┬─────────────────────┬──┘
                       │              │                     │
         ┌─────────────▼─┐ ┌─────────▼──────┐ ┌────────────▼─────┐
         │   AGENT 1     │ │  AGENT 2 & 3   │ │    AGENT 4       │
         │ (Sequential)  │ │   (Parallel)   │ │ (Sequential)     │
         │               │ │                │ │                  │
         │ Data Fetch    │ │ Fundamental    │ │ 4-Stage Reasoning│
         │ ─────────────▼ │ Analysis &     │ │ ──────────────▼  │
         │ 55s budget    │ │ Market Intel   │ │ Intent Class    │
         │               │ │                │ │ Context Retrieval│
         │ yfinance      │ │ 60s timeout    │ │ Answer Generation│
         │ News API      │ │ (combined)     │ │                  │
         │ Analyst data  │ │                │ │ Groq LLM        │
         │               │ │ Isolation      │ │ (60s cache)     │
         │               │ │ Forest model   │ │                  │
         │               │ │                │ │ RAG (tab-aware) │
         └──────┬────────┘ └────────┬───────┘ └────────┬────────┘
                │                   │                   │
                └───────────────────┴───────────────────┘
                                    │
                         ┌──────────▼────────────┐
                         │  COMPANY MEMORY       │
                         │  (unified_state.py)   │
                         │  20+ sections:        │
                         │  - company_info       │
                         │  - financial_metrics  │
                         │  - peer_comparison    │
                         │  - red_flags          │
                         │  - risks/opportunities│
                         │  - market_intelligence│
                         │  (+ cache to disk)    │
                         └──────────┬────────────┘
                                    │
                         ┌──────────▼──────────────┐
                         │  API RESPONSE +         │
                         │  CACHE (10min TTL)      │
                         │  - HTML Report          │
                         │  - Dashboard JSON       │
                         │  - Chat Answer          │
                         │  _data_quality metadata │
                         └─────────────────────────┘
```

## 5.2 Agent Data Flow Sequence

**Fig. 5.1: System Architecture and Data Flow**

The following sequence describes the end-to-end research request for a single company:

1. **User Input**: User submits a research question or selects a company from the dashboard.

2. **Extraction**: `pipeline.py::extract_companies()` uses fuzzy matching and the NIFTY50 list to identify which companies are mentioned.

3. **Cache Check**: `_get_cached()` checks if results for this company exist in memory with TTL < 600s. If cache hit, skip to step 10.

4. **Agent 1 Execution**: `fetch_all_data()` is invoked with a 55-second hard wall-clock timeout. Parallel ThreadPoolExecutor (6 workers) fetches:
   - Price history (yfinance, 180 days)
   - News articles (Google News RSS + NewsAPI fallback)
   - Analyst consensus (yfinance `.info`, recommendation summary)
   - Company info (sector, industry, market cap, fundamentals)
   - Financial metrics (yfinance income statement, balance sheet, cash flow)
   - Market drivers (NIFTY 50, BankNifty, forex, commodities, peer averages)
   - Company website context (Investor Relations web scraping)

   Output: Agent 1 payload with all data streams or partial data if timeout.

5. **Agent 2 & 3 Parallel Execution**: After Agent 1 completes, Agents 2 and 3 are submitted to ThreadPoolExecutor (max 2 workers) with a 60-second combined timeout.

   **Agent 2** processes Agent 1 output:
   - Extracts 12 TARGET_METRICS (ROCE, Debt, Sales, OPM, etc.) via `build_health_features()`
   - Compares peers: ThreadPoolExecutor (8 workers, 20s timeout) fetches all peers' metrics; calculates percentile ranks
   - Runs Isolation Forest model on 15 z-scored features; outputs anomaly_score, prediction (anomaly yes/no)
   - Detects red flags using 5 hardcoded thresholds + Isolation Forest result
   - Derives strengths/weaknesses from percentile ranks

   **Agent 3** processes Agent 1 output:
   - Routes query to relevant modules (news, analyst, price, comparison, future outlook)
   - Extracts news events; classifies sentiment (positive/negative/neutral)
   - Fetches analyst consensus and recommendation
   - Creates price chart data for Plotly
   - Synthesizes market intelligence narrative
   - Determines sentiment (Bullish, Bearish, Neutral, or None if no data)

6. **Agent 4 Execution**: After Agents 2 & 3 complete, Agent 4 processes the full context:
   - Classifies the user question intent using LLM (60-second cache on classification result)
   - Retrieves relevant memory sections based on intent
   - Routes to specialized answer generator (financial_health, comparison, education, etc.)
   - Invokes Groq LLM with system prompt + context; falls back to "openai/gpt-oss-20b" on rate limit
   - Strips reasoning leaks from response
   - Returns structured answer

7. **Memory Building**: `build_company_memory()` aggregates Agent 1/2/3 outputs into unified 20-section state:
   - company_info, financial_metrics, peer_comparison, red_flags, price_data, chart_metrics, market_stats, risks, opportunities, market_intelligence, etc.

8. **Cache Storage**: Entire pipeline result cached with 10-minute TTL; persisted to `company_memory.json`.

9. **API Response Construction**: `backend/main.py` sanitizes JSON (replaces NaN/Inf), adds `_data_quality` metadata (which sources returned data, confidence), and returns rich response.

10. **Response Delivery**: Structured JSON response includes company info, metrics, red flags, risk model results, analyst data, price forecast, sector metrics, and optionally a chat answer if the user provided a question.

11. **Frontend Rendering**: Dashboard or company detail page renders tabs; per-tab chat uses `tab_context` to ground responses in on-screen data.

---

## 5.3 Cache Layers

| Cache | Scope | TTL | Trigger |
|-------|-------|-----|---------|
| Pipeline cache | Per-company result (all agents) | 10 min | company ticker |
| Agent 4 classification | Question classification result | 60 s | question text |
| Prediction service | XGBoost predictions per ticker | 15 min | ticker |
| yfinance info cache | yfinance .info API call | Process lifetime | ticker |
| RAG context cache | Built company memory | 10 min | company ticker |

---
