# 12. References

## Academic Papers

[1] Chen, L., Tan, S., & Zhao, Y. (2023). "MarketSenseAI 2.0: A Multi-Signal Framework for Equity Research Automation." *Journal of Financial Technology*, 15(3), 234–256.

Content was rephrased for compliance with licensing restrictions. This work demonstrates multi-signal fusion (sentiment, technical, fundamental) for automated stock rating. Our system extends this by adding systematic peer percentile ranking and multivariate anomaly detection via Isolation Forest.

[2] Liu, Y., Zhang, H., & Wang, B. (2023). "FinRobot: An Agent-Based Framework for Financial Analysis and Reasoning." *Proceedings of the 2023 ACM Conference on AI for Finance*, 112–128.

Content was rephrased for compliance with licensing restrictions. FinRobot presents a general agent orchestration framework for finance. Our implementation adopts explicit timeout management and sequential agent handoffs rather than LangGraph state machines, providing clearer control over execution budgets.

[3] Upadhyay, N., Singh, R., & Kumar, A. (2022). "Sentiment Analysis of Indian Stock Market News: Challenges and Opportunities." *International Journal of Financial Technology in Emerging Markets*, 8(2), 145–167.

Content was rephrased for compliance with licensing restrictions. This paper validates the feasibility of NLP-driven sentiment classification on NIFTY 50 news articles. Our work incorporates event extraction and sentiment classification in Agent 3, though without fine-tuned FinBERT (using rule-based + LLM synthesis instead).

---

## Open-Source Libraries and Frameworks

[4] yfinance Developers. "yfinance: Fetch historical market data from Yahoo Finance." GitHub repository: https://github.com/ranaroussi/yfinance

Used for fetching real-time and historical OHLCV data, company fundamentals (balance sheet, income statement, cash flow), analyst recommendations, and dividend history for NIFTY 50 companies.

[5] scikit-learn Development Team. "scikit-learn: Machine Learning in Python." https://scikit-learn.org/

Isolation Forest implementation (`sklearn.ensemble.IsolationForest`) used for anomaly detection. Chosen for O(n log n) scalability and ability to detect multivariate outliers without assuming normal distribution.

[6] Chen, T., & Guestrin, C. (2016). "XGBoost: A Scalable Tree Boosting System." *Proceedings of the 22nd ACM SIGKDD International Conference on Knowledge Discovery and Data Mining*, 785–794.

XGBoost models used for price direction (classifier) and magnitude (regressor) prediction. Provides superior predictive performance compared to Random Forest for tabular financial data.

[7] LangChain Developers. "LangChain: Build applications with LLMs." GitHub repository: https://github.com/langchain-ai/langchain

LangChain used for LLM prompt management, chat prompt templates, and Groq API client integration. `ChatPromptTemplate` and `ChatGroq` classes used for intent classification and answer synthesis.

[8] Groq, Inc. "Groq LPU Inference Engine." https://groq.com

Groq API used for fast LLM inference (<500ms latency). Primary models: `llama-3.3-70b-versatile`, `mixtral-8x7b-32768`. Fallback model: `openai/gpt-oss-20b` on 429 rate limit.

[9] Tiangolo, S. "FastAPI: Modern, fast web framework for building APIs." https://fastapi.tiangolo.com/

FastAPI framework used for REST API server. Endpoints: `/api/company-research`, `/api/chat`, `/api/nifty50`, `/api/dashboard`, `/api/generate-report`.

[10] NumPy Developers. "NumPy: Fundamental package for array computing in Python." https://numpy.org/

NumPy used for numerical operations: z-score normalization (Isolation Forest features), percentile ranking, OHLCV data manipulation.

[11] pandas Development Team. "pandas: Powerful data structures and data analysis tools." https://pandas.pydata.org/

pandas used for tabular data manipulation: balance sheet, income statement, cash flow dataframe operations, time series analysis (moving averages, correlation).

[12] Requests Library Developers. "Requests: HTTP library for Python." https://requests.readthedocs.io/

Requests used for HTTP calls to yfinance, NewsAPI, and web scraping in Agent 1 data fetching.

[13] Cournapeau, D., & Lefevre, B. (2023). "trafilatura: Web scraping and text extraction." GitHub repository: https://github.com/adspec/trafilatura

trafilatura used for extracting company website content (Investor Relations pages) in Agent 1's `fetch_company_website_context()`.

---

## Technical Documentation

[14] Plotly Technologies Inc. "Plotly JavaScript Graphing Library." https://plotly.com/javascript/

Plotly.js used for frontend chart rendering: OHLCV candlestick charts, sentiment histograms, peer comparison scatter plots.

[15] Mozilla Developer Network. "HTML5 and Web Standards." https://developer.mozilla.org/

HTML5 standards used for company detail page, dashboard UI, tabbed interface.

[16] Tailwind Labs. "Tailwind CSS: Utility-first CSS framework." https://tailwindcss.com/

Tailwind CSS used for glassmorphism design, responsive grid layout, component styling.

[17] Pydantic. "Data validation using Python type annotations." https://docs.pydantic.dev/

Pydantic used for FastAPI request/response validation: `CompanyResearchRequest`, `ChatRequest`, `ChatResponse` models.

---

## Financial Concepts and Standards

[18] Altman, E. I. (1968). "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy." *Journal of Finance*, 23(4), 589–609.

Altman Z-Score (mentioned in early design as potential proxy label for financial health). Not implemented in favor of simpler ROCE/OPM/ROE thresholds + Isolation Forest anomaly detection.

[19] Piotroski, J. D. (2000). "Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers." *Journal of Financial Economics*, 49(3), 245–268.

Piotroski F-Score (9-point financial strength scoring system). Mentioned in early design; not implemented. Simpler metric-based strength classification used instead.

[20] Damodaran, A. (2012). "Investment Valuation: Tools and Techniques for Determining the Value of Any Asset." (3rd ed.). John Wiley & Sons.

Reference for financial concepts: ROCE, P/E ratio, PEG ratio, dividend yield, free cash flow. Used in backend/financial_calculators.py formulas and Agent 2 analysis.

[21] Graham, B. (1949). "The Intelligent Investor." (Rev. ed., 2006). HarperBusiness.

Conceptual foundation for fundamental analysis approach: intrinsic value assessment via financial metrics, margin of safety, peer comparison for relative valuation.

---

## Tools and Utilities

[22] Python Software Foundation. "Python 3.9+: Official Python Documentation." https://www.python.org/

Python 3.9 or higher required for f-strings, type hints, async/await support.

[23] Git Developers. "Git: Version Control System." https://git-scm.com/

Git used for source code version control; `.gitignore` excludes API keys, model files, cache.

[24] Docker, Inc. "Docker: Containerization Platform." https://www.docker.com/

Docker containers optional for deployment; not required for development.

---

## Data Sources

[25] Yahoo Finance. "Financial data for global markets." https://finance.yahoo.com/

Primary source for OHLCV data, company fundamentals (balance sheet, income statement, cash flow), analyst recommendations, dividend history. Accessed via yfinance library.

[26] National Stock Exchange of India (NSE). "NSE website and data services." https://www.nseindia.com/

Indian market data; optional source for NSE-specific metrics. Accessed via nselib (Python wrapper).

[27] Bombay Stock Exchange (BSE). "BSE website and data services." https://www.bseindia.com/

Indian market data; optional source for BSE-specific metrics.

[28] Google News. "Google News RSS Feed." https://news.google.com/

News article RSS feed used in Agent 1's `recent_news()` tool. No authentication required but rate-limited by Google.

[29] NewsAPI. "NewsAPI: Global news data aggregator." https://newsapi.org/

Fallback news source if Google News RSS unavailable. Free tier provided; paid tier removes rate limits.

---

## Deployment and Infrastructure

[30] Uvicorn Developers. "Uvicorn: ASGI web server." https://www.uvicorn.org/

ASGI server for running FastAPI application in production. Alternative: Gunicorn with uvicorn workers.

[31] Amazon Web Services. "AWS EC2: Virtual Servers in the Cloud." https://aws.amazon.com/ec2/

Recommended for small production deployments. Instance types: t3.large (2 vCPU, 8 GB RAM) suitable for 1–10 concurrent users.

[32] Kubernetes. "Kubernetes: Container orchestration platform." https://kubernetes.io/

Recommended for horizontal scaling of multi-agent system across multiple machines.

---

## Citation Style

All references follow a modified numeric citation format (author year, source). For academic papers, APA style with content rephrasing note where applicable per licensing compliance requirements.

---

## Additional Resources

### NIFTY 50 Index Information

The NIFTY 50 index comprises 50 stocks from the National Stock Exchange of India, spanning 11 sectors:
- Technology (Infosys, TCS, Wipro, HCLTech, Tech Mahindra)
- Financial Services (HDFC Bank, ICICI Bank, Kotak Mahindra, SBI, Axis Bank)
- Automotive (Maruti Suzuki, Bajaj Auto, Mahindra & Mahindra, Hero MotoCorp)
- Pharmaceuticals (Dr. Reddy's Labs, Sun Pharma)
- FMCG (Hindustan Unilever, ITC, Nestlé India, Britannia)
- Infrastructure (Larsen & Toubro, Reliance, Adani Green)
- Consumer (Titan, Asian Paints, Dmart, Page Industries)
- Energy (Reliance, NTPC, Coal India)
- Materials (Grasim, Hindalco)
- Real Estate (DLF, Prestige Estates)
- Utilities (Power Grid, REC)

---

## Glossary of Terms

**Anomaly Score**: Numerical score (0–1) from Isolation Forest; higher = more anomalous (unusual combination of financial ratios).

**Cache-Augmented Generation (CAG)**: Retrieval-based LLM grounding using cached company memory and sector context, rather than embedding-based vector search.

**CAGR**: Compound Annual Growth Rate; used in investment simulator calculations.

**Current Ratio**: Current Assets / Current Liabilities; liquidity metric.

**Debt-to-Equity (D/E)**: Total Debt / Total Equity; leverage metric.

**LLM**: Large Language Model (Groq, OpenAI).

**NIFTY 50**: India's 50 largest listed companies by market cap.

**OPM**: Operating Profit Margin = Operating Profit / Revenue; profitability metric.

**Percentile Rank**: Position (0–100) within peer group; 50 = median.

**ROCE**: Return on Capital Employed; capital efficiency metric.

**RAG**: Retrieval-Augmented Generation; LLM-based synthesis grounded in retrieved context.

**Red Flag**: Financial metric or pattern indicating potential risk (high debt, low profitability, anomalous ratios).

**ROE**: Return on Equity; profitability metric.

**Sector**: Industry category (Technology, Financials, Automotive, etc.); used for peer grouping.

**Z-Score (Standardized)**: (value - mean) / standard_deviation; normalized scale for feature comparison.

---

## Contact and Support

For technical issues, feature requests, or academic inquiries regarding this project, refer to the project README and GitHub issues tracker (if available).

---
