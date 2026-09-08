# 8. Pipeline Summary

## 8.1 End-to-End Research Request Flow

The following sequence describes the complete flow from user query to final output artifact.

### Stage 0: Input

User submits a research request via one of three channels:

1. **CLI**: `python main.py "Is TCS financially healthy?" --ticker TCS.NS --days 180`
2. **REST API**: `POST /api/company-research { name: "Tata Consultancy Services", ticker: "TCS.NS", days: 180, chat_query: "Optional question" }`
3. **Web Dashboard**: User selects company from dropdown; frontend calls `/api/company-research`

### Stage 1: Company Extraction and Cache Check

```
Input: query = "Is TCS financially healthy?"
  │
  ├─→ extract_companies(query) via fuzzy matching
  │   └─→ Identifies: ["TCS.NS"]
  │
  ├─→ Check cache_key("TCS") in CACHE
  │   ├─ If hit (TTL < 600s) → Jump to Stage 8 (return cached)
  │   └─ If miss → Continue
  │
  └─→ primary_ticker = "TCS.NS"
```

### Stage 2: Agent 1 Execution (Data Fetching)

```
Input: ticker = "TCS.NS", days = 180, news_limit = 12
  │
  ├─→ fetch_all_data(ticker) with 55-second budget
  │   │
  │   ├─→ ThreadPoolExecutor (6 workers)
  │   │   ├─ fetch_price_history() → OHLCV, 52W range, avg volume
  │   │   ├─ fetch_news_articles() → Headlines + sentiment
  │   │   ├─ fetch_analyst_consensus() → Target price, buy/hold/sell
  │   │   ├─ fetch_company_info() → Sector, industry, market cap, ratios
  │   │   ├─ fetch_financial_metrics() → ROE, margins, debt/equity
  │   │   └─ fetch_market_drivers() → NIFTY 50, macro, peer averages
  │   │
  │   ├─→ Monitor wall-clock time; cancel tasks if > 55s
  │   │
  │   └─→ Output: agent1_output with 6 data streams (partial if timeout)
  │
  └─→ Validate: wrap_result() with status (SUCCESS, RETRIEVAL_ERROR, TIMEOUT)
```

**Agent 1 Output** (JSON structure):
```json
{
  "ticker": "TCS.NS",
  "company_info": {...},
  "price_history": {...},
  "news": [...],
  "analyst_data": {...},
  "financial_metrics": {...},
  "market_drivers": {...},
  "_fetch_complete_time": 23.4
}
```

### Stage 3: Agents 2 & 3 Parallel Execution

After Agent 1 completes, Agents 2 and 3 are submitted to ThreadPoolExecutor (max 2 workers) with 60-second combined timeout.

#### Agent 2: Fundamental Health Analysis
```
Input: agent1_output
  │
  ├─→ build_health_features(ticker)
  │   └─ Extracts 12 TARGET_METRICS (ROCE, Debt, OPM, etc.)
  │
  ├─→ compare_peers(ticker, company_features)
  │   ├─ Identify sector peers
  │   ├─ ThreadPoolExecutor (8 workers, 20s timeout) fetches peer metrics
  │   └─ Calculate percentile ranks for each metric
  │
  ├─→ assess_isolation_forest(ticker)
  │   ├─ Load pre-trained model
  │   ├─ Build 15 z-scored features
  │   └─ Predict: -1 (anomaly) or +1 (normal); anomaly_score 0–1
  │
  ├─→ detect_red_flags(ticker)
  │   ├─ Check 5 hardcoded thresholds
  │   ├─ Include Isolation Forest result
  │   └─ Return severity-tagged flags (high/medium/low)
  │
  └─→ Output: agent2_output with red flags, peer comparison, model assessment
```

#### Agent 3: Market Intelligence & Perception
```
Input: agent1_output, question
  │
  ├─→ _route_query(question)
  │   └─ Determine which modules to run (news, analyst, price, comparison, future)
  │
  ├─→ extract_events(news)
  │   └─ Classify sentiment (positive/negative/neutral)
  │
  ├─→ get_analyst_consensus(ticker)
  │   └─ Fetch recommendation, target, analyst counts
  │
  ├─→ create_price_chart(ticker, price_data, events)
  │   └─ Generate chart JSON for Plotly rendering
  │
  ├─→ Determine sentiment
  │   ├─ If analyst recommendation available → map to Bullish/Bearish/Neutral
  │   ├─ Else if news sentiment available → aggregate event sentiment
  │   └─ Else → None (do not default to 50)
  │
  └─→ Output: agent3_output with sentiment, market intelligence, risks, opportunities
```

### Stage 4: Agent 4 Execution (Report Synthesis)

After Agents 2 & 3 complete, Agent 4 runs sequentially.

```
Input: question, agent1_output, agent2_output, agent3_output
  │
  ├─→ classify_question(question)
  │   ├─ Check 60-second classification cache
  │   ├─ If hit → use cached classification
  │   ├─ Else → invoke Groq LLM (mixtral-8x7b or llama-3.3-70b)
  │   ├─ LLM returns: intent, entities, needs, tools
  │   └─ Cache result for 60s
  │
  ├─→ retrieve_context(memory, required_sections)
  │   └─ Filter to relevant memory sections based on intent
  │
  ├─→ answer_with_reasoning(query, memory, context, intent)
  │   ├─ Route to specialized generator
  │   │   ├─ financial_health → Debt analysis, ROE interpretation
  │   │   ├─ comparison → Side-by-side metrics
  │   │   ├─ calculation → CAGR, future value
  │   │   ├─ education → Concept explanation
  │   │   ├─ unsupported → Reject price predictions
  │   │   ├─ historical_performance → Return calculations (1D, 1M, 1Y, 5Y)
  │   │   ├─ sector_ranking → Best/worst peers
  │   │   ├─ investment_simulator → Historical returns
  │   │   └─ [other intents]
  │   │
  │   └─ Optionally invoke Groq LLM with context to synthesize narrative
  │
  └─→ Output: agent4_output with response, intent, target_price, reasoning_steps
```

### Stage 5: Company Memory Building

```
Input: agent1_output, agent2_output, agent3_output
  │
  ├─→ build_company_memory(...)
  │   ├─ Aggregate 20+ memory sections:
  │   │   ├─ company_info, financial_metrics, financial_facts
  │   │   ├─ peer_comparison, anomaly_detection, price_data, chart_metrics
  │   │   ├─ market_stats, risk_metrics, news_articles, events
  │   │   ├─ analyst_data, risks, opportunities, market_intelligence
  │   │   ├─ dashboard (business_fundamentals, market_mood, price_story, financial_stability)
  │   │   └─ [15 more sections]
  │   │
  │   ├─ Derive missing sections
  │   │   ├─ If risks empty → derive from metrics (low ROCE, high debt, etc.)
  │   │   └─ If opportunities empty → derive from positive factors
  │   │
  │   └─ Output: unified memory state (dict with 20+ keys)
  │
  └─→ save_company_memory(memory) to company_memory.json (disk persistence)
```

### Stage 6: Cache Storage

```
Input: pipeline_result
  │
  ├─→ _set_cached(cache_key, {
  │       agent1: agent1_output,
  │       agent2: agent2_output,
  │       agent3: agent3_output
  │   })
  │
  ├─→ Set TTL = 600 seconds (10 minutes)
  │
  └─→ Cache persists in memory; subsequent requests for same company within 10min use cached results
```

### Stage 7: API Response Construction

```
Input: memory, agent outputs
  │
  ├─→ Sanitize JSON
  │   ├─ Replace NaN → 0.0
  │   ├─ Replace Infinity → 999999.0
  │   └─ Ensure all floats are valid IEEE 754
  │
  ├─→ Build _data_quality metadata
  │   ├─ price_available: current_price is not None
  │   ├─ news_available: news articles count > 0
  │   ├─ sentiment_analyzed: sentiment is not None (only true if analysis ran)
  │   ├─ risks_identified: red flags count > 0
  │   ├─ peer_data_available: peer_comparison metrics exist
  │   └─ analysis_errors: list of caught exceptions
  │
  └─→ Construct response JSON
      {
        "success": true,
        "ticker": "TCS.NS",
        "company_name": "Tata Consultancy Services",
        "sector": "Technology",
        "current_price": 3200.0,
        "financial_metrics": {...},
        "red_flags": [...],
        "peer_comparison": {...},
        "sentiment_score": 75,  # if sentiment == "Bullish"
        "expected_return": 8.5,
        "risks": [...],
        "opportunities": [...],
        "_data_quality": {...},
        "_data_sources": {...}
      }
```

### Stage 8: Response Delivery

Response is returned to caller (CLI prints JSON, API returns HTTP 200 with JSON body, frontend renders tabs).

### Stage 9: Optional Chat Processing

If user provides a `chat_query`, RAG processing is triggered:

```
Input: chat_query, memory, agent2_output, ticker, tab_context
  │
  ├─→ rag_chat(question, memory, agent2_output, ticker, tab_context)
  │   │
  │   ├─ Validate company ticker
  │   ├─ Check question relevance (block crypto, forex, personal advice, etc.)
  │   │
  │   ├─ Build company context from memory + red flags
  │   ├─ Inject tab_context (exact on-screen data) into system prompt
  │   │
  │   ├─ Call Groq LLM
  │   │   ├─ If 429 rate limit → retry on openai/gpt-oss-20b (fallback model)
  │   │   └─ If other error → return error status
  │   │
  │   ├─ Strip reasoning leaks
  │   │   ├─ Remove <think> blocks
  │   │   ├─ Strip "Here's my thinking:", "Let me analyze:", etc.
  │   │   └─ Take last coherent paragraph if multiple reasoning sections
  │   │
  │   └─ Output: { response: str, status: "success|error|blocked", company: ticker }
  │
  └─→ Return chat answer to user
```

---

## 8.2 Key Concepts Demonstrated

1. **Multi-Agent Orchestration**: Four specialized agents with explicit data handoffs; no shared mutable state.

2. **Self-Supervised Proxy Labeling**: Isolation Forest trained on z-scored financial ratios detects anomalies without ground-truth labels; Altman Z-Score / Piotroski F-Score concepts inspired the feature selection.

3. **Cache-Augmented Generation (CAG)**: Retrieval is cache-based (not embedding-based); LLM synthesis grounded in stored company memory + sector context.

4. **Rule-Based + LLM Synthesis**: Red flags identified via hardcoded thresholds + Isolation Forest; final narrative synthesized by Groq LLM.

5. **Scope-Disciplined ML**: XGBoost used only for price direction/magnitude; Isolation Forest for anomaly detection. K-Means abandoned. No model for every problem.

6. **Timeout Budgets & Graceful Degradation**: Agent 1 has 55-second hard wall-clock timeout; partial data returned if exceeded. Agents 2 & 3 have 60-second combined timeout; continue if one fails.

7. **Context-Aware RAG**: Chat grounded in exact tab_context (rendered on-screen data); prevents hallucination by matching numbers first.

8. **Rate-Limit Resilience**: Groq LLM rate-limit (429) triggers fallback to openai/gpt-oss-20b (separate quota pool).

---

## 8.3 Data Hand-Offs

```
Agent 1 Output (agent1_output)
    ↓
    ├→ Agent 2 Input (read-only)
    │   ├─ Extracts company_info for sector lookup
    │   ├─ Extracts price_history for correlation
    │   └─ Returns: agent2_output (red_flags, peer_comparison, model_assessment)
    │
    ├→ Agent 3 Input (read-only)
    │   ├─ Extracts news for event extraction
    │   ├─ Extracts price_history for chart
    │   └─ Returns: agent3_output (sentiment, market_intelligence, risks, opportunities)
    │
    └→ Agent 4 Input (read-only, along with agent2_output, agent3_output)
        ├─ Builds unified memory from all three agent outputs
        ├─ Synthesizes reasoning-based answers
        └─ Returns: agent4_output (response, intent, target_price)

All outputs (agent1, agent2, agent3, agent4, memory)
    ↓
    └→ Cache & Disk Persistence (company_memory.json)
        ↓
        └→ FastAPI Response (sanitized JSON with metadata)
            ↓
            └→ Frontend (tabs, charts, chat, download report)
```

---

## 8.4 Sequence Diagram

**Fig. 8.1: End-to-End Research Pipeline Sequence**

```
User / API Client
        │
        │ query: "Is TCS healthy?" (or POST /api/company-research)
        │
        ├──→ main.py / backend.main.py
        │
        ├──→ pipeline.run_pipeline()
        │        │
        │        ├─→ extract_companies(query) → ["TCS.NS"]
        │        │
        │        ├─→ _get_cached(key) → None (no cache hit)
        │        │
        │        ├─→ Agent 1: fetch_all_data(ticker)
        │        │   │ [6 parallel data streams, 55s budget]
        │        │   └─→ agent1_output
        │        │
        │        ├─→ Agents 2 & 3: Parallel Execution (ThreadPoolExecutor, 2 workers, 60s timeout)
        │        │   │
        │        │   ├─→ run_agent2(agent1_output)
        │        │   │   │ [peer comparison, red flags, Isolation Forest]
        │        │   │   └─→ agent2_output
        │        │   │
        │        │   ├─→ run_agent3(agent1_output, question)
        │        │   │   │ [event extraction, sentiment, market synthesis]
        │        │   │   └─→ agent3_output
        │        │   │
        │        │   └─ Wait for both to complete or timeout
        │        │
        │        ├─→ Agent 4: run_agent4(question, agent1, agent2, agent3)
        │        │   │ [4-stage reasoning: classify → retrieve → reason → answer]
        │        │   └─→ agent4_output
        │        │
        │        ├─→ build_company_memory(agent1, agent2, agent3)
        │        │   └─→ memory (20+ sections)
        │        │
        │        ├─→ _set_cached(key, results) [10min TTL]
        │        │
        │        └─→ return {agent1, agent2, agent3, agent4, memory}
        │
        ├──→ backend.main.py::company_research()
        │        │
        │        ├─→ Sanitize JSON (NaN/Inf)
        │        │
        │        ├─→ Build _data_quality metadata
        │        │
        │        └─→ Return HTTP 200 + JSON response
        │
        └──→ Frontend / Client
             │
             ├─ Render company detail tabs
             ├─ Display metrics, red flags, peer comparison
             ├─ Show chart and market intelligence
             └─ Enable per-tab chat (calls /api/chat with tab_context)

If user asks a chat question:
        │
        ├──→ /api/chat { question, symbol, tab, context }
        │        │
        │        ├─→ rag_chat(question, memory, agent2_output, ticker, tab_context)
        │        │   │
        │        │   ├─→ Validate ticker & question relevance
        │        │   ├─→ Build company context + tab_context
        │        │   ├─→ Call Groq LLM (fallback to openai/gpt-oss-20b on 429)
        │        │   ├─→ Strip reasoning leaks
        │        │   └─→ Return { response, status, company }
        │        │
        │        └─→ HTTP 200 + JSON answer
        │
        └──→ Frontend displays answer in chat widget
```

---
