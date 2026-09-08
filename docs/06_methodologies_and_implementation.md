# 6. Methodologies and Implementation

## 6.1 Methods

### Agent 1: Data Fetching Method

Agent 1 employs a **parallel fetching strategy** with hard wall-clock timeout to collect 10+ data streams within a predictable 55-second budget. Each stream targets a specific data source (yfinance, NewsAPI, web scraping) and runs independently. If any stream times out, partial data is returned rather than failing the entire request. This "optimistic degradation" ensures that missing analyst data does not block news retrieval.

### Agent 2: Fundamental Health Analysis Method

Agent 2 combines three complementary approaches:

1. **Absolute Metric Analysis**: Computes 12 financial ratios (ROCE, OPM, D/E, current ratio, etc.) from standardized balance sheet and income statement line items. Thresholds (e.g., ROCE < 10% weak, > 20% strong) are applied to label each metric.

2. **Peer Percentile Ranking**: For each metric, calculates the company's percentile rank among its sector peers (0–100), where 50 = sector median. This contextualization addresses the problem that a company with D/E of 1.2 may appear risky in isolation but reasonable if sector median is 1.8.

3. **Multivariate Anomaly Detection via Isolation Forest**: Detects companies with unusual combinations of financial characteristics (e.g., high debt + low liquidity + high margins = potential stress despite headline profitability). The model scores each company on 15 z-scored features; anomaly_score quantifies deviation from normal distribution. A score ≥ 0.7 flags the company for manual review.

### Agent 3: Market Intelligence & Perception Method

Agent 3 synthesizes four dimensions of market data into a unified narrative:

1. **Event Extraction**: Classifies recent news articles by sentiment (positive/negative/neutral) to assess whether headlines are creating tailwinds or headwinds.

2. **Analyst Consensus**: Aggregates analyst buy/hold/sell recommendations, target prices, and upside/downside percentages to quantify consensus expectations.

3. **Price Performance**: Calculates returns over multiple horizons (1D, 1M, 6M, 1Y) and technical signals (moving averages, support/resistance) to contextualize where the stock sits in its cycle.

4. **Narrative Synthesis**: LLM-powered summarization (via Groq) that converts raw signals into investor-friendly language: "Analysts are bullish with 8% upside, but recent news has been mixed, and price is near its 52-week high."

### Agent 4: Report Synthesis via 4-Stage Reasoning

Agent 4 implements a four-stage pipeline:

**Stage 1 – Question Classification**: An LLM (Groq llama-3.3-70b or mixtral-8x7b) categorizes the user's question into one of 13 intents (financial_health, explanation, comparison, etc.). Results are cached for 60 seconds to avoid redundant LLM calls.

**Stage 2 – Context Retrieval**: Based on the classified intent, Agent 4 selects relevant memory sections. A financial_health question retrieves company_info, financial_metrics, and peer_comparison; an education question retrieves only the definition and examples.

**Stage 3 – Reasoning**: A specialized generator is invoked for each intent class. For example:
- `_generate_financial_health_answer()` interprets debt levels, ROE, and peer percentiles into risk assessment
- `_generate_comparison_answer()` structures a side-by-side metrics table
- `_generate_unsupported_answer()` rejects speculative predictions ("I cannot reliably forecast future prices")

**Stage 4 – Answer Generation & Grounding**: The generator produces text, optionally invoking the Groq LLM to synthesize complex narratives. The response is grounded in the retrieved context to prevent hallucination. If a chat request includes `tab_context` (the exact on-screen tab data), the LLM prioritizes these numbers in its response.

---

## 6.2 Models

### Isolation Forest (Anomaly Detection)

**Training Setup**: Pre-trained on NIFTY 50 historical financial data (date of training not documented in code; model file: `agent_2/isolation_forest_model.pkl`).

**Features (15 z-scored financial ratios)**:
- Leverage: Debt To Equity, Debt Ratio, Net Debt To EBITDA, Total Debt To Capitalization
- Liquidity: Current Ratio, Quick Ratio, Cash Ratio
- Profitability: Net Profit Margin, Operating Profit Margin, ROE, ROIC
- Quality: Income Quality (OCF/NI), Cash Flow To Debt, Interest Coverage, Asset Turnover

**Algorithm**: Isolation Forest isolates anomalies by randomly selecting features and split values; anomalies are isolated in fewer splits, resulting in shorter path lengths in the forest.

**Output**:
- `prediction`: 1 (normal) or -1 (anomaly)
- `decision_function`: Continuous score (negative = anomalous, positive = normal)
- `anomaly_score`: Normalized 0–1 where higher = more anomalous
- Threshold: `is_anomaly = prediction == -1` or `anomaly_score ≥ 0.7`

**Validation**: Applied to every company during Agent 2 execution; results feed into red flag detection and fundamental_profile scoring.

### XGBoost Price Prediction (Classifier + Regressor)

**Classifier Model** (`xgb_classifier.pkl`): Predicts price direction (UP=1, DOWN=0)

**Regressor Model** (`xgb_regressor.pkl`): Predicts magnitude of price change (% return)

**Features (9 technical indicators)**:
- Returns (daily percentage change)
- Simple Moving Averages (SMA 5, SMA 20)
- Relative Strength Index (RSI)
- MACD (Moving Average Convergence Divergence)
- Bollinger Band width (2-std volatility measure)
- Volume ratio (today vs. 20-day average)
- Volatility (standard deviation of returns)
- Momentum (price rate of change)

**Training**: Not performed during project execution; pre-trained models assumed to exist. `prediction_service.py` loads and invokes them.

**Usage**: Dashboard predictions for top gainers/losers. Output: `{current_price, predicted_price, expected_return %, direction}`.

**Caching**: 15-minute TTL per ticker to avoid recomputation.

**Fallback**: If model load fails, uses simple heuristic: if recent trend is up, predict +5% return; if down, predict -3%.

### Cache-Augmented Generation (CAG) for Report Synthesis

**Architecture**: Agent 4 does not use traditional embedding-based RAG (e.g., FinBERT + vector database). Instead, it uses Cache-Augmented Generation:

1. **Context Storage**: Sector metrics, macro indicators (NIFTY 50 returns, bond yields, forex), and reference documents (RBI monetary policy summaries, Zerodha Varsity articles) are pre-stored in a cache layer.

2. **Query-Time Retrieval**: When synthesizing a report, Agent 4 identifies which sector/macro/reference context is relevant to the company and retrieves it.

3. **LLM Grounding**: Groq LLM is provided the company memory plus retrieved context, ensuring synthesis is grounded in actual data rather than hallucinated.

**Benefit**: Avoids expensive fine-tuning of FinBERT or maintaining a vector database; leverages the LLM's reasoning ability to connect dots between company metrics and market context.

---

## 6.3 Model Implementation Workflow

**Fig. 6.3: Fundamental Health Scoring Workflow**

The following sequence describes the end-to-end health scoring process for a single company:

```
1. INPUT: ticker = "TCS.NS"
   │
   ├─→ 2. FETCH: build_health_features(ticker)
   │       ├─ yfinance balance sheet (current quarter)
   │       ├─ yfinance income statement (current quarter)
   │       ├─ yfinance cash flow (current quarter)
   │       └─ Output: feature_vector = {ROCE: 23.5, Debt: 5000, ...}
   │
   ├─→ 3. PEER COMPARISON: compare_peers(ticker, feature_vector)
   │       ├─ Fetch sector = "Technology"
   │       ├─ Identify peers = [INFY.NS, WIPRO.NS, HCLTECH.NS, ...]
   │       ├─ ThreadPoolExecutor (8 workers, 20s timeout)
   │       │  └─ fetch_health_features(peer) for each peer
   │       ├─ Calculate percentile for each metric
   │       └─ Output: peer_comparison = {
   │           "sector": "Technology",
   │           "metrics": {
   │             "ROCE": {"company": 23.5, "sector_average": 18.2, "percentile": 78},
   │             ...
   │           }
   │         }
   │
   ├─→ 4. ANOMALY DETECTION: assess_isolation_forest(ticker)
   │       ├─ build_features(ticker) → 15 z-scored ratios
   │       ├─ Load model from isolation_forest_model.pkl
   │       ├─ Predict via model.predict(feature_vector)
   │       ├─ Score via model.decision_function()
   │       └─ Output: model_assessment = {
   │           "prediction": 1 | -1,
   │           "anomaly_score": 0.34,
   │           "is_anomaly": false
   │         }
   │
   ├─→ 5. RED FLAGS: detect_red_flags(ticker)
   │       ├─ Check 5 hardcoded conditions (high debt, low margin, etc.)
   │       ├─ Add Isolation Forest anomaly result to flags
   │       └─ Output: red_flags = [
   │           {"metric": "Low ROCE", "severity": "low", ...},
   │           ...
   │         ]
   │
   ├─→ 6. FUNDAMENTAL SIGNALS: analyze_fundamentals(peer_comparison, red_flags)
   │       ├─ Extract strengths (metrics > 70th percentile)
   │       ├─ Extract weaknesses (metrics < 30th percentile)
   │       └─ Output: fundamental_signals = {
   │           "strengths": ["High ROCE", "Strong cash flow"],
   │           "weaknesses": []
   │         }
   │
   └─→ 7. AGGREGATE: Agent 2 output
       {
         "ticker": "TCS.NS",
         "financial_facts": {...},
         "red_flags": [...],
         "model_assessment": {...},
         "peer_comparison": {...},
         "fundamental_signals": {...}
       }
```

---

## 6.4 Internal Implementation Workflow

Agents hand off data via the pipeline orchestrator. No shared memory between agents; all communication is message-passing:

```
Agent 1 Output (JSON)
    │
    ├─→ Agent 2 Input ──→ Agent 2 Processing ──→ Agent 2 Output (JSON)
    │                                                    │
    └─→ Agent 3 Input ──→ Agent 3 Processing ──→ Agent 3 Output (JSON)
                                                         │
                ┌────────────────────────────────────────┘
                │
                ├─→ Agent 4 Input (Agents 1, 2, 3 outputs) ──→ Agent 4 Processing ──→ Agent 4 Output
                │
                └─→ Company Memory Builder ──→ Unified Memory State (20+ sections)
```

---

## 6.5 Integration/Orchestration Logic

The `pipeline.py::run_pipeline()` function orchestrates all agents:

1. Extract companies from query (fuzzy match or explicit ticker)
2. Check cache; return if hit
3. Run Agent 1 (55-second budget); handle timeout gracefully
4. Submit Agents 2 & 3 to ThreadPoolExecutor; wait for both (60-second combined timeout)
5. Run Agent 4 (sequential, no timeout but 60-second classification cache)
6. Build unified company memory
7. Cache result (10-minute TTL)
8. Return aggregated output to caller

**Why LangGraph was not used**: The project originally considered LangChain's LangGraph for agent state management but opted for explicit Python control flow (ThreadPoolExecutor, timeouts, caching) for:
- Explicit timeout budgets per agent (55s for Agent 1, 60s for Agents 2&3)
- Fine-grained error handling (partial data if timeout)
- Simpler debugging (direct print statements, no state machine)
- Lighter dependency footprint

---

## 6.6 Interface & Integration

### FastAPI Backend Integration

`backend/main.py` provides REST endpoints:

- **`POST /api/company-research`**: Accepts company name + ticker + optional chat query → returns rich JSON
- **`POST /api/chat`**: Accepts company + question + tab context → returns RAG-grounded answer
- **`POST /api/generate-report`**: Generates downloadable HTML report
- **`GET /api/nifty50`**: Dashboard data (50 companies, index, predictions)
- **`GET /api/dashboard`**: Full market view

All responses sanitized for NaN/Inf; all include `_data_quality` metadata.

### Groq LLM Integration

Two points of LLM integration:

1. **Agent 4 Intent Classification**: Groq llama-3.3-70b or mixtral-8x7b classifies question intent (60-second cache).
2. **RAG Chat (`rag_assistant.py`)**: Groq used for free-form question answering grounded in company context + tab data.

Rate limit fallback: If Groq returns 429, retry on "openai/gpt-oss-20b" (separate quota pool).

### Frontend Integration

HTML/Tailwind/Plotly.js frontend receives JSON responses and renders:

- Dashboard: Index chart, market indicators, top movers (with ML predictions), sector heatmap
- Company Research: 6 tabs (overview, financials, peers, sentiment, events, risks)
- Per-tab Chat: User asks question → backend receives tab_context → RAG grounds response in on-screen data

---
