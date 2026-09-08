# 1. Introduction

## 1.1 About the Project

The AI-Powered NIFTY 50 Stock Market Research Agent is a multi-agent system designed to synthesize fundamental financial analysis, market intelligence, and sentiment-driven insights for comprehensive investment research on India's largest 50 publicly traded companies. The system was developed as a solo academic project combining portfolio applications with research goals.

The architecture comprises four specialized agents operating in a coordinated pipeline:

- **Agent 1 (Data Fetching)**: Collects real-time financial data, news, analyst consensus, and market drivers from yfinance, NSE/BSE sources, and web scraping.
- **Agent 2 (Fundamental Health Analysis)**: Evaluates financial health using statistical peer comparison, Isolation Forest anomaly detection, and calculated red flags.
- **Agent 3 (Market Intelligence & Perception)**: Synthesizes news sentiment, analyst views, price performance, and market narrative.
- **Agent 4 (Report Synthesis)**: Conducts four-stage reasoning (intent classification, context retrieval, reasoning, answer generation) to produce investor-grade conclusions and downloadable HTML reports.

All agents operate within strict scope boundaries: NIFTY 50 only, no price prediction (explicitly rejected as unsupported), and machine learning used only where justified (anomaly detection and price trend classification, not for all predictions).

## 1.2 Problem Statement

Manual stock research for retail investors faces fundamental limitations:

1. **Single-Signal Analysis**: Most tools provide either fundamental metrics or sentiment, not both, limiting holistic assessment.
2. **Lack of Context-Grounded Intelligence**: Market data without company fundamentals creates misaligned conclusions; fundamental metrics without market perception miss critical catalysts.
3. **Manual Peer Comparison**: Identifying which companies are outliers within their sector requires manual data aggregation and percentile calculation.
4. **Inefficient Report Synthesis**: Generating a structured investment perspective from disparate data sources (balance sheets, news, analyst views, technical trends) is time-consuming for individual investors.
5. **Scalability Gap**: Analyzing one company takes hours; analyzing all 50 NIFTY members is impractical for manual review.
6. **No Anomaly Detection**: Financial statement red flags are identified ad hoc, missing systematic outlier detection that compares against peer distributions.

## 1.3 Project Objectives

### Primary Objectives

1. **Health Scoring**: Assign each NIFTY 50 company a multidimensional health score derived from:
   - Return on Capital Employed (ROCE), operating margins, and profitability ratios
   - Debt-to-equity leverage and liquidity metrics
   - Peer percentile rankings to contextualize absolute metrics

2. **Anomaly and Red-Flag Detection**: Use an Isolation Forest model trained on 15 z-scored financial ratios to identify companies with unusual financial patterns (outliers in debt structure, margin compression, liquidity stress, etc.).

3. **Peer Comparison**: Calculate percentile ranks for 12 target metrics (ROCE, Debt, Sales, OPM, etc.) within each sector to show relative performance.

4. **Market Intelligence via Cache-Augmented Generation (CAG)**: Retrieve relevant context from stored sector/macro/RBI/Zerodha Varsity sources and ground LLM synthesis in this retrieved data (not traditional embedding-based RAG or FinBERT).

5. **Downloadable Reports**: Generate structured HTML investment reports combining fundamental analysis, risks, opportunities, and market narrative in a single artifact.

### Secondary Objectives

1. **Scope Discipline**: Avoid over-engineering; implement only models with clear justification (Isolation Forest for anomaly detection justified; K-Means clustering abandoned).
2. **Efficient LLM Usage**: Trigger Groq API calls per-company on demand, not for all 50 on dashboard load; implement 60-second classification cache.
3. **Data Quality Transparency**: Include metadata (`_data_quality`, `_data_sources`) in every API response indicating which data sources returned values and confidence levels.
4. **Multi-Tab Context Grounding**: Ensure chat responses are grounded in the exact on-screen tab data the user is viewing (Financials tab context differs from Peers tab context).

---
