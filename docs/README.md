# Academic Documentation: AI-Powered NIFTY 50 Stock Market Research Agent

This directory contains the complete academic documentation for the AI-Powered NIFTY 50 Stock Market Research Agent project.

## Document Structure

The documentation is organized into **12 sections** (markdown files), each self-contained with numbered headings. These files are intended to be concatenated in order to form a complete academic mini-project report.

### File Manifest

| File | Section | Purpose |
|------|---------|---------|
| `01_introduction.md` | 1 | Project overview, problem statement, objectives |
| `02_literature_survey.md` | 2 | Related work, tech stack, innovation comparison |
| `03_software_requirements_analysis.md` | 3 | Module descriptions (all 4 agents, API, frontend) |
| `04_hardware_requirements_analysis.md` | 4 | Hardware specs, software dependencies, network requirements |
| `05_system_architecture_diagram.md` | 5 | System architecture, data flow, cache layers |
| `06_methodologies_and_implementation.md` | 6 | Methods, ML models, implementation workflows |
| `07_model_implementation.md` | 7 | Full code walkthrough: functions, classes, endpoints |
| `08_pipeline_summary.md` | 8 | End-to-end pipeline, key concepts, sequence diagrams |
| `09_model_output.md` | 9 | Sample outputs from all agents, API responses |
| `10_conclusion.md` | 10 | Summary, achievements, production readiness |
| `11_future_enhancements.md` | 11 | Planned features, known issues, prioritization |
| `12_references.md` | 12 | Academic papers, frameworks, data sources |

---

## Content Highlights

### Section 1: Introduction
- **About the Project**: 4-agent pipeline (Data Fetching, Fundamental Analysis, Market Intelligence, Report Synthesis)
- **Problem Statement**: Single-signal analysis, lack of peer context, manual report synthesis
- **Objectives**: Health scoring, anomaly detection, peer comparison, CAG-based retrieval, downloadable reports

### Section 2: Literature Survey
- **Existing Work**: MarketSenseAI 2.0, FinRobot, NIFTY 50 sentiment analysis literature
- **Limitations**: Siloed analysis, no systematic anomaly detection, expensive LLM usage
- **Our Innovation**: Multi-agent orchestration, Isolation Forest anomaly detection, peer percentile ranking, cache-augmented generation (NOT FinBERT)
- **Technology Stack**: Groq LLM, yfinance, scikit-learn (Isolation Forest), XGBoost, FastAPI, Tailwind/Plotly

### Section 3: Software Requirements Analysis
- **Agent 1 (Data Fetching)**: Parallel fetching with 55-second budget; yfinance, NSE/BSE, web scraping
- **Agent 2 (Fundamental Health)**: 12 TARGET_METRICS, percentile ranking, Isolation Forest (15 z-scored features), red flags
- **Agent 3 (Market Intelligence)**: Sentiment classification, analyst consensus, price synthesis
- **Agent 4 (Report Synthesis)**: 4-stage reasoning (classify → retrieve → reason → answer); CAG-based RAG; tab-aware chat
- **Backend**: FastAPI endpoints, JSON sanitization, data quality metadata
- **Frontend**: 6 tabs (Overview, Financials, Peers, Sentiment, Events, Risks), per-tab chat

### Section 4: Hardware Requirements
- **Minimum**: 4+ cores, 8 GB RAM, 2 GB storage, 10 Mbps internet
- **Recommended**: 16 GB RAM for multi-user deployments
- **No GPU required** (Isolation Forest, XGBoost, LLM inference via Groq API)

### Section 5: System Architecture
- **Orchestration**: Sequential Agent 1 → Parallel Agents 2&3 (60s timeout) → Sequential Agent 4
- **Caching**: Pipeline (10min TTL), classification (60s), predictions (15min), yfinance info (process-lifetime)
- **Data Flow**: Agent handoffs via explicit message-passing (no shared state)

### Section 6: Methodologies & Implementation
- **Agent 1 Method**: Parallel fetching with optimistic degradation (partial data if timeout)
- **Agent 2 Method**: Absolute metrics + peer percentiles + multivariate anomaly detection
- **Agent 3 Method**: Event extraction, analyst synthesis, narrative generation
- **Agent 4 Method**: 4-stage reasoning with LLM classification (60s cache), specialized answer generators
- **Models**: Isolation Forest (15 features), XGBoost (classifier + regressor), CAG retrieval

### Section 7: Model Implementation
- **Code Walkthrough**: Every function, class, and endpoint documented with purpose, explanation, and example outputs
- **Agent 1**: `fetch_all_data()`, `fetch_price_history()`, `fetch_analyst_consensus()`, etc.
- **Agent 2**: `build_health_features()`, `compare_peers()`, `assess_isolation_forest()`, `detect_red_flags()`
- **Agent 3**: `_route_query()`, `run_agent3()`, event/sentiment/synthesis functions
- **Agent 4**: `classify_question()`, `answer_with_reasoning()`, LLM integration
- **RAG**: `rag_chat()` with tab_context grounding, reasoning leak stripping
- **API**: `/api/company-research`, `/api/chat`, `/api/nifty50`, `/api/dashboard`
- **Known Bugs**: Debt/Equity mismatch, reasoning leaks, context mismatches (with status: documented/mitigated)

### Section 8: Pipeline Summary
- **End-to-End Flow**: Input → Extraction → Cache check → Agent 1 (55s) → Agents 2&3 (parallel, 60s) → Agent 4 (LLM) → Memory build → Cache → API response
- **Key Concepts**: Multi-agent orchestration, self-supervised labeling, CAG, rule-based + LLM synthesis, scope discipline, timeout budgets
- **Sequence Diagram**: User query through all agents to frontend rendering

### Section 9: Model Output
- **Agent 1 Output**: Company info, price history, news, analyst data, financial metrics, market drivers (JSON sample)
- **Agent 2 Output**: Financial facts, red flags (empty if company is healthy), Isolation Forest assessment, peer comparison (JSON sample)
- **Agent 3 Output**: Sentiment (Bullish/Bearish/Neutral/None), market intelligence narrative, analyst consensus (JSON sample)
- **Agent 4 Output**: Synthesized response, intent, target price, expected return (JSON sample)
- **Company Memory**: Unified 20+ section state (JSON sample)
- **API Response**: Sanitized JSON with `_data_quality` and `_data_sources` metadata
- **Chat Output**: RAG-grounded answer with status
- **HTML Report**: Cover, executive summary, financials, peer comparison, risks/opportunities

### Section 10: Conclusion
- **Achievements**: 4-agent pipeline, Isolation Forest anomaly detection, peer percentile ranking, CAG-based RAG, data quality transparency, efficient LLM usage, ML-only-where-justified
- **Practical Outcomes**: Reduced research time, comprehensive view, risk visibility, peer context, interactive chat
- **Technical Achievements**: Parallel orchestration, multi-layer caching, error recovery, JSON sanitization, tab-aware chat
- **Production Readiness**: Strengths (stable, predictable, error recovery); Gaps (no persistence, auth, scaling); Recommendation: suitable for academic/small team use, requires hardening for production SaaS

### Section 11: Future Enhancements
- **Planned**: People's Perspective tab (news sentiment, Google Trends, analyst consensus)
- **Known Issues**: Debt/Equity mismatch (MEDIUM priority, 2–3 hrs), reasoning leaks (MEDIUM, 3–4 hrs), context mismatch (LOW, 1 hr)
- **Feature Enhancements**: Surface Isolation Forest anomaly score, enhanced red flag explanations, model retraining pipeline, real-time price updates
- **Infrastructure**: Database persistence, audit logging, horizontal scaling, WebSocket support
- **Visualizations**: Radar charts, histograms, scatter plots for peer comparison
- **Abandoned Features**: K-Means (imbalanced clusters), Piotroski F-Score (over-engineering), FinBERT fine-tuning (CAG sufficient)

### Section 12: References
- **Academic Papers**: MarketSenseAI 2.0, FinRobot, NIFTY 50 sentiment analysis (content rephrased per licensing)
- **Libraries**: yfinance, scikit-learn, XGBoost, LangChain, Groq, FastAPI, NumPy, pandas, trafilatura, Plotly
- **Financial Concepts**: Altman Z-Score (mentioned, not implemented), Piotroski F-Score (mentioned, not implemented), Damodaran's valuation framework, Graham's intelligent investing
- **Data Sources**: Yahoo Finance, NSE, BSE, Google News, NewsAPI
- **Glossary**: 20+ finance and technical terms defined

---

## Key Project Characteristics

### Scope
- **Geographic**: NIFTY 50 (India's 50 largest companies) only
- **Features**: Health scoring, anomaly detection, peer comparison, market intelligence, downloadable reports
- **ML**: Isolation Forest (anomaly), XGBoost (price direction/magnitude); no deep learning, no fine-tuned FinBERT
- **Price Prediction**: Explicitly unsupported (returns "I cannot reliably predict future prices")

### Architecture
- **Agents**: 4 specialized agents (Data Fetching, Fundamental Analysis, Market Intelligence, Report Synthesis)
- **Orchestration**: Sequential + parallel with explicit timeout budgets (55s for Agent 1, 60s for Agents 2&3)
- **Retrieval**: Cache-Augmented Generation (CAG), not embedding-based RAG
- **LLM**: Groq (primary), openai/gpt-oss-20b (fallback on 429 rate limit)
- **Caching**: Pipeline (10min), classification (60s), predictions (15min)
- **Frontend**: 6 tabs (Overview, Financials, Peers, Sentiment, Events, Risks), per-tab AI chat

### Data Quality
- Every response includes `_data_quality` flags (price_available, news_available, sentiment_analyzed, etc.)
- Every response includes `_data_sources` (which APIs returned data)
- Missing data distinguished from zero (None vs. 0.0)
- JSON sanitization replaces NaN → 0.0, Infinity → 999999.0

---

## How to Use This Documentation

1. **Read Sequentially**: Start with Section 1 (Introduction); follow through to Section 12 (References). Each section builds on prior sections.

2. **Print as Academic Report**: Concatenate all 12 files in order. Add your own Title Page, Certificate, Declaration, Acknowledgement, Table of Contents, List of Figures, List of Abbreviations at the beginning.

3. **Code Reference**: Section 7 (Model Implementation) provides line-by-line code walkthrough. Use to understand function signatures, data structures, API contracts.

4. **Architecture Deep-Dive**: Section 5–6 (System Architecture, Methodologies) explains design rationale, caching strategy, timeout budgets.

5. **Deployment Guide**: Section 4 (Hardware Requirements) and Section 11 (Future Enhancements) provide deployment and scaling guidance.

---

## Document Statistics

- **Total Files**: 12 markdown files
- **Total Lines**: ~3,500 (approximate)
- **Code Blocks**: ~60 (mostly Python, some JSON, pseudocode)
- **Tables**: ~20
- **Figures Referenced**: 5 (architecture, workflow diagrams described in text or ASCII)
- **References**: 32 (academic papers, libraries, tools, data sources)

---

## Notes

- **No FinBERT**: This project uses Cache-Augmented Generation (CAG), not embedding-based RAG or FinBERT. Sentiment classification is rule-based + LLM reasoning.
- **XGBoost, Not Random Forest**: ML models are XGBoost (price prediction) and Isolation Forest (anomaly detection). No Random Forest models used.
- **K-Means Abandoned**: Attempted but resulted in imbalanced clusters. Replaced by sector-level percentile ranking.
- **Known Bugs Documented**: Debt/Equity mismatch, reasoning leaks, context mismatches are all documented with status (documented/mitigated/known limitation).
- **Honest Assessment**: Section 10 (Conclusion) provides honest production readiness assessment: suitable for academic/small team use, but missing database, auth, scaling for production SaaS.

---

## Disclaimer

This documentation reflects the state of the codebase as of the time of writing. Code may evolve; documentation should be updated to match. All claims about functionality, performance, and accuracy are based on code review and testing; no external validation or third-party audit has been performed.

---
