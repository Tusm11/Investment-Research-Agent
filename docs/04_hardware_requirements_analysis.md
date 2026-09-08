# 4. Hardware Requirements Analysis

## 4.1 Hardware Requirements

The system is designed for development and small-to-medium scale deployment on commodity hardware. It does not require GPU acceleration.

| Component | Specification | Rationale |
|-----------|---------------|-----------|
| **CPU** | 4+ cores (Intel i5/i7, AMD Ryzen 5+, or ARM equivalent) | Parallel execution: Agent 2 peer comparison (8 workers), Agent 3 market synthesis, Agent 1 data fetch (6 workers) benefit from multi-core parallelism. Single-core systems will experience timeouts. |
| **RAM** | 8 GB minimum, 16 GB recommended | Agent processes (4 agents), yfinance in-memory caching, Isolation Forest model in memory (~50 MB), concurrent request handling. 8 GB sufficient for individual user; 16 GB for modest multi-user deployments. |
| **Storage** | 2 GB minimum (SSD preferred) | OS + Python runtime + dependencies (1 GB), ML models (xgb_classifier.pkl ~100 MB, xgb_regressor.pkl ~100 MB, isolation_forest_model.pkl ~50 MB), company_memory.json snapshots, chart PNG cache (~50-100 MB for 50 companies). SSD reduces I/O latency for model loading. |
| **Network** | Stable 10+ Mbps internet | Continuous yfinance API calls, NewsAPI, Groq LLM inference, NSE/BSE data fetch. Rate limiting risk if < 5 Mbps. |
| **GPU** | Not required | Isolation Forest, XGBoost, and LLM inference (via Groq API, not local) do not require GPU. Local LLM serving would benefit from GPU, but architecture uses cloud-based Groq. |

## 4.2 Additional Requirements

### Software Dependencies

**Python**: 3.9 or higher (required for f-strings, type hints, async/await in FastAPI)

**Key Libraries**:
- `langchain` (>= 0.1.0): Agent orchestration, prompt templates, LLM chaining
- `scikit-learn` (>= 1.3.0): Isolation Forest anomaly detection
- `xgboost` (>= 2.0.0): Price direction and magnitude prediction
- `yfinance` (>= 0.2.0): Financial data fetching
- `groq` (>= 0.4.0): LLM API client (Groq inference)
- `fastapi` (>= 0.100.0): Web framework
- `pandas` (>= 1.5.0): Data manipulation
- `numpy` (>= 1.24.0): Numerical computation
- `requests` (>= 2.31.0): HTTP client for web scraping
- `trafilatura` (>= 1.6.0): Web page extraction (company IR scraping)
- `plotly` (>= 5.0.0): Chart rendering (frontend, via CDN)
- `pydantic` (>= 2.0.0): FastAPI request validation

See `requirements.txt` for complete dependency list with pinned versions.

### External API Keys

- **Groq API Key** (`GROQ_API_KEY`): Required for LLM-based intent classification and report synthesis. Free tier available at groq.com.
- **NewsAPI Key** (optional): Fallback for news fetching if Google News RSS unavailable.

### Network Requirements

- **yfinance**: Requires internet; rate limits ~2 calls per second per IP.
- **Groq LLM API**: Must have stable outbound HTTPS to api.groq.com (port 443).
- **NSE/BSE Data**: Optional; nselib uses web scraping (no API key needed but depends on site availability).
- **Google News RSS**: Public feed; no authentication needed but does not allow programmatic volume (fallback: NewsAPI).

### Environment Configuration

Create a `.env` file in the project root with:

```
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=mixtral-8x7b-32768
# Optional: NEWSAPI_KEY=your_newsapi_key_here
# Optional: DEBUG=true
```

### Deployment Considerations

**Development**: Single developer machine with 8 GB RAM, stable home internet.

**Small Production (1–10 concurrent users)**: 
- AWS EC2 t3.large (2 vCPU, 8 GB RAM) or equivalent
- Or local server with 4+ cores, 16 GB RAM

**Multi-User Deployment**:
- Consider caching layer (Redis) to reduce duplicate API calls
- Implement API rate limiting per-user
- Use process pool (Gunicorn with 4+ workers) for FastAPI

---
