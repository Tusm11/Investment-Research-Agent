# 9. Model Output

This section documents actual output artifacts from the pipeline. Sample data reflects typical NIFTY 50 company analysis.

## 9.1 Agent 1 Output: Data Fetching

**Sample Output** (TCS.NS, 2024 snapshot):

```json
{
  "ticker": "TCS.NS",
  "company_info": {
    "company_name": "Tata Consultancy Services",
    "sector": "Technology",
    "industry": "IT Services",
    "business_summary": "Tata Consultancy Services is an IT services and consulting company...",
    "website": "www.tcs.com",
    "employees": 456445,
    "market_cap": 13500000000000,
    "pe_ratio": 28.5,
    "dividend_yield": 0.012,
    "debtToEquity": 0.18,
    "currentRatio": 2.45,
    "returnOnEquity": 0.34,
    "operatingMargins": 0.221,
    "revenueGrowth": 0.12
  },
  "price_history": {
    "current_price": 3200.0,
    "open": 3185.0,
    "day_high": 3210.0,
    "day_low": 3150.0,
    "week_52_high": 3500.0,
    "week_52_low": 2700.0,
    "average_volume": 5234567,
    "ohlcv": [
      [3180, 3210, 3150, 3190, 5234567],
      [3190, 3220, 3175, 3205, 4987654],
      ...
    ]
  },
  "news": [
    {
      "title": "TCS Q3 FY2024 earnings beat expectations",
      "summary": "Tata Consultancy Services reported Q3 net profit of ₹11,600 crore, beating analyst expectations...",
      "source": "Reuters",
      "url": "https://reuters.com/...",
      "date": "2024-01-15",
      "sentiment": "positive"
    },
    {
      "title": "Tech sector faces headwinds amid US slowdown",
      "summary": "Indian IT companies may see reduced demand from US clients...",
      "source": "Bloomberg",
      "date": "2024-01-12",
      "sentiment": "negative"
    }
  ],
  "analyst_data": {
    "status": "success",
    "recommendation_key": "buy",
    "number_of_analysts": 25,
    "target_mean_price": 3500.0,
    "current_price": 3200.0,
    "upside_downside_percent": 8.5,
    "buy": 18,
    "hold": 5,
    "sell": 2
  },
  "financial_metrics": {
    "roce": 0.235,
    "operating_margin": 0.221,
    "net_margin": 0.18,
    "debt_to_equity": 0.18,
    "current_ratio": 2.45,
    "cash_flow": 15000000000,
    "sales": 64000000000
  },
  "market_drivers": {
    "nifty50_return_1m": 0.05,
    "sector_avg_return_1m": 0.08,
    "macro_environment": "Mixed: RBI maintained rates; inflation stable"
  },
  "_fetch_complete_time": 23.4
}
```

---

## 9.2 Agent 2 Output: Fundamental Health Analysis

**Sample Output** (TCS.NS):

```json
{
  "ticker": "TCS.NS",
  "financial_facts": {
    "ROCE": 23.5,
    "OperatingMargin": 22.1,
    "Debt": 5000000000,
    "CurrentRatio": 2.45,
    "NetProfit": 11600000000,
    "CashFromOperatingActivity": 15000000000,
    "DebtorDays": 58.5,
    "InventoryDays": 12.3,
    "WorkingCapitalDays": 45.2
  },
  "red_flags": [],
  "model_assessment": {
    "model_path": "agent_2/isolation_forest_model.pkl",
    "model_loaded": true,
    "prediction": 1,
    "decision_function": 1.234,
    "anomaly_score": 0.0,
    "is_anomaly": false,
    "used_features": [
      "Debt To Equity_z",
      "Debt Ratio_z",
      "Net Debt To Ebitda_z",
      "Total Debt To Capitalization_z",
      "Current Ratio_z",
      "Quick Ratio_z",
      "Cash Ratio_z",
      "Net Profit Margin_z",
      "Operating Profit Margin_z",
      "ROE_z",
      "ROIC_z",
      "Income Quality_z",
      "Cash Flow To Debt Ratio_z",
      "Interest Coverage_z",
      "Asset Turnover_z"
    ]
  },
  "peer_comparison": {
    "sector": "Technology",
    "peers": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "metrics": {
      "ROCE": {
        "company": 23.5,
        "sector_average": 18.2,
        "percentile": 78
      },
      "OPM %": {
        "company": 22.1,
        "sector_average": 19.5,
        "percentile": 65
      },
      "Debt": {
        "company": 5000000000,
        "sector_average": 8500000000,
        "percentile": 35
      },
      "Current Ratio": {
        "company": 2.45,
        "sector_average": 2.1,
        "percentile": 70
      },
      "Net Profit": {
        "company": 11600000000,
        "sector_average": 6200000000,
        "percentile": 85
      },
      "Sales": {
        "company": 64000000000,
        "sector_average": 45000000000,
        "percentile": 82
      }
    }
  },
  "fundamental_profile": {
    "overall_health": "Strong",
    "strengths_count": 5,
    "weaknesses_count": 0,
    "red_flag_count": 0,
    "anomaly_risk": "Low"
  },
  "fundamental_signals": {
    "strengths": [
      "ROCE at 23.5% is strong (78th percentile); well above cost of capital",
      "Operating margin of 22.1% demonstrates pricing power and efficiency",
      "Low debt relative to peers; D/E of 0.18 is conservative (35th percentile)",
      "Current ratio of 2.45 indicates strong short-term liquidity",
      "Net profit scaling at ₹11,600 crore; largest in tech sector (85th percentile)"
    ],
    "weaknesses": []
  }
}
```

**Interpretation**:
- **ROCE 23.5% (78th percentile)**: TCS generates ₹23.5 in operating profit for every ₹100 of capital invested, outperforming 78% of sector peers.
- **OPM 22.1% (65th percentile)**: Operating margin is healthy, indicating strong pricing and operational efficiency.
- **Low Debt (D/E 0.18, 35th percentile)**: Conservative balance sheet; less leveraged than peers.
- **Isolation Forest anomaly_score = 0.0 (prediction = +1)**: No financial anomalies detected; company exhibits normal pattern of ratios.

---

## 9.3 Agent 3 Output: Market Intelligence & Perception

**Sample Output** (TCS.NS):

```json
{
  "ticker": "TCS.NS",
  "sentiment": "Bullish",
  "market_intelligence_report": {
    "market_perception": "Market consensus is bullish on TCS. Analysts target ₹3,500 (8.5% upside from current ₹3,200). Q3 earnings beat, combined with stable IT spending expectations, is driving optimism. However, US tech sector slowdown poses a near-term headwind.",
    "risk_factors": [
      "US economic slowdown could reduce IT spending from largest client base (US = 55% of revenue)",
      "Rupee appreciation pressures margins on dollar-denominated revenues",
      "Tech sector valuation at historic highs; correction risk if macro softens"
    ],
    "positive_factors": [
      "Strong Q3 execution: revenue beat, margin expansion",
      "Digital transformation tailwinds: cloud, AI, cybersecurity demand strong",
      "Consistent dividend payments signal management confidence"
    ],
    "key_catalysts": [
      "Q4 FY2024 earnings (Feb 2024): guidance on FY2025 growth",
      "RBI policy: rupee volatility may ease if rates held",
      "US Fed meetings: market-sensitive; slowdown expectations shift with each meeting"
    ]
  },
  "market_facts": {
    "recommendation": "buy",
    "target_price": 3500.0,
    "analyst_count": 25,
    "upside_downside_percent": 8.5,
    "buy": 18,
    "hold": 5,
    "sell": 2
  },
  "recent_events": [
    {
      "title": "TCS reports strong Q3 FY2024 earnings",
      "summary": "Q3 net profit ₹11,600 crore, up 13% YoY. Operating margin expanded 50 bps to 22.1%.",
      "source": "Reuters",
      "date": "2024-01-15",
      "sentiment": "positive"
    },
    {
      "title": "Tech sector may see reduced US IT spending in 2024",
      "summary": "IDC forecasts 2% slowdown in US IT budgets as enterprises prioritize cost optimization.",
      "source": "Bloomberg",
      "date": "2024-01-12",
      "sentiment": "negative"
    }
  ],
  "risks": [
    "US economic slowdown reduces demand from largest client base",
    "Rupee appreciation pressures rupee-equivalent margins",
    "Tech sector valuation at historic highs"
  ],
  "opportunities": [
    "AI and cloud transformation driving pricing power and growth",
    "Emerging markets expansion (India, Southeast Asia) diversifies revenue",
    "Margin expansion through operational leverage"
  ]
}
```

**Sentiment Derivation**:
- Analyst recommendation key = "buy" → Bullish sentiment assigned
- If recommendation was "hold" → would check news sentiment
- If no analyst data → sentiment = None (not defaulted to 50)

---

## 9.4 Agent 4 Output: Report Synthesis

**Sample Output** (Question: "Is TCS financially healthy?"):

```json
{
  "response": "TCS is in strong financial health. Key indicators: ROCE at 23.5% (78th percentile) shows efficient capital deployment; operating margin of 22.1% demonstrates pricing power; debt-to-equity of 0.18 is conservative (35th percentile); current ratio of 2.45 indicates strong liquidity. The Isolation Forest model detected no financial anomalies (score 0.0). Red flags: none. Peer comparison shows TCS outperforms sector median on profitability and scale metrics. Near-term risk: US economic slowdown may impact IT spending. Opportunity: AI/cloud demand tailwinds. Analyst consensus is bullish with ₹3,500 target (8.5% upside).",
  "intent": "financial_health",
  "consensus_rating": "BUY",
  "target_price": 3500.0,
  "expected_return": 8.5,
  "sections_used": ["company_info", "financial_metrics", "peer_comparison", "market_facts", "risks", "opportunities"],
  "reasoning_steps": [
    "Analyzed capital efficiency: ROCE 23.5% indicates strong returns on invested capital",
    "Compared debt levels: D/E 0.18 is conservative relative to sector average 0.45",
    "Assessed liquidity: current ratio 2.45 ensures ability to meet short-term obligations",
    "Ran Isolation Forest: no multivariate anomalies detected across 15 financial ratios",
    "Identified risks: US slowdown, rupee strength, valuation",
    "Weighted analyst consensus: 18 buy, 5 hold, 2 sell = bullish majority"
  ]
}
```

---

## 9.5 Company Memory (Unified State)

**Sample Output** (merged from all agents):

```json
{
  "company_info": {
    "name": "Tata Consultancy Services",
    "ticker": "TCS.NS",
    "sector": "Technology",
    "industry": "IT Services",
    "summary": "Tata Consultancy Services is a global IT services and consulting company...",
    "market_cap": 13500000000000,
    "pe_ratio": 28.5,
    "dividend_yield": 0.012,
    "peers": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"]
  },
  "financial_metrics": {
    "roce": 23.5,
    "operating_margin": 22.1,
    "net_margin": 18.0,
    "debt_to_equity": 0.18,
    "current_ratio": 2.45,
    "cash_flow": 15000000000,
    "sales": 64000000000
  },
  "financial_facts": {
    "ROCE": 23.5,
    "OperatingMargin": 22.1,
    "Debt": 5000000000,
    "CurrentRatio": 2.45,
    "NetProfit": 11600000000,
    "CashFromOperatingActivity": 15000000000,
    "DebtorDays": 58.5,
    "InventoryDays": 12.3,
    "WorkingCapitalDays": 45.2
  },
  "peer_comparison": {
    "sector": "Technology",
    "peers": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "metrics": {
      "ROCE": {"company": 23.5, "sector_average": 18.2, "percentile": 78},
      "OPM %": {"company": 22.1, "sector_average": 19.5, "percentile": 65},
      "Debt": {"company": 5000000000, "sector_average": 8500000000, "percentile": 35},
      ...
    }
  },
  "anomaly_detection": {
    "anomaly_score": 0.0,
    "model_assessment": {"prediction": 1, "is_anomaly": false},
    "red_flags_count": 0,
    "red_flags": []
  },
  "price_data": {
    "current": 3200.0,
    "open": 3185.0,
    "day_high": 3210.0,
    "day_low": 3150.0,
    "high_52w": 3500.0,
    "low_52w": 2700.0,
    "avg_volume": 5234567,
    "ohlcv_count": 180,
    "ohlcv": [[3180, 3210, 3150, 3190, 5234567], ...]
  },
  "market_facts": {
    "recommendation": "buy",
    "target_price": 3500.0,
    "analyst_count": 25,
    "upside_downside_percent": 8.5,
    "buy": 18,
    "hold": 5,
    "sell": 2
  },
  "risks": [
    "US economic slowdown reduces IT spending from largest client base",
    "Rupee appreciation pressures margins",
    "Tech sector valuation at historic highs"
  ],
  "opportunities": [
    "AI and cloud transformation drives growth",
    "Emerging markets expansion",
    "Margin expansion through leverage"
  ],
  "market_intelligence": {
    "market_perception": "Bullish; Q3 earnings beat, analyst consensus buy with 8.5% upside",
    "risk_factors": ["US slowdown", "Rupee strength", "Valuation"],
    "positive_factors": ["Q3 beat", "Digital tailwinds", "Dividend confidence"],
    "key_catalysts": ["Q4 earnings", "RBI policy", "US Fed"]
  },
  "dashboard": {
    "business_fundamentals": {
      "overall": "Strong",
      "strengths": ["High ROCE", "Strong margins", "Low debt", "Scale"],
      "watch_items": ["US exposure", "Rupee volatility"]
    },
    "market_mood": {
      "overall_sentiment": "Bullish",
      "positive_factors": ["Q3 beat", "Analyst consensus"],
      "areas_to_watch": ["US slowdown"]
    },
    "price_story": {
      "trend": "Up",
      "distance_from_52w": "Small (near highs)",
      "support_resistance": "Support: ₹3,050; Resistance: ₹3,500"
    },
    "financial_stability": {
      "risk_level": "Low",
      "concerns": []
    }
  }
}
```

---

## 9.6 API Response: /api/company-research

**HTTP Status**: 200 OK

**Response Body**:

```json
{
  "success": true,
  "ticker": "TCS.NS",
  "company_name": "Tata Consultancy Services",
  "sector": "Technology",
  "current_price": 3200.0,
  "expected_return": 8.5,
  "target_price": 3500.0,
  "sentiment_score": 75,
  "red_flags": [],
  "financial_metrics": {
    "roce": 23.5,
    "operating_margin": 22.1,
    "debt_to_equity": 0.18,
    "current_ratio": 2.45
  },
  "peer_comparison": {
    "sector": "Technology",
    "metrics": {
      "ROCE": {"company": 23.5, "sector_average": 18.2, "percentile": 78},
      ...
    }
  },
  "risks": [
    "US economic slowdown",
    "Rupee appreciation",
    "Tech sector valuation"
  ],
  "opportunities": [
    "AI and cloud transformation",
    "Emerging markets expansion",
    "Margin expansion"
  ],
  "_data_quality": {
    "price_available": true,
    "news_available": true,
    "sentiment_analyzed": true,
    "risks_identified": true,
    "peer_data_available": true,
    "analysis_errors": []
  },
  "_data_sources": {
    "price": "yfinance",
    "news": "Google News RSS + NewsAPI",
    "analyst": "yfinance recommendations",
    "fundamentals": "yfinance balance sheet, income statement",
    "peers": "NIFTY50 list + peer health features fetch"
  }
}
```

---

## 9.7 Chat Output: /api/chat

**Request**:
```json
{
  "symbol": "TCS.NS",
  "question": "Why is TCS's debt-to-equity so low compared to peers?",
  "tab": "Financials",
  "context": "Financials Tab: Debt/Equity = 0.18, Sector Average = 0.45"
}
```

**Response**:
```json
{
  "response": "TCS maintains a conservative capital structure with debt-to-equity of 0.18, compared to the technology sector average of 0.45. This reflects several strategic choices: (1) Strong free cash flow generation (₹15,000 crore annually) reduces reliance on debt financing; (2) Large market cap (₹13.5 trillion) and investment-grade credit rating allow access to low-cost capital, but management prioritizes financial flexibility; (3) IT services business generates consistent, high-quality earnings with low capex needs, so external leverage is unnecessary; (4) Conservative approach aligns with shareholder expectations for steady dividends rather than aggressive growth financing. The low leverage translates to lower financial risk and higher resilience during economic downturns — a competitive advantage for TCS given US client concentration exposure.",
  "status": "success",
  "company": "TCS.NS"
}
```

---

## 9.8 HTML Report Output

Generated via `/api/generate-report`, the report includes:

- **Cover Page**: Company name, sector, current price, analyst rating, report date
- **Executive Summary**: 1-page health assessment (3–5 key highlights, 2–3 risks, investment recommendation)
- **Company Overview**: Business summary, key products/services, sector position
- **Financials**: P&L, balance sheet, cash flow (3-year history if available)
- **Fundamental Analysis**: ROCE, profitability, leverage, liquidity (tabular format)
- **Peer Comparison**: Percentile rank table (company vs. sector median for 12 metrics)
- **Market Intelligence**: Analyst consensus, target price, sentiment, recent news
- **Risks & Opportunities**: Bulleted lists with color-coded severity
- **Recommendation**: BUY/HOLD/SELL with target price and expected return

---

## 9.9 Data Quality Indicators

The `_data_quality` and `_data_sources` metadata are included in every API response:

```json
"_data_quality": {
  "price_available": true,           # current_price is not None
  "news_available": true,             # news articles fetched successfully
  "sentiment_analyzed": true,         # agent3 ran; sentiment != None
  "risks_identified": true,           # red_flags or risks populated
  "peer_data_available": true,        # peer_comparison metrics exist
  "analysis_errors": []               # No exceptions caught during pipeline
}
```

This allows frontend to display a confidence indicator: if any flag is false, the UI shows a warning (e.g., "Sentiment data unavailable for this company").

---
