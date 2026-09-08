# 11. Future Enhancements

This section documents planned features, known issues to fix, and realistic next steps for the project.

## 11.1 Planned Features (Next Phase)

### People's Perspective Tab (Not Yet Implemented)

**Scope**: Interactive tab on company detail page showing investor sentiment and retail interest.

**Components**:

1. **News Sentiment Breakdown**: Instead of single sentiment score, provide multi-dimensional breakdown:
   - Positive vs. negative article counts (time series)
   - Sentiment keywords extracted (e.g., "strong growth", "margin pressure", "regulatory concern")
   - Sentiment trend: improving, stable, or deteriorating over past 3 months

2. **yFinance Analyst Consensus**: Already fetched; enhance display:
   - Buy/hold/sell breakdown as stacked bar chart
   - Analyst rating changes over time (if yfinance provides history)
   - Target price evolution (consensus drifting up/down?)

3. **Google Trends Search Interest** (new data stream):
   - Add `fetch_google_trends(ticker)` to Agent 1
   - Returns: search volume index for company name, competitor names, sector keywords
   - Interpretation: spike in searches may indicate emerging catalysts or negative events
   - Example: Search volume for "Reliance" up 40% week-over-week → potential catalyst

4. **Social Media / Reddit Sentiment** (optional):
   - Scrape discussion volume, sentiment from r/IndianStocks, r/StockMarket
   - Low priority; data is noisy and may require content moderation

**Implementation Effort**: 1–2 weeks (Google Trends API integration + frontend tab)

---

## 11.2 Known Issues to Fix

### Issue 1: Debt/Equity Display Mismatch

**Bug**: Debt values differ between red_flags, peer_comparison, and Financials tab.

**Root Cause**: Debt fetched from multiple sources:
- `red_flags.py`: `bs.get("Total Debt")` (balance sheet)
- `company_info` (yfinance `.info.totalDebt`)
- RAG system displays real-time fetched value on Financials tab

**Impact**: User sees D/E = 1.2 on Financials tab, but red flags show D/E = 1.5 (or vice versa).

**Fix Strategy**:
1. Unify debt source: choose one authoritative source (recommend yfinance `.info.totalDebt` with fallback to balance sheet)
2. Store debt value in Agent 1 and reuse throughout pipeline
3. Add unit test: verify D/E ratio used in red_flags matches display value

**Effort**: 2–3 hours

**Priority**: Medium (UX confusion, not correctness risk)

---

### Issue 2: AI Chain-of-Thought Leaking

**Bug**: LLM responses occasionally include reasoning markers (`<think>`, "Here's my thinking:") visible in UI.

**Root Cause**: RAG system strips reasoning blocks but may miss edge cases depending on LLM model behavior:
- Groq models: llama-3.3-70b, mixtral-8x7b (tested, stripping works)
- Fallback model: openai/gpt-oss-20b (may output reasoning differently)

**Impact**: Chat answer shows: "Here's my thinking: Based on the debt ratio... The answer is: low leverage." User sees internal reasoning.

**Fix Strategy**:
1. Extend reasoning marker list: add markers observed in production (log them)
2. Test fallback model: run chat queries through openai/gpt-oss-20b, identify markers
3. Add aggressive fallback: if response contains multiple sections like reasoning, extract longest coherent section (current logic does this; may be too aggressive in rare cases)
4. Add system prompt instruction: "Output only the direct answer, no thinking process" (already in place; reinforce)

**Effort**: 3–4 hours

**Priority**: Medium (mostly cosmetic; rare in practice with Groq models)

---

### Issue 3: Financials Tab Context Mismatch

**Bug**: User opens Financials tab; async load starts. User asks AI question before data loads. Context passed to RAG is empty or stale.

**Root Cause**: Frontend does not wait for Financials tab data to fully load before enabling chat input.

**Impact**: Chat answer is not grounded in on-screen data; user sees generic company answer instead of Financials-specific answer.

**Fix Strategy**:
1. Add loading state indicator on chat input: disable/dim until tab data loads
2. Frontend passes `context = ""` (empty) if data not yet rendered
3. Backend (RAG) detects empty context and falls back to general company memory (already implemented)
4. Optional: add user-facing hint "Financials loading... Chat will be available shortly"

**Effort**: 1 hour (frontend only)

**Priority**: Low (rare edge case; gracefully degraded already)

---

## 11.3 Surfacing Isolation Forest Results in UI

**Current State**: Isolation Forest anomaly_score computed in Agent 2, stored in model_assessment, included in memory. NOT displayed in frontend.

**Proposed Enhancement**: Add anomaly risk indicator to company detail:
- Dashboard company card: small badge showing anomaly_score (0–1, color-coded: green 0–0.3, yellow 0.3–0.7, red 0.7–1.0)
- Financials tab: anomaly_score displayed near red flags section
- Interpretation text: "This company exhibits normal financial patterns" (score < 0.3) or "Financial patterns differ from sector norms; manual review recommended" (score > 0.7)

**Implementation Effort**: 2–3 hours (frontend + backend metric formatting)

**Priority**: Medium (valuable risk indicator, currently hidden)

---

## 11.4 Enhanced Red Flag Explanations

**Current State**: Red flags show metric, value, severity, explanation (e.g., "Debt/Equity > 5: High severity").

**Proposed Enhancement**: Add context-specific interpretation:
- For high debt flag: "Sector average D/E is 0.45; your company is at 1.2. Recommended action: compare against peer group, assess interest coverage ratios."
- For low margin: "Operating margin of 5% vs. sector 18%; consider: pricing power, scale, operational efficiency. Has margin historically trended down?"

**Implementation Effort**: 2 hours (add sector median + trend to red flag generation)

**Priority**: Low (nice-to-have; explanations clear enough as-is)

---

## 11.5 Model Versioning and Retraining Pipeline

**Current State**: Isolation Forest and XGBoost models are static (pre-trained, stored as .pkl files).

**Proposed Enhancement**: Implement retraining pipeline:
1. Monthly retraining trigger: collect past month's NIFTY 50 data
2. Retrain Isolation Forest on updated feature set (15 z-scored ratios)
3. Retrain XGBoost price prediction on updated technical indicators
4. Version models: `isolation_forest_v1_2024_01.pkl`, `xgb_regressor_v1_2024_01.pkl`
5. A/B test: 10% of requests use new model; compare prediction accuracy against holdout test set
6. Promote model if accuracy improves; roll back if degrades

**Implementation Effort**: 2–3 weeks (data pipeline, model registry, A/B testing framework)

**Priority**: Low (academic project, not production ML system)

---

## 11.6 Real-Time Price Updates

**Current State**: Prices fetched on-demand; not streamed.

**Proposed Enhancement**: WebSocket support for real-time price updates:
1. Open WebSocket connection when user navigates to company detail
2. Subscribe to price updates (via websocket to backend; backend pulls from market data provider)
3. Update price display in real-time; no page refresh needed
4. Close connection when user navigates away

**Requires**:
- Market data provider integration (e.g., NSE WebSocket API, Zerodha Kite, ODIN broker API)
- FastAPI WebSocket endpoints
- Frontend WebSocket client (reconnect on disconnect)

**Implementation Effort**: 3–4 weeks (broker integration, infrastructure)

**Priority**: Very Low (out of scope for academic project; overkill for retail research)

---

## 11.7 Persistent Database and Audit Logging

**Current State**: Company memory stored in `company_memory.json` (file-based).

**Proposed Enhancement**: Migrate to production database:
1. PostgreSQL backend: store company_research table (ticker, timestamp, agent1/2/3/4 outputs, memory, query, user_id)
2. Add audit logging: who ran research, when, what was downloaded, user IP address
3. Enable user accounts: sign up, save favorite companies, download history, saved reports
4. Query history: user can re-run research from history, compare with previous results

**Implementation Effort**: 2–3 weeks (database schema, migrations, auth, API updates)

**Priority**: Low (academic project does not require persistence)

---

## 11.8 Horizontal Scaling

**Current State**: Single-machine deployment; processes Agent 1–4 sequentially for each company.

**Proposed Enhancement**: Distributed processing:
1. Separate Agent 1 fetcher into standalone service (Redis queue, consumed by N workers)
2. Agent 2/3 analysis services (parallel workers)
3. Agent 4 synthesis service (workers)
4. FastAPI server: routes requests to services, aggregates results
5. Load balancer: distribute API traffic across multiple FastAPI instances

**Requires**: Docker, Kubernetes or AWS ECS, message queue (Redis, RabbitMQ)

**Implementation Effort**: 4–6 weeks (containerization, orchestration, testing)

**Priority**: Very Low (academic project)

---

## 11.9 Enhanced Peer Comparison Visualizations

**Current State**: Peer comparison shown as table (metric, company value, sector average, percentile).

**Proposed Enhancement**: Interactive visualizations:
1. Radar chart: company vs. sector average across 12 metrics (visual perception of strengths/weaknesses)
2. Histogram: distribution of metric values across sector peers; company highlighted
3. Scatter plot: ROCE vs. Debt for all peers; company highlighted (identify outliers)

**Implementation Effort**: 2–3 hours (Plotly visualizations on frontend)

**Priority**: Medium (significant UX improvement; low effort)

---

## 11.10 Scenario Analysis / Sensitivity Tables

**Proposed Enhancement**: "What-if" analysis for investment scenarios:
- User inputs: purchase price, hold period (years), target return % (or target price)
- System calculates: implied annual return, upside/downside scenarios at 25th/50th/75th percentiles
- Uses historical volatility, analyst target ranges, sector growth estimates

**Example**: "If I buy TCS at ₹3,200 and hold for 5 years, what returns should I expect?"
- Base case (50th percentile): 12% CAGR → ₹5,100 exit price
- Bull case (75th percentile): 18% CAGR → ₹6,400 exit price
- Bear case (25th percentile): 6% CAGR → ₹4,280 exit price

**Implementation Effort**: 1–2 weeks (financial calculator + frontend UI)

**Priority**: Low (useful for investors, but out of scope for research platform)

---

## 11.11 Competitor / Relative Comparison

**Proposed Enhancement**: Side-by-side company comparison:
- User selects 2–3 companies → system displays all 12 health metrics side-by-side
- Highlights best/worst performer for each metric
- Shows relative valuation (P/E, P/B, PEG ratio) and growth expectations
- Generates comparison report (download as PDF)

**Implementation Effort**: 2–3 hours (frontend UI, report generation)

**Priority**: Low (valuable for users, but can be done manually today)

---

## 11.12 Integration with Portfolio Tracking

**Proposed Enhancement**: User uploads portfolio (CSV or import from broker):
- System compares portfolio against NIFTY 50 peers
- Highlights: "Your holdings are concentrated in Financials sector (50% vs. NIFTY 50 30%)"
- Shows portfolio-level risk: "Average D/E: 0.8 (vs. sector 0.6); portfolio is leveraged"
- Suggests rebalancing: "Consider increasing exposure to Technology; high ROCE companies"

**Implementation Effort**: 2–3 weeks (portfolio ingestion, aggregation, recommendations)

**Priority**: Low (out of scope for academic research tool)

---

## 11.13 Prioritization Summary

| Enhancement | Effort | Priority | Why |
|-------------|--------|----------|-----|
| People's Perspective Tab | 1–2 weeks | High | Complete missing feature; high user value |
| Fix Debt/Equity Mismatch | 2–3 hours | Medium | Bug; user confusion |
| Fix Reasoning Leak | 3–4 hours | Medium | Edge case; cosmetic |
| Fix Financials Context Mismatch | 1 hour | Low | Rare; already gracefully degraded |
| Surface Isolation Forest | 2–3 hours | Medium | Valuable risk indicator currently hidden |
| Enhanced Red Flags | 2 hours | Low | Nice-to-have explanation |
| Model Retraining Pipeline | 2–3 weeks | Low | Not needed for academic project |
| Real-Time Prices | 3–4 weeks | Very Low | Out of scope |
| Database + Audit Logging | 2–3 weeks | Low | Academic project doesn't require |
| Horizontal Scaling | 4–6 weeks | Very Low | Academic project doesn't need |
| Peer Visualizations | 2–3 hours | Medium | Good UX; low effort |
| Scenario Analysis | 1–2 weeks | Low | Useful but non-core |
| Competitor Comparison | 2–3 hours | Low | Doable manually today |
| Portfolio Integration | 2–3 weeks | Very Low | Out of scope |

---

## 11.14 Abandoned Features (Not Implementing)

### K-Means Clustering (Abandoned)

**Reason**: Attempted to cluster NIFTY 50 companies by financial similarity. Result: highly imbalanced clusters (Technology 20 companies in one cluster, others sparse). No clear business value. Abandoned in favor of sector-based percentile ranking.

### Piotroski F-Score (Abandoned)

**Reason**: Mentioned in early design as proxy label for fundamental strength. Implementation would require manual calculation of 9 financial signals with specific thresholds. Simpler approach: use ROCE > 20% + OPM > 15% + ROE > 15% as strength indicators. Isolation Forest provides more nuanced anomaly scoring.

### FinBERT Fine-Tuning (Abandoned)

**Reason**: Would require curating labeled NIFTY 50 news corpus and 2–3 weeks fine-tuning. Cache-Augmented Generation + Groq LLM sufficient for report synthesis. Return on fine-tuning investment is marginal.

### Portfolio Optimization (Out of Scope)

**Reason**: Would require mean-variance optimization, risk budgeting, constraint modeling. Significantly expands scope beyond research to active portfolio management. Intentionally not implemented.

---
