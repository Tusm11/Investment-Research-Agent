# 2. Literature Survey

## 2.1 Existing Work

Relevant research in automated stock analysis and multi-agent investment systems includes:

**MarketSenseAI 2.0** [1]: A framework combining sentiment analysis, technical indicators, and fundamental metrics for equity research. The system demonstrates the value of multi-signal fusion but lacks formal peer comparison and real-time anomaly detection. Our work extends this by implementing sector-level percentile ranking and Isolation Forest-based outlier detection.

**FinRobot** [2]: An LLM-based financial analysis framework that orchestrates multiple specialized agents for data retrieval, analysis, and report generation. FinRobot emphasizes agent orchestration and LLM reasoning chains. Our implementation adopts this orchestration philosophy but combines it with classical ML (Isolation Forest) for financial anomaly detection rather than relying entirely on LLM-based classification.

**Sentiment Analysis in Indian Stock Markets** [3]: Studies applying NLP and sentiment classification to news data for NIFTY 50 stocks demonstrate the feasibility and impact of sentiment-driven insights. Our project incorporates this through event extraction and market sentiment synthesis, but focuses on retrieval-augmented reasoning (CAG) rather than fine-tuned FinBERT models.

**Multi-Agent Systems for Financial Analysis** [4]: General frameworks for coordinating independent agents (data gathering, analysis, reasoning) show that sequential pipelines with clear handoff boundaries outperform monolithic systems in maintainability and modularity. Our four-agent pipeline reflects this principle.

## 2.2 Limitations of Existing Systems

1. **Siloed Analysis**: Most tools separate fundamental analysis from sentiment analysis, requiring users to manually reconcile signals.
2. **No Systematic Anomaly Detection**: Red flags are identified through hardcoded thresholds or simple rule-based logic, missing multivariate outliers.
3. **Limited Peer Context**: Single-company metrics without sector percentile ranking obscure whether a metric is good in absolute terms but poor relative to peers.
4. **Expensive LLM Usage**: Systems that call LLMs for all 50 companies on each request face rate limits and latency issues.
5. **No Interactive Chat Grounding**: Most systems do not tie chat answers to the exact data rendered on the user's current screen, leading to context mismatches.
6. **Static Reports**: HTML reports generated once; no per-tab interactive chat to clarify findings.

## 2.3 Our Innovation and Improvements

| Aspect | Existing Systems | Our Implementation |
|--------|------------------|--------------------|
| **Agent Orchestration** | Sequential or simple parallel | 4-stage reasoning with 2x parallel (Agents 2 & 3), explicit cache (10min TTL per company) |
| **Anomaly Detection** | Threshold-based (e.g., D/E > 5) | Isolation Forest on 15 z-scored features; anomaly_score (0–1) quantifies risk |
| **Peer Comparison** | Manual or external tools | Automated percentile ranking (12 metrics × 11 sectors × ThreadPoolExecutor, 8 workers) |
| **LLM Efficiency** | All 50 companies queried on load | Per-company on-demand, 60s classification cache, 429 rate-limit fallback |
| **Context Grounding** | LLM sees general company memory | RAG system receives exact tab_context (rendered data on screen); prevents hallucination |
| **Red Flags** | 3–4 hardcoded rules | 5 thresholds + Isolation Forest + 15-feature model |
| **Report Format** | Text-only or generic tables | Structured HTML with linked sections, sentiment badges, peer visuals |
| **Data Quality** | Opaque sourcing | Every response includes `_data_quality`, `_data_sources` metadata |

## 2.4 Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **LLM & Reasoning** | Groq (llama-3.3-70b, mixtral-8x7b) | <500ms inference latency; rate-limit fallback to openai/gpt-oss-20b |
| **Data Fetching** | yfinance, NSE/BSE (nselib), trafilatura web scraping | Real-time OHLCV, fundamentals, news; 55-second budget with hard timeout |
| **Anomaly Detection** | scikit-learn Isolation Forest | O(n log n) training; 15 multivariate financial features; pre-trained model |
| **Price Forecasting** | XGBoost classifier + regressor | Directional (UP/DOWN) + magnitude (% return); 9 technical features |
| **Peer Ranking** | NumPy percentile calculation | Parallelized with ThreadPoolExecutor (8 workers, 20s timeout) |
| **Web Framework** | FastAPI | Async endpoints, CORS middleware, JSON sanitization for NaN/Inf |
| **Frontend** | HTML5 + Tailwind CSS + Plotly.js | Glassmorphism design, responsive tabs, real-time chart rendering |
| **Context Retrieval** | Cache-Augmented Generation (CAG) | Groq-powered retrieval over stored sector/macro/RBI/Zerodha Varsity sources |
| **Deployment** | Python 3.9+, pip dependencies | See requirements.txt: langchain, scikit-learn, xgboost, yfinance, groq, fastapi, pandas |

### Note on Retrieval Architecture

This project uses **Cache-Augmented Generation (CAG)** for report synthesis, not traditional embedding-based RAG. CAG leverages pre-stored sector metrics, macro indicators, and RBI/Zerodha Varsity sources cached in memory, then grounds LLM synthesis in these retrieved sections. No FinBERT fine-tuning is employed; sentiment classification uses rule-based keywords and LLM-driven event analysis.

---
