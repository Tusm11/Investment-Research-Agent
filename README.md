# Investment Research Agent

An AI-powered investment research platform that analyzes NIFTY 50 companies with real-time financial data, peer comparisons, and machine learning-driven insights.

## Features

- **Real-time Financial Data**: P&L, Balance Sheet, Cash Flow statements for 4 years
- **Peer Comparison**: Percentile rankings across 15+ financial metrics
- **ML Anomaly Detection**: Isolation Forest model flags financial outliers
- **AI Research Assistant**: Ask natural language questions about companies
- **Price Forecasting**: XGBoost predictions for stock price movements
- **Market Intelligence**: News sentiment, analyst consensus, macro drivers
- **Interactive Dashboard**: View all 50 NIFTY companies with live metrics

## Tech Stack

**Backend:**
- FastAPI (Python web framework)
- yfinance (financial data)
- scikit-learn (Isolation Forest)
- XGBoost (price predictions)
- Groq API (LLM for research)

**Frontend:**
- HTML5 + CSS3 + JavaScript
- Responsive material design
- Real-time data updates

**Data Sources:**
- Yahoo Finance (OHLCV, fundamentals)
- NewsAPI (sentiment analysis)
- NSE NIFTY50 constituents

## Quick Start

### Prerequisites
- Python 3.9+
- pip / venv

### Installation

```bash
git clone https://github.com/Tusm11/Investment-Research-Agent.git
cd Investment-agent
python -m venv .venv
source .venv/Scripts/activate  # On Windows
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:
```
GROQ_API_KEY=your_groq_api_key
NEWSAPI_KEY=your_newsapi_key
```

### Run

```bash
python backend/main.py
```

Server starts at `http://0.0.0.0:8502`

Open `http://localhost:8502` in your browser.

## Project Structure

```
├── agent_1/              # Data fetching agent
├── agent_2/              # Financial analysis & red flags
├── agent_3/              # Market intelligence & events
├── agent_4/              # Forecast & verdict generation
├── backend/              # FastAPI server
│   ├── main.py
│   ├── financial_calculators.py
│   └── research_enhancer.py
├── public/               # Frontend (HTML/CSS/JS)
│   ├── dashboard.html
│   ├── company.html
│   └── styles.css
├── pipeline.py           # Orchestrates all agents
├── rag_assistant.py      # RAG chat assistant
└── requirements.txt
```

## API Endpoints

- `GET /api/nifty50` - All 50 companies snapshot
- `GET /api/company/{ticker}` - Full company research
- `GET /api/company/{ticker}/price-history` - 6-month price chart
- `POST /api/chat` - AI research questions

## Key Metrics

Each company shows:
- **Financial**: Revenue, EBIT, Net Profit, EPS
- **Ratios**: ROCE, ROE, P/E, D/E, Current Ratio
- **Health**: Red flags, anomaly score, fundamental quality
- **Market**: Price, P/E, analyst consensus, 52-week range
- **Forecast**: Next quarter price prediction + confidence

## Features Highlights

✓ Balance sheet with 4-year history (2022 empty year removed)  
✓ All financial fields auto-populated with calculation fallbacks  
✓ Peer percentile rankings (0-100 scale)  
✓ Forecast column for all 50 companies  
✓ Price charts with 6 timeframes  
✓ Per-tab AI assistant context  
✓ No reasoning leakage in chat responses  

## Performance

- Full 50-company analysis: ~15-20 seconds
- Caching reduces repeat queries to <1 second
- Async data fetching for parallel processing

## Future Enhancements

- [ ] Portfolio optimization
- [ ] Options chain analysis
- [ ] Real-time alerts
- [ ] Backtesting engine
- [ ] Export reports (PDF/Excel)

## License

MIT License - see LICENSE file

## Author

Investment Research Agent - Built with ❤️ for Indian stock investors

---

**Disclaimer**: This tool is for research purposes only. Not financial advice. Always do your own due diligence before investing.
