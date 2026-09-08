# 3. Software Requirements Analysis

## 3.1 Modules and Their Functionalities

### 3.1.1 Data Fetching Module (Agent 1)

**Location**: `agent_1/data_fetcher.py`, `agent_1/data_validator.py`, `agent_1/tools/`

**Responsibility**: Parallel collection of 10+ data streams per company within a strict 55-second budget.

**Key Functions**:

- `fetch_price_history(ticker, days=180)`: Retrieves OHLCV data from yfinance; calculates 52-week highs/lows, average volume, trend.
- `fetch_analyst_consensus(ticker)`: Extracts analyst recommendation, target price, upside/downside %, buy/hold/sell breakdown.
- `fetch_company_info(ticker)`: Collects 30+ fields (sector, industry, market cap, P/E, debt/equity, dividend yield, earnings dates, insider holdings).
- `fetch_financial_metrics(ticker)`: ROE, operating margins, debt/equity, current ratio, revenue growth, free cash flow, total revenue.
- `fetch_market_drivers(ticker)`: Parallel sub-fetches for macro (NIFTY 50 index, BankNifty, USD/INR, gold, crude, yields), sector performance (5-peer averages), earnings calendar, promoter activity.
- `fetch_news_articles(ticker, days=180, max_articles=10)`: Google News RSS + NewsAPI fallback; returns headline, summary, source, URL, date.
- `calculate_market_correlation(ticker, ohlcv_data)`: Pearson correlation between daily returns and NIFTY 50; interpretation string included.
- `fetch_company_website_context(ticker, max_pages=3)`: Scrapes investor relations pages; 5s per-page timeout; capped at 2500 chars/page.

**Output Structure**:
```json
{
  "ticker": "TCS.NS",
  "company_info": {...30+ fields...},
  "price_history": {
    "current_price": 3200.0,
    "ohlcv": [[open, high, low, close, volume], ...],
    "week_52_high": 3500.0,
    "week_52_low": 2800.0,
    "average_volume": 5000000
  },
  "news": [{title, summary, source, url, date, sentiment}, ...],
  "analyst_data": {
    "recommendation_key": "buy",
    "target_mean_price": 3500.0,
    "upside_downside_percent": 8.5,
    "buy": 18, "hold": 5, "sell": 2
  },
  "market_drivers": {...},
  "correlation": {...}
}
```

**Caching**: 10-minute TTL shared `_INFO_CACHE` for yfinance `.info` to prevent duplicate expensive calls within a process invocation.

**Error Handling**: `data_validator.py` wraps all outputs with status (SUCCESS, NO_DATA, RETRIEVAL_ERROR, TIMEOUT) and metadata (fetch_time_ms, source, timestamp).

---

### 3.1.2 Fundamental Health Analysis Module (Agent 2)

**Location**: `agent_2/agent.py`, `agent_2/red_flags.py`, `agent_2/health_data.py`, `agent_2/peer_comparison.py`, `agent_2/fundamentals.py`

**Responsibility**: Quantify financial health through 12 target metrics, anomaly detection, peer ranking, and red-flag identification.

**Key Functions**:

- `build_health_features(ticker)`: Extracts 12 TARGET_METRICS from yfinance balance sheet, income statement, cash flow:
  - ROCE % = EBIT / Capital Employed × 100
  - OPM % = Operating Profit / Sales × 100
  - Debt, Sales, Net Profit, Operating Profit, Total Assets, Total Liabilities, Cash from Operations (all in rupees)
  - Debtor Days = (AR / Sales) × 365
  - Inventory Days = (Inventory / COGS) × 365
  - Working Capital Days = ((CA - CL) / Sales) × 365

- `compare_peers(ticker, company_features)`: ThreadPoolExecutor (8 workers, 20s timeout) fetches features for all peers in sector; calculates percentile ranks (0–100) for each metric; returns sector average and peer list.

- `assess_isolation_forest(ticker)`: Loads pre-trained model; builds 15 z-scored feature vector (debt ratios, liquidity, profitability, quality); returns prediction (-1=anomaly, +1=normal), decision_function, anomaly_score (0–1).

- `detect_red_flags(ticker)`: Checks 5 conditions:
  - Incomplete Financial Data (missing revenue or equity) → HIGH severity
  - High Debt (D/E > 5) → HIGH severity
  - Low Profit Margin (< 10%) → MEDIUM severity
  - Low ROE (< 15%) → LOW severity
  - Slow Revenue Growth (< 8%) → LOW severity
  - Isolation Forest anomaly_score ≥ 0.7 → MEDIUM/HIGH severity

- `analyze_fundamentals(peer_comparison, red_flags)`: Derives strengths (ROCE > 20%, OPM > 20%, low debt, strong cash flow, efficient receivables) and weaknesses (ROCE < 10%, OPM < 10%, high debt, slow cash conversion).

**Output Structure**:
```json
{
  "ticker": "TCS.NS",
  "financial_facts": {
    "ROCE": 23.5, "Debt": 5000, "CurrentRatio": 1.8, ...
  },
  "red_flags": [
    {
      "metric": "High Debt",
      "value": "D/E: 1.2",
      "severity": "medium",
      "explanation": "..."
    }
  ],
  "model_assessment": {
    "prediction": 1,
    "anomaly_score": 0.34,
    "is_anomaly": false
  },
  "peer_comparison": {
    "sector": "Technology",
    "peers": ["INFY.NS", "WIPRO.NS", ...],
    "metrics": {
      "ROCE": {"company": 23.5, "sector_average": 18.2, "percentile": 78},
      ...
    }
  },
  "fundamental_signals": {
    "strengths": ["High ROCE", "Strong cash flow"],
    "weaknesses": []
  }
}
```

---

### 3.1.3 Market Intelligence & Perception Module (Agent 3)

**Location**: `agent_3/agent.py`, `agent_3/event_classifier.py`, `agent_3/analyst_consensus.py`, `agent_3/price_chart.py`, `agent_3/market_synthesis.py`, `agent_3/comparison.py`

**Responsibility**: Synthesize market sentiment, analyst views, news events, and price trends into a narrative market intelligence report.

**Key Functions**:

- `_route_query(question)`: Pattern-matches question to determine which analysis modules to run (news, analyst, price, rag, comparison, future).

- `extract_events(news_dict)`: Classifies news articles by sentiment (positive, negative, neutral); extracts headline, summary, source, date.

- `get_analyst_consensus(ticker)`: Fetches recommendation_key, target price, buy/hold/sell counts, number of analysts, upside/downside %.

- `create_price_chart(ticker, price_data, events)`: Generates chart JSON with OHLCV series, event markers, technical signals for Plotly frontend rendering.

- `synthesize_market(ticker, events, analyst_consensus, price_performance, ...)`: Aggregates all inputs into single market intelligence report; outputs market_perception, risk_factors, positive_factors, key_catalysts.

- `compare_tickers(ticker, question)`: Fetches peer metrics for comparison context.

**Output Structure**:
```json
{
  "ticker": "TCS.NS",
  "sentiment": "Bullish|Bearish|Neutral|null",
  "market_intelligence_report": {
    "market_perception": "...",
    "risk_factors": [...],
    "positive_factors": [...]
  },
  "market_facts": {
    "recommendation": "buy",
    "target_price": 3500.0,
    "analyst_count": 25,
    "upside_downside_percent": 8.5,
    "buy": 18, "hold": 5, "sell": 2
  },
  "recent_events": [{title, summary, date, source, sentiment}, ...],
  "risks": [...],
  "opportunities": [...]
}
```

**Note**: No FinBERT or traditional embedding-based retrieval in this agent. Retrieval/context-grounding is handled by Agent 4 (CAG-based).

---

### 3.1.4 Report Synthesis Module (Agent 4)

**Location**: `agent_4/agent.py`, `rag_assistant.py`

**Responsibility**: 4-stage reasoning engine that classifies user intent, retrieves relevant context, reasons about the data, and generates investor-grade conclusions or answers.

**Key Functions**:

- `classify_question(query, memory)`: LLM-powered intent classifier (60-second cache) that maps user questions to 11+ intents (financial_health, explanation, education, comparison, calculation, historical_performance, sector_ranking, investment_simulator, market_intelligence, price_analysis, investment_summary, news, unsupported).

- `retrieve_context(memory, required_sections)`: Filters company memory to sections needed for the intent (e.g., financial_health retrieves company_info, financial_metrics, peer_comparison).

- `answer_with_reasoning(query, memory, context, plan)`: Routes to specialized generator:
  - `_generate_financial_health_answer()`: Debt analysis, ROE interpretation, risk assessment
  - `_generate_comparison_answer()`: Side-by-side metrics
  - `_generate_calculation_answer()`: CAGR, future value (e.g., "₹1 lakh @ 12% for 5 years")
  - `_generate_education_answer()`: Explains concepts (ROCE, P/E, D/E, dividend yield)
  - `_generate_unsupported_answer()`: Rejects price predictions ("I can't reliably predict...")
  - `_generate_historical_performance_answer()`: Return calculations over 1D, 1M, 6M, 1Y, 5Y, MAX
  - `_generate_sector_ranking_answer()`: Best/worst performers in sector
  - `_generate_investment_simulator_answer()`: "If you bought ₹X years ago..."
  - `_generate_general_answer()`: Fallback for unclassified queries

- `rag_chat(question, memory, agent2_output, ticker, tab_context)`: RAG-specific chat function:
  - Validates company ticker (ensures correct company context)
  - Builds company knowledge base from memory + agent2 red flags
  - Includes tab_context parameter: exact rendered data on current tab
  - Calls Groq LLM; falls back to "openai/gpt-oss-20b" on rate limit
  - Strips reasoning leaks (`<think>` blocks, "Here's my thinking:", analysis preambles)

**Output Structure**:
```json
{
  "response": "Full synthesized analysis",
  "intent": "financial_health|explanation|...",
  "consensus_rating": "BUY|SELL|HOLD",
  "target_price": 3500.0,
  "expected_return": 8.5,
  "sections_used": ["company_info", "financial_metrics", "peer_comparison"],
  "reasoning_steps": ["Analyzed debt levels", "Compared peers", ...]
}
```

---

### 3.1.5 Frontend/Dashboard Module

**Location**: `public/index.html`, `public/company.html`, `public/script.js`, `public/styles.css`

**Responsibility**: Responsive web UI for dashboard view (all 50 companies) and company research (detailed tabs).

**Dashboard Features**:
- Live NIFTY 50 Index (price, change %, chart with 1D/1W/1M/6M/1Y/5Y selectors)
- Market indicators (advancing/declining stocks, A/D ratio, breadth, avg return)
- Top gainers/losers with ML predictions (direction + expected return %)
- Sector performance heatmap
- Market news (Google News RSS integration)

**Company Detail Page Tabs**:
1. **Overview**: Company name, sector, business summary, market cap, P/E, dividend yield, 52W range
2. **Financials**: P&L (Revenue, Op. Profit, Net Profit, EPS), Balance Sheet (Debt, Equity, Current Ratio), Cash Flow
3. **Peer Comparison**: Percentile rankings across 12 metrics with sector averages
4. **Market Sentiment**: Analyst consensus (recommendation, target, buy/hold/sell counts), news sentiment badges
5. **Recent Events**: News articles timeline with sentiment indicators
6. **Risks & Opportunities**: Red flags, risk factors, opportunities from Agents 2 & 3

**Per-Tab AI Chat**:
- User enters question on any tab → backend receives `{symbol, question, tab, context}` (exact rendered data)
- RAG grounds response in tab_context; prevents hallucination by matching on-screen numbers first

---

### 3.1.6 API/Backend Module

**Location**: `backend/main.py`, `backend/financial_calculators.py`, `backend/metrics_formatter.py`, `backend/prediction_service.py`, `backend/sector_metrics.py`

**Responsibility**: FastAPI server orchestrating all agents, managing endpoints, sanitizing JSON, serving UI.

**Endpoints**:

- `POST /api/company-research`: Research request for one company
  - Input: `{name, ticker, days, chat_query (optional)}`
  - Output: Rich JSON with company info, metrics, risks, AI analysis, `_data_quality`, `_data_sources` metadata

- `GET /api/nifty50`: Dashboard endpoint (index, gainers, losers, sectors, predictions, news)

- `GET /api/companies`: List of NIFTY 50 companies for dropdown

- `GET /api/dashboard`: Aggregated market view (index, indicators, movers, sectors, predictions, companies)

- `POST /api/generate-report`: Generate downloadable HTML report for a company

- `POST /api/chat`: Chat about a company grounded in tab context
  - Input: `{symbol, question, tab, context}`
  - Output: `{answer: str}`

**Financial Calculators** (`financial_calculators.py`):
- P&L: calc_operating_profit, calc_opm, calc_pbt, calc_tax, calc_eps
- Balance Sheet: calc_total_liabilities, calc_other_liabilities, calc_reserves
- Ratios: calc_roe, calc_roce, calc_de_ratio, calc_current_ratio, calc_pe_ratio

**Data Quality**:
- SafeJSONEncoder: NaN → 0.0, Infinity → 999999.0
- sanitize_json(): Recursive NaN/Inf replacement
- Every response includes `_data_quality` (price_available, news_available, sentiment_analyzed, risks_identified, peer_data_available, analysis_errors)

**ML Predictions** (`prediction_service.py`):
- XGBoost classifier: predicts UP/DOWN (classes 1/0)
- XGBoost regressor: predicts % return
- Features: 9 technical indicators (SMA, RSI, MACD, Bollinger Bands, volume ratio, volatility, momentum)
- Per-ticker 15-minute cache; fallback to simple heuristic if models unavailable

---

## 3.2 Data Flow

Data flows from Agent 1 → Agents 2 & 3 (parallel) → Agent 4 (sequential) → Company Memory (unified state) → API response + Cache.

Cache hierarchy:
- Pipeline-level (10-minute TTL per company)
- Agent 4 classification cache (60-second TTL)
- Prediction service (15-minute TTL per ticker)
- yfinance info cache (process-scoped)

---
