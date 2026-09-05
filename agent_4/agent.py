"""Agent 4 - Reasoning Agent with four internal stages."""

from __future__ import annotations
import json, os, re, time
from math import prod
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

# Cache for LLM classification results (valid for 60 seconds)
_classification_cache = {}
_CACHE_TTL = 60

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")

try:
    from agent_1.data_fetcher import fetch_company_website_context
except Exception:
    fetch_company_website_context = None

# STAGE 1: Question Classifier

def classify_question(query, memory=None):
    """
    Classify the user's question and determine what tools are needed.
    
    Returns: {
        "intent": str,           # financial_health, explanation, comparison, etc.
        "entities": list,        # company names/tickers mentioned
        "needs": list,           # required memory sections
        "tools": list,           # tools to use (financial, market, chart, math, education, comparison)
    }
    """
    # Check cache first
    cache_key = query.strip()
    if cache_key in _classification_cache:
        cached_result, cached_time = _classification_cache[cache_key]
        if time.time() - cached_time < _CACHE_TTL:
            return cached_result
    
    system_prompt = """You are a Question Classifier for an investment research assistant.
    
Your job is to analyze the user's question and determine:
1. What the user is trying to learn (intent)
2. Which companies are mentioned (entities)
3. What data sections are needed
4. Which tools to use

Return compact JSON with keys: intent, entities, needs, tools.

Intents to recognize:
- financial_health: Assessing company financial stability (ROCE, debt, margins, liquidity)
- explanation: Explaining metrics (ROCE, P/E, debt, etc.)
- education: Teaching concepts (What is ROCE?, Why is debt important?)
- comparison: Comparing two or more companies
- calculation: Mathematical queries (CAGR, future value, returns)
- historical_performance: Historical price changes over specific periods (e.g., "performance in last 5 years", "return over 6 months", "gain in past year")
- sector_ranking: Finding best/worst performers in a sector
- investment_simulator: Calculate returns from historical investments
- market_intelligence: News, sentiment, analyst views, sector trends
- price_analysis: Price movements, support/resistance, volatility
- investment_summary: Long-term investment suitability
- news: Recent events, news summaries
- unsupported: Questions about future price predictions

RULES:
1. If the question asks about company performance, return, gain, loss over time - it's HISTORICAL_PERFORMANCE
2. If the question asks "What is X?" where X is a financial concept (ROCE, P/E ratio, etc.) - it's EDUCATION
3. Do NOT confuse company performance with explaining concepts

Entities: Extract company names or ticker symbols.
Needs: List of required memory sections from: company_info, financial_metrics, financial_facts, peer_comparison, price_data, chart_metrics, risk_metrics, news_articles, events, analyst_data, market_facts, market_intelligence, opportunities, risks.
Tools: List of tools: financial, market, chart, math, education, comparison, news.

Example output for "Why is Reliance's debt high?":
{
    "intent": "explanation",
    "entities": ["Reliance"],
    "needs": ["company_info", "financial_metrics", "peer_comparison"],
    "tools": ["financial", "market"]
}

Example output for "What is the performance of Reliance in last 5 years?":
{
    "intent": "historical_performance",
    "entities": ["Reliance"],
    "needs": ["price_data", "chart_metrics"],
    "tools": ["historical"]
}

Example output for "What is ROCE?":
{
    "intent": "education",
    "entities": [],
    "needs": [],
    "tools": ["education"]
}

Example output for "Compare TCS and Infosys":
{
    "intent": "comparison",
    "entities": ["TCS", "Infosys"],
    "needs": ["financial_metrics", "price_data", "chart_metrics", "market_intelligence"],
    "tools": ["comparison"]
}

Example output for "Can I invest ₹1 lakh at 12% for 5 years?":
{
    "intent": "calculation",
    "entities": [],
    "needs": [],
    "tools": ["math"]
}

Example output for "Will Reliance reach ₹5000 next year?":
{
    "intent": "unsupported",
    "entities": ["Reliance"],
    "needs": ["company_info", "price_data", "analyst_data"],
    "tools": []
}
"""

    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{question}")])
    
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"), temperature=0)
    
    try:
        response = (prompt | llm).invoke({"question": query.strip()}).content.strip()
        response = re.sub(r"^```(?:json)?|```$", "", response, flags=re.IGNORECASE | re.MULTILINE).strip()
        result = json.loads(response)
        result["_query"] = query
        return _normalize_classification(result)
    except json.JSONDecodeError:
        # LLM returned invalid JSON, use fallback
        result = _fallback_classification(query)
    except Exception as e:
        # Fallback classification
        result = _fallback_classification(query)
    else:
        result = _normalize_classification(result)
    
    # Cache the result
    _classification_cache[query.strip()] = (result.copy(), time.time())
    return result


def _normalize_classification(data):
    """Normalize classification output."""
    if not isinstance(data, dict):
        return _fallback_classification("")
    
    intent = (data.get("intent") or "general").lower()
    entities = data.get("entities", []) or []
    needs = list(set(str(n) for n in (data.get("needs") or []) if n))
    tools = list(set(str(t) for t in (data.get("tools") or []) if t))
    
    result = {
        "intent": intent,
        "entities": entities,
        "needs": needs,
        "tools": tools,
    }
    
    # Post-processing: Override education intent if question is about historical performance
    query_lower = data.get("_query", "").lower()
    if intent == "education" and any(k in query_lower for k in ["performance", "return", "gain", "loss"]):
        return _fallback_classification(data.get("_query", ""))
    
    return result


def _fallback_classification(query):
    """Fallback classification when LLM fails."""
    text = (query or "").lower()
    
    # New: Historical performance detection - check FIRST to override "what is" and "explain"
    if any(k in text for k in ["performance", "return", "increase", "decrease", "gain", "loss", "growth", "last", "ago", "past", "years"]):
        intent = "historical_performance"
        tools = ["historical"]
        needs = ["price_data", "chart_metrics"]
    # New: Sector ranking detection
    elif any(k in text for k in ["best", "top", "worst", "leader", "perform", "rank"]):
        intent = "sector_ranking"
        tools = ["sector_ranking"]
        needs = ["company_info", "financial_metrics", "price_data", "chart_metrics"]
    # New: Investment simulator detection
    elif any(k in text for k in ["invest", "bought", "purchased", "years ago"]):
        intent = "investment_simulator"
        tools = ["investment_simulator", "math"]
        needs = ["price_data"]
    elif any(k in text for k in ["compare", "vs", "versus"]):
        intent = "comparison"
        tools = ["comparison"]
        needs = ["financial_metrics", "price_data"]
    elif any(k in text for k in ["cagr", "future value", "returns", "₹.*lakh", "₹.*crore", "invest.*ago"]):
        intent = "calculation"
        tools = ["math"]
        needs = ["price_data"]
    elif any(k in text for k in ["what is", "explain", "define", "meaning"]):
        intent = "education"
        tools = ["education"]
        needs = []
    elif any(k in text for k in ["sentiment", "news", "analyst", "opinion"]):
        intent = "market_intelligence"
        tools = ["market"]
        needs = ["news_articles", "analyst_data"]
    elif any(k in text for k in ["fall", "rising", "price", "52w", "support", "resistance"]):
        intent = "price_analysis"
        tools = ["chart"]
        needs = ["price_data", "chart_metrics"]
    elif any(k in text for k in ["healthy", "debt", "roce", "profitable", "liquidity"]):
        intent = "financial_health"
        tools = ["financial"]
        needs = ["financial_metrics", "company_info"]
    elif any(k in text for k in ["investment", "long term", "suitable"]):
        intent = "investment_summary"
        tools = ["financial", "market"]
        needs = ["financial_metrics", "news_articles", "analyst_data", "opportunities", "risks"]
    else:
        intent = "general"
        tools = ["financial", "market"]
        needs = ["financial_metrics", "company_info"]
    
    return {
        "intent": intent,
        "entities": [],
        "needs": needs,
        "tools": tools,
    }

# STAGE 2: Context Retriever

def retrieve_context(memory, required_sections):
    """Retrieve only the required sections from memory."""
    context = {}
    for section in set(required_sections):
        if section in memory:
            context[section] = memory[section]
    return context

# STAGE 3 & 4: Reasoning and Answer Generation

def answer_with_reasoning(query, memory, context, plan):
    """
    Generate answer using LLM reasoning with specialized tools.
    """
    intent = plan["intent"]
    tools = plan["tools"]
    
    # Check if dashboard insights exist and can answer the question directly
    dashboard = memory.get("dashboard", {})
    
    # For financial_health questions, check business_fundamentals first
    if intent == "financial_health" and dashboard.get("business_fundamentals"):
        business = dashboard["business_fundamentals"]
        debt = context.get("company_info", {}).get("debt_to_equity")
        roce = context.get("company_info", {}).get("return_on_equity") or context.get("financial_metrics", {}).get("roce")
        
        # If query is about debt, use debt-specific answer
        if "debt" in query.lower() and debt is not None:
            return {
                "response": _generate_dashboard_answer(query, business, "Debt Position", debt),
                "sections_used": list(context.keys())
            }
        # If query is about ROCE/returns, use ROCE-specific answer
        elif ("roce" in query.lower() or "returns" in query.lower() or "capital" in query.lower()) and roce is not None:
            return {
                "response": _generate_dashboard_answer(query, business, "ROCE Position", roce),
                "sections_used": list(context.keys())
            }
        # Use debt answer if available
        elif debt is not None:
            return {
                "response": _generate_dashboard_answer(query, business, "Debt Position", debt),
                "sections_used": list(context.keys())
            }
        elif roce is not None:
            return {
                "response": _generate_dashboard_answer(query, business, "ROCE Position", roce),
                "sections_used": list(context.keys())
            }
    
    # Build the reasoning prompt based on intent
    if intent == "comparison":
        return _generate_comparison_answer(query, context, memory)
    elif intent == "calculation":
        return _generate_math_answer(query, context)
    elif intent == "education":
        return _generate_education_answer(query, context)
    elif intent == "unsupported":
        return _generate_unsupported_answer(query, intent)
    elif intent == "historical_performance":
        return _generate_historical_performance_answer(query, context)
    elif intent == "sector_ranking":
        return _generate_sector_ranking_answer(query, memory)
    elif intent == "investment_simulator":
        return _generate_investment_simulator_answer(query, context)
    else:
        # Default: general financial reasoning
        return _generate_general_answer(query, context, memory)


def _generate_dashboard_answer(query, dashboard_section, key, value):
    """Generate answer using dashboard insights."""
    # Extract relevant insight from dashboard
    strengths = dashboard_section.get("strengths", [])
    watch_items = dashboard_section.get("watch_items", [])
    summary = dashboard_section.get("summary", "")
    
    # Build answer based on the specific insight
    if "debt" in query.lower():
        debt_reasons = []
        for item in watch_items:
            if "debt" in item.lower() or "high" in item.lower() or "elevated" in item.lower():
                debt_reasons.append(item)
        
        if debt_reasons:
            explanation = "; ".join(debt_reasons)
            return f"Debt is elevated because: {explanation}. {summary}"
        else:
            return f"Debt levels are within acceptable range. {summary}"
    
    return f"Based on the dashboard analysis: {summary}"


def _build_reasoning_prompt(query, context, intent):
    """Build the reasoning prompt for the LLM."""
    parts = []
    
    # System instruction based on intent
    if intent == "financial_health":
        parts.append("You are a financial analyst answering questions about a company's financial health.")
        parts.append("Focus on ROCE, debt levels, profitability, and liquidity.")
    elif intent == "explanation":
        parts.append("You are explaining financial concepts to a beginner investor.")
        parts.append("Be clear, use simple language, and relate to the company's actual data.")
    elif intent == "historical_performance":
        parts.append("You are analyzing historical stock performance.")
        parts.append("Focus on price changes, returns over time, and trend analysis.")
        parts.append("Use bold formatting for the return percentage as it's what users notice first.")
    elif intent == "sector_ranking":
        parts.append("You are ranking companies within a sector based on performance.")
        parts.append("Provide clear rankings and explain the top performer.")
    elif intent == "investment_simulator":
        parts.append("You are calculating investment returns based on historical data.")
        parts.append("Show initial investment, current value, profit, and percentage return.")
    elif intent == "market_intelligence":
        parts.append("You are a market analyst explaining sentiment and news impact.")
        parts.append("Focus on analyst views, news sentiment, and sector trends.")
    elif intent == "price_analysis":
        parts.append("You are a technical analyst explaining price movements.")
        parts.append("Focus on price levels, trends, support/resistance, and volatility.")
    elif intent == "investment_summary":
        parts.append("You are evaluating a company for long-term investment suitability.")
        parts.append("Discuss strengths, risks, and uncertainties without predicting prices.")
        parts.append("Use available evidence: financials, news, analyst views, opportunities, risks.")
    elif intent == "news":
        parts.append("You are summarizing recent news and events for a company.")
        parts.append("Focus on the most important developments and their potential impact.")
    else:
        parts.append("You are an investment research assistant providing clear, reliable answers.")
    
    parts.append("")
    parts.append("User Question: " + query)
    parts.append("")
    
    # Provide context - simplified format for better LLM parsing
    if context:
        parts.append("### DATA FOR ANALYSIS ###")
        for section, data in context.items():
            if isinstance(data, dict):
                parts.append(f"### {section.upper().replace('_', ' ')} ###")
                for k, v in list(data.items())[:30]:
                    val = str(v)[:500] if v is not None else "N/A"
                    parts.append(f"{k}: {val}")
                parts.append("")
        parts.append("### END DATA ###")
        parts.append("")
        parts.append("IMPORTANT: Use ONLY the data above to answer. If data says 'N/A', state 'Data not provided' not 'data not available'.")
    
    # Provide reasoning instructions
    if intent == "financial_health":
        # Add debt info if available
        debt_info = ""
        if context.get("company_info", {}).get("debt_to_equity"):
            debt_info = f" Debt-to-Equity Ratio: {context['company_info']['debt_to_equity']}"
        if context.get("financial_metrics", {}).get("debt_to_equity"):
            debt_info = f" Debt-to-Equity Ratio: {context['financial_metrics']['debt_to_equity']}"
        
        parts.append("IMPORTANT: Use the Available Data above to answer the question. Do not say data is unavailable if it appears in the Available Data section.")
        parts.append("Answer by:")
        parts.append("1. Assessing current financial metrics")
        parts.append("2. Explaining why debt levels are what they are based on the data")
        parts.append("3. Identifying strengths and concerns related to debt")
        parts.append("4. Providing a balanced conclusion")
        if debt_info:
            parts.append(f"Key debt metric: {debt_info.strip()}")
    elif intent == "explanation":
        parts.append("Answer by:")
        parts.append("1. Defining the term clearly")
        parts.append("2. Explaining why it matters")
        parts.append("3. Relating it to this company's actual data")
    elif intent == "investment_summary":
        parts.append("Answer by:")
        parts.append("1. Assessing long-term strengths")
        parts.append("2. Discussing key risks and uncertainties")
        parts.append("3. Evaluating evidence for/against long-term potential")
        parts.append("4. Providing a balanced view without price predictions")
    else:
        parts.append("Provide a clear, evidence-based answer using the data above.")
    
    return "\n".join(parts)

# Tool-Specific Answer Generation

def _generate_general_answer(query, context, memory):
    """Generate answer for general queries."""
    
    # Check if this is a math question
    text = query.lower()
    if "cagr" in text or "future value" in text or "returns" in text or "lakh" in text or "crore" in text or "%" in text and ("invest" in text or "years" in text):
        return _generate_math_answer(query, context)
    
    prompt = _build_reasoning_prompt(query, context, "general")
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"), temperature=0)
    
    try:
        response = (ChatPromptTemplate.from_template(prompt) | llm).invoke({}).content
        return {"response": response, "sections_used": list(context.keys())}
    except Exception as e:
        return {"response": f"Error generating response: {str(e)}", "sections_used": []}


def _build_comparison_table(context, info1, second_company):
    """Build a comparison table for two companies."""
    table_data = []
    
    # First company metrics
    if info1:
        table_data.append(("Company", info1.get("company_name", info1.get("name", "Unknown"))))
        table_data.append(("Sector", info1.get("sector", "N/A")))
        table_data.append(("Market Cap", info1.get("marketCap", "N/A")))
    
    if context.get("financial_metrics"):
        fm = context["financial_metrics"]
        table_data.append(("ROCE", fm.get("roce", "N/A")))
        table_data.append(("Debt/Equity", fm.get("debt_to_equity", "N/A")))
        table_data.append(("Operating Margin", fm.get("operating_margin", "N/A")))
        table_data.append(("Revenue Growth", info1.get("revenueGrowth", "N/A")))
    
    if context.get("price_data"):
        pd = context["price_data"]
        table_data.append(("Current Price", pd.get("current", "N/A")))
        table_data.append(("52W High", pd.get("high_52w", "N/A")))
        table_data.append(("52W Low", pd.get("low_52w", "N/A")))
    
    return table_data


def _generate_comparison_answer(query, context, memory):
    """Generate answer for company comparison queries."""
    info1 = (memory or {}).get("company_info", {})
    info2 = (memory or {}).get("company_info_2", {})
    
    # Extract entities (company names) from the query
    text = query.lower()
    companies_in_query = []
    for name, ticker in [("reliance", "RELIANCE"), ("tcs", "TCS"), ("infosys", "INFY"), ("hdfc", "HDFCBANK"), 
                          ("icici", "ICICIBANK"), ("sbi", "SBIN"), ("btc", "BHARTIARTL"), ("lt", "LT"),
                          ("itc", "ITC"), ("wipro", "WIPRO"), ("hindu", "HINDUNILVR"), ("maruti", "MARUTI"),
                          ("ongc", "ONGC"), ("bpcl", "BPCL"), ("coal", "COALINDIA")]:
        if name in text:
            companies_in_query.append(ticker)
    
    # Check if companies are in the same sector
    sector1 = info1.get("sector", "")
    sector2 = info2.get("sector", "") if info2 else ""
    
    # Check if this is a same-sector comparison
    same_sector = sector1 and sector2 and sector1 == sector2
    
    # Get second company info if available
    second_company = None
    if info2:
        second_company = {
            "name": info2.get("company_name", info2.get("name", "Second Company")),
            "sector": info2.get("sector", ""),
            "roce": (memory.get("financial_metrics_2") or {}).get("roce"),
            "debt_to_equity": (memory.get("financial_metrics_2") or {}).get("debt_to_equity"),
            "pe_ratio": info2.get("trailingPE"),
        }
    
    prompt_parts = [
        "You are comparing two companies for investment purposes.",
        f"User Question: {query}",
        "",
        "First Company:",
    ]
    
    if info1:
        prompt_parts.append(f"  Name: {info1.get('company_name', info1.get('name', 'Unknown'))}")
        prompt_parts.append(f"  Sector: {info1.get('sector', 'N/A')}")
        prompt_parts.append(f"  Market Cap: {info1.get('marketCap', 'N/A')}")
    
    if context.get("financial_metrics"):
        fm = context["financial_metrics"]
        prompt_parts.append(f"  ROCE: {fm.get('roce', 'N/A')}")
        prompt_parts.append(f"  Debt/Equity: {fm.get('debt_to_equity', 'N/A')}")
        prompt_parts.append(f"  Operating Margin: {fm.get('operating_margin', 'N/A')}")
        prompt_parts.append(f"  Revenue Growth: {info1.get('revenueGrowth', 'N/A')}")
    
    if context.get("price_data"):
        pd = context["price_data"]
        prompt_parts.append(f"  Current Price: {pd.get('current', 'N/A')}")
        prompt_parts.append(f"  52W High: {pd.get('high_52w', 'N/A')}")
        prompt_parts.append(f"  52W Low: {pd.get('low_52w', 'N/A')}")
    
    if second_company:
        prompt_parts.append("")
        prompt_parts.append("Second Company:")
        prompt_parts.append(f"  Name: {second_company.get('name', 'Unknown')}")
        prompt_parts.append(f"  Sector: {second_company.get('sector', 'N/A')}")
        
        if second_company.get("roce"):
            prompt_parts.append(f"  ROCE: {second_company.get('roce')}")
        if second_company.get("debt_to_equity"):
            prompt_parts.append(f"  Debt/Equity: {second_company.get('debt_to_equity')}")
        if second_company.get("pe_ratio"):
            prompt_parts.append(f"  P/E Ratio: {second_company.get('pe_ratio')}")
    
    prompt_parts.append("")
    prompt_parts.append("Compare these companies and provide a balanced analysis.")
    
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"), temperature=0)
    
    try:
        response = (ChatPromptTemplate.from_template("\n".join(prompt_parts)) | llm).invoke({}).content
        return {"response": response, "sections_used": list(context.keys())}
    except Exception as e:
        return {"response": f"Error generating response: {str(e)}", "sections_used": []}


def _generate_math_answer(query, context):
    """Generate answer for mathematical calculations."""
    current = (context.get("price_data") or {}).get("current")
    
    text = query.lower()
    
    # Future value calculation
    fv = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:annual(?:ly)?|per year)?\s*(?:for\s*)?(\d+)\s*years?", text)
    if ("invest" in text or "future value" in text) and fv:
        amount_match = re.search(r"(₹?\s*[\d,.]+)\s*(lakh|crore)?", text, re.IGNORECASE)
        if not amount_match:
            amount = 100000  # Default ₹1 lakh
        else:
            amt_str = amount_match.group(1).replace("₹", "").replace(",", "").strip()
            amount = float(amt_str)
            unit = (amount_match.group(2) or "").lower()
            amount *= {"crore": 1e7, "lakh": 1e5}.get(unit, 1)
        
        rate = float(fv.group(1)) / 100.0
        years = int(fv.group(2))
        future_value = amount * ((1 + rate) ** years)
        
        return {
            "response": f"If you invest ₹{amount:,.0f} at {fv.group(1)}% annual return for {years} years, your investment would grow to ₹{future_value:,.0f}.",
            "sections_used": [],
        }
    
    # CAGR calculation
    if "cagr" in text or "compound annual" in text:
        if current:
            initial_match = re.search(r"buy.*?₹([\d,.]+)", text)
            if initial_match:
                initial = float(initial_match.group(1).replace(",", ""))
                cagr = ((current / initial) ** (1 / 5) - 1) * 100 if initial else 0
                return {
                    "response": f"With current price at ₹{current:,.0f} and purchase price of ₹{initial:,.0f} 5 years ago, the CAGR would be {cagr:.2f}%. Note: This is a simplified calculation.",
                    "sections_used": [],
                }
    
    # Returns calculation
    if "returns" in text or "profit" in text:
        target_match = re.search(r"target.*?₹([\d,.]+)", text)
        if target_match and current:
            target = float(target_match.group(1).replace(",", ""))
            upside = ((target - current) / current) * 100
            return {
                "response": f"Current price is ₹{current:,.0f}. To reach the target of ₹{target:,.0f}, the stock would need to increase by {upside:.1f}%.",
                "sections_used": [],
            }
    
    return {
        "response": "I can help calculate investment returns and CAGR. Please specify: initial investment amount, expected return rate, and time period.",
        "sections_used": [],
    }


def _generate_education_answer(query, context):
    """Generate educational answers for concept questions."""
    text = query.lower()
    
    if "roce" in text:
        return {
            "response": "ROCE stands for Return on Capital Employed. It measures how efficiently a company uses its capital to generate profits. ROCE = EBIT / Capital Employed.\n\nA higher ROCE indicates better capital efficiency. Generally:\n- ROCE > 20%: Excellent capital efficiency\n- ROCE 15-20%: Good capital efficiency\n- ROCE 10-15%: Acceptable capital efficiency\n- ROCE < 10%: Low capital efficiency\n\nFor context, what's the company's ROCE?",
            "sections_used": [],
        }
    
    if "p/e" in text or "pe ratio" in text:
        return {
            "response": "P/E Ratio (Price-to-Earnings) shows how much investors pay for each rupee of earnings.\n\nP/E = Market Price per Share / Earnings per Share (EPS)\n\nInterpretation:\n- Low P/E (< 15): May indicate undervaluation or weak growth expectations\n- Moderate P/E (15-30): Reasonable valuation for established companies\n- High P/E (> 30): May indicate high growth expectations or overvaluation\n\nA high P/E isn't bad if the company can grow earnings to justify it.",
            "sections_used": [],
        }
    
    if "debt" in text or "debt/equity" in text:
        return {
            "response": "Debt/Equity measures a company's financial leverage.\n\nD/E = Total Debt / Shareholders' Equity\n\nInterpretation:\n- D/E < 0.5: Very conservative, low debt\n- D/E 0.5-1: Moderate leverage\n- D/E 1-2: Higher leverage, monitor cash flow\n- D/E > 2: High leverage, higher financial risk\n\nCapital-intensive industries (like energy, manufacturing) naturally have higher D/E ratios.",
            "sections_used": [],
        }
    
    if "dividend" in text:
        return {
            "response": "Dividend Yield shows how much a company pays in dividends relative to its stock price.\n\nDividend Yield = Annual Dividend per Share / Price per Share\n\nInterpretation:\n- High yield (> 5%): May indicate strong cash returns but check sustainability\n- Moderate yield (2-5%): Typical for stable companies\n- Low yield (< 2%): Company may be reinvesting profits for growth\n\nA high yield isn't always better—check if the company can sustain dividends.",
            "sections_used": [],
        }
    
    return {
        "response": "I can explain financial concepts like ROCE, P/E ratio, debt/equity, and dividend yield. What specific concept would you like to understand?",
        "sections_used": [],
    }


def _generate_unsupported_answer(query, intent):
    """Generate answer for unsupported question types."""
    return {
        "response": "I can't reliably predict future share prices or make market calls. Stock price predictions involve significant uncertainty and depend on many factors including market sentiment, economic conditions, and company performance that are difficult to forecast accurately.\n\nHowever, I can help you understand:\n• The company's financial health and fundamentals\n• Analyst targets and consensus views\n• Historical price patterns and technical levels\n• Growth drivers and potential catalysts\n• Risks that could impact future performance\n\nWould you like me to analyze any of these aspects instead?",
        "sections_used": [],
    }


# New Intent Handlers

def _generate_historical_performance_answer(query, context):
    """Generate answer for historical performance questions with table format for years."""
    price_data = context.get("price_data", {})
    chart_metrics = context.get("chart_metrics", {})
    
    current = price_data.get("current")
    ohlcv = price_data.get("ohlcv", [])
    
    # Get returns from chart metrics (for standard periods)
    returns = chart_metrics.get("returns", {}) or {}
    
    # Parse time period from query
    text = query.lower()
    
    months = None
    years = None
    
    # Check for months
    months_match = re.search(r"(\d+)\s*months?", text)
    if months_match:
        months = int(months_match.group(1))
    # Check for years
    years_match = re.search(r"(\d+)\s*years?", text)
    if years_match:
        years = int(years_match.group(1))
    
    # If months specified, calculate dynamically and show simple response
    if months:
        if ohlcv and len(ohlcv) >= 2:
            days_back = months * 30  # Approximate
            if days_back < len(ohlcv):
                price_now = ohlcv[-1].get("close")
                price_then = ohlcv[-days_back].get("close")
                if price_now and price_then and price_then > 0:
                    return_pct = ((price_now - price_then) / price_then) * 100
                    company_name = _extract_company_name_from_query(query, context)
                    return {
                        "response": f"Over the last {months} months, {company_name} returned **{return_pct:.1f}%** ({'gain' if return_pct >= 0 else 'decline'}).",
                        "sections_used": ["price_data"]
                    }
    
    # If years specified, show table with year-by-year returns
    if years:
        if ohlcv and len(ohlcv) >= 2:
            current_price = ohlcv[-1].get("close")
            company_name = _extract_company_name_from_query(query, context)
            
            # Build year-by-year table using available data
            table_rows = []
            for y in range(1, years + 1):
                # Use available data - get price from (y) years ago or earliest available
                # For simplicity, use fixed intervals based on available data length
                if len(ohlcv) >= 365 * y:
                    days_back = y * 365
                else:
                    # Use available data - go back proportionally
                    days_back = int((y / years) * (len(ohlcv) - 1) * 365 / 365)
                    if days_back < 1:
                        days_back = 1
                
                if len(ohlcv) > days_back:
                    price_then = ohlcv[-days_back].get("close")
                    if price_then and price_then > 0:
                        return_pct = ((current_price - price_then) / price_then) * 100
                        arrow = "📈" if return_pct >= 0 else "📉"
                        table_rows.append(f"{y}Y ago|{return_pct:+.1f}%|{arrow}")
            
            if table_rows:
                # Build markdown table
                table_md = f"### {company_name} Historical Performance (Year-by-Year)\n\n| Period | Return |\n|--------|--------|\n"
                for row in table_rows:
                    parts = row.split("|")
                    table_md += f"| {parts[0]} | {parts[1]} {parts[2]} |\n"
                return {
                    "response": table_md,
                    "sections_used": ["price_data"]
                }
            
            # If table is empty, calculate total return from available period
            if len(ohlcv) >= 2:
                price_then = ohlcv[0].get("close")
                if price_then and price_then > 0:
                    total_return = ((current_price - price_then) / price_then) * 100
                    arrow = "📈" if total_return >= 0 else "📉"
                    return {
                        "response": f"### {company_name} Historical Performance\n\n| Period | Return |\n|--------|--------|\n| Last {len(ohlcv)} days | {total_return:+.1f}% {arrow} |\n",
                        "sections_used": ["price_data"]
                    }
    
    # Try to infer from available data (standard periods)
    for p in ["1M", "6M", "1Y", "5Y"]:
        if returns.get(p) is not None:
            return_pct = returns.get(p)
            period_label = p
            break
    
    if return_pct is not None and period_label:
        company_name = _extract_company_name_from_query(query, context)
        return {
            "response": f"Over the last {period_label}, {company_name} returned **{return_pct:.1f}%** ({'gain' if return_pct >= 0 else 'decline'}).",
            "sections_used": ["price_data", "chart_metrics"]
        }
    
    return {
        "response": "I don't have sufficient historical price data to calculate the return for the specified period. Please ask about a different time frame (e.g., 'last 6 months', 'past year').",
        "sections_used": []
    }


def _extract_company_name_from_query(query, context):
    """Extract company name from query or memory."""
    # Try to get from entities in context
    if context:
        info = context.get("company_info", {})
        if info:
            return info.get("company_name", info.get("name", "the company"))
    
    # Try to extract from query - simple substring match
    text = query.lower()
    from agent_1.tools.nifty50 import NIFTY50
    
    for ticker, _ in NIFTY50:  # NIFTY50 format is (ticker, sector)
        ticker_name = ticker.split(".")[0]  # Get TCS from TCS.NS
        ticker_name_lower = ticker_name.lower()
        
        # Simple substring check - if ticker name appears in query
        if ticker_name_lower in text:
            return ticker_name
    
    # Default fallback
    return "the company"


def _generate_sector_ranking_answer(query, memory):
    """Generate answer for sector ranking questions (e.g., which Energy company performed best over 5 years?)."""
    from agent_1.tools.nifty50 import NIFTY50
    
    sector_keywords = ["energy", "banking", "it", "financial", "consumer", "pharma", "auto", "metal", "infra"]
    text = query.lower()
    
    # Extract sector
    sector = None
    for kw in sector_keywords:
        if kw in text:
            sector = kw.title()
            break
    
    if not sector:
        # Try to get sector from query
        sector_match = re.search(r"(\w+)\s+sector", text)
        if sector_match:
            sector = sector_match.group(1).title()
    
    if not sector:
        return {
            "response": "I need to know which sector you want to analyze. Please specify (e.g., Energy, Banking, IT).",
            "sections_used": []
        }
    
    # Find companies in this sector
    sector_companies = [(t, s) for t, s in NIFTY50 if s.lower() == sector.lower()]
    
    if not sector_companies:
        return {
            "response": f"No NIFTY50 companies found in the {sector} sector.",
            "sections_used": []
        }
    
    # For each company, get 5Y return from chart metrics
    company_returns = []
    for ticker, _ in sector_companies:
        try:
            company_memory = memory  # In a real scenario, we'd fetch each company's data
            chart = (company_memory or {}).get("chart_metrics", {})
            returns = chart.get("returns", {}) or {}
            
            five_y_return = returns.get("5Y") or returns.get("3Y") or returns.get("1Y")
            if five_y_return is not None:
                company_returns.append({
                    "ticker": ticker,
                    "name": ticker.split(".")[0],
                    "return": five_y_return
                })
        except Exception:
            continue
    
    if not company_returns:
        return {
            "response": f"I don't have return data for any companies in the {sector} sector.",
            "sections_used": []
        }
    
    # Sort by return
    company_returns.sort(key=lambda x: x["return"], reverse=True)
    
    # Generate response
    top_performer = company_returns[0]
    top_return = top_performer["return"]
    
    response = f"In the {sector} sector, **{top_performer['name']}** has delivered the strongest performance with a return of **{top_return:.1f}%** over the available period."
    
    if len(company_returns) > 1:
        response += f" The sector average return is {sum(c['return'] for c in company_returns) / len(company_returns):.1f}%."
    
    return {
        "response": response,
        "sections_used": ["chart_metrics"]
    }


def _generate_investment_simulator_answer(query, context):
    """Generate answer for investment simulator questions (e.g., if I invested ₹2 lakh in Reliance 5 years ago?)."""
    price_data = context.get("price_data", {})
    
    current = price_data.get("current")
    price_history = price_data.get("history", [])
    
    # Parse investment amount
    text = query.lower()
    amount_match = re.search(r"(₹?\s*[\d,.]+)\s*(lakh|crore)?", text, re.IGNORECASE)
    
    if not amount_match:
        return {
            "response": "I need to know the investment amount. Please specify (e.g., ₹2 lakh, ₹50,000).",
            "sections_used": []
        }
    
    amt_str = amount_match.group(1).replace("₹", "").replace(",", "").strip()
    amount = float(amt_str)
    unit = (amount_match.group(2) or "").lower()
    amount *= {"crore": 1e7, "lakh": 1e5}.get(unit, 1)
    
    # Parse time period
    years_match = re.search(r"(\d+)\s*years?", text)
    if not years_match:
        return {
            "response": "I need to know how many years ago you made the investment.",
            "sections_used": []
        }
    
    years = int(years_match.group(1))
    
    # Get historical price
    if price_history and len(price_history) >= 2:
        # Get price from years ago (approximate: look at oldest price in history)
        oldest_price = price_history[0].get("close")
        if oldest_price and oldest_price > 0 and current:
            # Calculate shares bought
            shares = amount / oldest_price
            current_value = shares * current
            profit = current_value - amount
            return_pct = (profit / amount) * 100
            
            return {
                "response": f"An investment of ₹{amount:,.0f} made {years} years ago would now be worth ₹{current_value:,.0f}, generating a profit of ₹{profit:,.0f} (**{return_pct:.0f}%**).",
                "sections_used": ["price_data"]
            }
    
    return {
        "response": "I don't have sufficient historical price data to calculate the investment return. Please check the price chart for more details.",
        "sections_used": []
    }

# Main Entry Point

def run_agent4(query, agent1_output, agent2_output=None, agent3_output=None):
    """Main entry point for Agent 4 - Four-stage reasoning process."""
    from company_memory import build_company_memory
    
    # Build memory from all agents
    memory = build_company_memory(agent1_output, agent2_output, agent3_output)
    
    # STAGE 1: Classify the question
    plan = classify_question(query, memory)
    
    # STAGE 2: Retrieve relevant context
    context = retrieve_context(memory, plan["needs"])
    
    # STAGE 3 & 4: Generate answer with reasoning
    return answer_with_reasoning(query, memory, context, plan)


def explain_financial_pattern(memory):
    """Generate context-aware financial pattern analysis explanation."""
    info = (memory or {}).get("company_info", {}) or {}
    financial = (memory or {}).get("financial_metrics", {}) or {}
    peer = (memory or {}).get("peer_comparison", {}) or {}
    sector = info.get("sector", "") or peer.get("sector", "")
    anomaly = (memory or {}).get("anomaly_detection", {}) or {}
    model = anomaly.get("model_assessment", {}) or {}
    red_flags = anomaly.get("red_flags", []) or []
    
    roce = financial.get("roce")
    debt_to_equity = financial.get("debt_to_equity")
    current_ratio = financial.get("current_ratio")
    
    anomaly_score = model.get("anomaly_score")
    prediction = model.get("prediction")
    is_anomaly = prediction == -1 or (anomaly_score is not None and anomaly_score >= 0.15)
    
    explanation_parts = []
    
    company_name = info.get("name", "this company")
    summary = info.get("summary", "") or ""
    sector_lower = sector.lower() if sector else ""
    summary_lower = summary.lower()
    
    if "bank" in sector_lower or "financial" in sector_lower:
        company_type = "banking/financial institution"
    elif any(k in summary_lower for k in ["conglomerate", "diversified", "multiple"]):
        company_type = "diversified conglomerate"
    elif any(k in summary_lower for k in ["capital", "infrastructure", "manufacturing", "energy", "refining"]):
        company_type = "capital-intensive business"
    elif any(k in summary_lower for k in ["services", "technology", "it", "consulting"]):
        company_type = "service-oriented business"
    else:
        company_type = "sector player"
    
    explanation_parts.append(f"{company_name} operates as a {company_type} in the {sector} sector.")
    
    if is_anomaly:
        if "bank" in sector_lower or "financial" in sector_lower:
            explanation_parts.append("Banks naturally operate with balance sheets that look very different from companies in other industries. Its lending activities, capital requirements, and interest income create financial ratios that differ from non-banking businesses. Within the banking sector, credit quality and capital adequacy become more important than manufacturing-style profitability metrics.")
        elif "conglomerate" in summary_lower or "diversified" in summary_lower:
            explanation_parts.append("It operates across multiple business lines which creates a financial profile that differs from focused peers. Investors should evaluate whether future growth from newer businesses offsets the capital required to support them.")
        elif any(k in summary_lower for k in ["capital", "infrastructure", "manufacturing", "energy", "refining"]):
            explanation_parts.append("Capital-intensive businesses require substantial investments which naturally leads to higher leverage and lower short-term returns. These companies should be evaluated based on long-term cash flow generation rather than current ratios alone.")
        elif any(k in summary_lower for k in ["services", "technology", "it", "consulting"]):
            explanation_parts.append("Service companies typically have different financial characteristics than manufacturing businesses. Their valuation should focus on growth metrics, margins, and cash conversion rather than traditional capital intensity ratios.")
        else:
            explanation_parts.append(f"The company's financial profile differs from many sector peers due to its scale, business model, or operational structure. This is not necessarily negative—it reflects the unique characteristics of {company_name.lower()}.")
        
        differences = []
        if debt_to_equity is not None and isinstance(debt_to_equity, (int, float)) and debt_to_equity > 2:
            differences.append("higher leverage")
        if roce is not None and isinstance(roce, (int, float)) and roce < 15:
            differences.append("lower returns on capital")
        if current_ratio is not None and isinstance(current_ratio, (int, float)) and current_ratio < 1.5:
            differences.append("moderate liquidity")
        
        if differences:
            explanation_parts.append(f"Key differences include: {', '.join(differences)} compared to typical sector firms.")
        
        if any("strong" in rf.get("explanation", "").lower() for rf in red_flags):
            conclusion = "The detected pattern reflects the company's unique characteristics rather than a financial weakness. This signal should be evaluated alongside growth prospects and market position."
        elif any("cyclical" in rf.get("explanation", "").lower() for rf in red_flags):
            conclusion = "The pattern reflects normal cyclicality in the industry. Focus should be on profitability and cash generation across business cycles rather than interpreting the pattern as a permanent issue."
        else:
            conclusion = "This is a pattern detection signal, not an investment recommendation. Large, diversified, or capital-intensive companies naturally appear different from their peers."
        
        return {
            "status": "unusual",
            "headline": "🔴 Unusual Financial Pattern Detected" if not any("strong" in rf.get("explanation", "").lower() for rf in red_flags) else "🟢 Financial profile stands out positively",
            "why_noticed": explanation_parts,
            "what_this_means": conclusion
        }
    else:
        return {
            "status": "normal",
            "headline": "🟢 No unusual pattern detected",
            "why_noticed": [f"{company_name}'s financial profile is consistent with sector peers."],
            "what_this_means": "The company's financial characteristics are typical for its sector, suggesting standard operations for the industry."
        }


def generate_suggested_questions(memory, company_name):
    """Generate personalized suggested questions based on company data."""
    info = (memory or {}).get("company_info", {}) or {}
    financial = (memory or {}).get("financial_metrics", {}) or {}
    peer = (memory or {}).get("peer_comparison", {}) or {}
    chart = (memory or {}).get("chart_metrics", {}) or {}
    analyst = (memory or {}).get("analyst_data", {}) or {}
    news = (memory or {}).get("news_articles", []) or []
    risks = (memory or {}).get("risks", []) or []
    opportunities = (memory or {}).get("opportunities", []) or []
    
    roce = financial.get("roce")
    debt_to_equity = financial.get("debt_to_equity")
    current_ratio = financial.get("current_ratio")
    operating_margin = financial.get("operating_margin")
    revenue_growth = info.get("revenue_growth")
    pe_ratio = info.get("trailingPE") or info.get("pe_ratio")
    market_cap = info.get("market_cap")
    sector = info.get("sector", "sector")
    
    suggested = []
    
    if roce is not None and 10 <= roce < 20:
        suggested.append(f"Why is {company_name}'s ROCE only {roce:.1f}% compared to stronger peers in the {sector} sector?")
    elif roce is not None and roce < 10:
        suggested.append(f"Why is {company_name}'s ROCE below {roce:.1f}%? Does this indicate competitive challenges?")
    
    if debt_to_equity is not None and isinstance(debt_to_equity, (int, float)) and debt_to_equity > 1.5:
        suggested.append(f"Is {company_name}'s debt level of {debt_to_equity:.1f}x a concern for investors?")
    
    if pe_ratio is not None and pe_ratio > 25 and (roce is None or roce < 15):
        suggested.append(f"Why is {company_name} valued at a high P/E of {pe_ratio:.1f} despite moderate returns?")
    
    if opportunities:
        suggested.append(f"What are {company_name}'s biggest growth opportunities over the next 5 years?")
    
    if peer.get("peers"):
        peer_list = peer.get("peers", [])
        if len(peer_list) >= 2:
            suggested.append(f"How does {company_name} compare to its closest competitor, {peer_list[0] if isinstance(peer_list[0], str) else peer_list[0].get('ticker', 'a peer')}?")
    
    if risks:
        risk_text = risks[0] if risks else ""
        if "debt" in risk_text.lower() or "leverage" in risk_text.lower():
            suggested.append(f"How does {company_name} manage its debt obligations?")
        elif "margin" in risk_text.lower() or "profitability" in risk_text.lower():
            suggested.append(f"What is {company_name}'s strategy to improve profitability?")
        else:
            suggested.append(f"What are the main risks that could affect {company_name}'s performance?")
    
    positive_news = [n for n in news[:3] if any(k in ((n.get("headline") or "") + (n.get("summary") or "")).lower() for k in ["upside", "growth", "expansion", "launch", "strong"])]
    if positive_news:
        suggested.append(f"What catalysts could drive {company_name}'s stock price higher?")
    
    if chart.get("trend") == "down":
        suggested.append(f"Why has {company_name}'s stock underperformed recently?")
    elif chart.get("trend") == "up":
        suggested.append(f"What's driving {company_name}'s positive momentum?")
    
    target_price = analyst.get("target_mean_price") or analyst.get("targetMeanPrice")
    if target_price:
        current = (memory.get("price_data") or {}).get("current")
        if current and target_price:
            upside = ((target_price - current) / current) * 100
            suggested.append(f"What does it take for {company_name} to reach the analyst target of ₹{target_price:,.0f}?")
    
    if len(suggested) < 3:
        if revenue_growth is not None:
            suggested.append(f"How sustainable is {company_name}'s revenue growth rate of {revenue_growth:.1f}%?")
        else:
            suggested.append(f"What makes {company_name} a compelling investment in the {sector} sector?")
    
    generic_questions = [
        f"How does {company_name}'s financial health compare to other companies in the {sector} sector?",
        f"Is {company_name} a good long-term investment based on its fundamentals?",
        f"What are the key factors that could impact {company_name}'s stock price in the next year?",
    ]
    
    for q in generic_questions:
        if len(suggested) >= 5:
            break
        if q not in suggested:
            suggested.append(q)
    
    return suggested[:5]


def explain_market(memory):
    """Return a small market-mood summary for the UI."""
    news = (memory or {}).get("news_articles", []) or []
    risks = (memory or {}).get("risks", []) or []
    opportunities = (memory or {}).get("opportunities", []) or []
    analyst = (memory or {}).get("analyst_data", {}) or {}

    bullish = len(opportunities) + sum(
        1 for item in news[:5]
        if any(k in ((item.get("headline") or item.get("title") or "") + " " + (item.get("summary") or "")).lower()
               for k in ["upside", "growth", "expansion", "launch", "strong", "beat"])
    )
    bearish = len(risks) + sum(
        1 for item in news[:5]
        if any(k in ((item.get("headline") or item.get("title") or "") + " " + (item.get("summary") or "")).lower()
               for k in ["fall", "slip", "decline", "weak", "pressure", "risk"])
    )

    if bullish > bearish:
        mood = "👍 Positive"
        label = "Positive"
    elif bearish > bullish:
        mood = "👎 Negative"
        label = "Negative"
    else:
        mood = "🟡 Mixed"
        label = "Mixed"

    rec = analyst.get("recommendation_key") or analyst.get("recommendationKey")
    parts = []
    if rec:
        parts.append(f"Analyst view: {str(rec).title()}")
    if opportunities:
        parts.append(opportunities[0])
    if risks:
        parts.append(risks[0])

    return {
        "mood": mood,
        "label": label,
        "consensus": " ".join(parts) if parts else "The market view is mixed and should be read alongside the fundamentals.",
        "explanation": " ".join(parts) if parts else "No strong single signal dominated the available data.",
    }


def interpret_market_intelligence(memory):
    """Alias used by the frontend for a more structured market signal."""
    market = explain_market(memory)
    return {
        "label": market["label"],
        "confidence": market["confidence"],
        "explanation": market["explanation"],
    }


def explain_chart(memory):
    """Return a compact chart summary for the UI."""
    chart = (memory or {}).get("chart_metrics", {}) or {}
    return {
        "trend": chart.get("trend", "sideways"),
        "returns": chart.get("returns", {}) or {},
        "volatility": chart.get("volatility"),
        "distance_from_52w_high": chart.get("distance_from_52w_high"),
        "distance_from_52w_low": chart.get("distance_from_52w_low"),
    }


def price_story_summary(memory):
    """Generate one-line price story."""
    chart = memory.get("chart_metrics", {})
    price = memory.get("price_data", {})
    current = price.get("current")
    high_52w = price.get("high_52w")
    trend = chart.get("trend", "sideways")
    
    parts = []
    if isinstance(current, (int, float)) and isinstance(high_52w, (int, float)) and current == current and high_52w == high_52w and high_52w != 0:
        below = ((high_52w - current) / high_52w) * 100
        parts.append(f"₹{current:,.2f} is {below:.1f}% below 52-week high")
    else:
        parts.append("Current price context is limited, so the chart should be read cautiously")
    
    trend_text = {"up": "Momentum is constructive", "down": "Momentum is weak"}.get(trend, "Price consolidating")
    parts.append(trend_text)
    
    return ". ".join(parts) + "."


def top_news_summary(memory):
    """Generate top news summary for the UI."""
    articles = (memory or {}).get("news_articles", []) or []
    if not articles:
        return []
    
    summary = []
    for art in articles[:3]:
        headline = art.get("headline", "")
        sentiment = art.get("sentiment", "neutral")
        if headline:
            emoji = {"positive": "✅", "negative": "⚠", "neutral": "•"}.get(sentiment, "•")
            summary.append(f"{emoji} {headline[:80]}")
    return summary


def explain_market(memory):
    """Interpret overall market sentiment."""
    market = (memory or {}).get("market_intelligence", {}) or {}
    analyst = (memory or {}).get("analyst_data", {}) or {}
    news = (memory or {}).get("news_articles", []) or []
    chart = (memory or {}).get("chart_metrics", {}) or {}
    
    bullish = 0
    bearish = 0
    
    rec = analyst.get("recommendation")
    if rec and rec.lower() in ("buy", "strong_buy", "outperform"):
        bullish += 2
    elif rec and rec.lower() in ("sell", "underperform"):
        bearish += 2
    
    for art in news[:5]:
        sent = (art.get("sentiment") or "neutral").lower()
        if sent == "positive":
            bullish += 1
        elif sent == "negative":
            bearish += 1
    
    trend = chart.get("trend")
    if trend == "up":
        bullish += 1
    elif trend == "down":
        bearish += 1
    
    if bullish > bearish + 1:
        label = "Positive"
    elif bearish > bullish + 1:
        label = "Negative"
    elif abs(bullish - bearish) <= 1:
        label = "Mixed"
    else:
        label = "Cautiously Positive"
    
    parts = []
    if rec:
        parts.append(f"Analyst consensus is {rec}")
    if chart.get("trend"):
        parts.append(f"Price trend is {chart['trend']}")
    
    return {
        "mood": "constructive" if bullish > bearish else "cautious",
        "label": label,
        "confidence": min(0.9, 0.5 + abs(bullish - bearish) * 0.1),
        "consensus": " ".join(parts) if parts else "The market view is mixed.",
        "explanation": " ".join(parts) if parts else "No strong single signal.",
    }


def explain_business_snapshot(memory):
    """Generate business snapshot explanation."""
    info = (memory or {}).get("company_info", {}) or {}
    metrics = (memory or {}).get("financial_metrics", {}) or {}
    sector = info.get("sector", "")
    roce = metrics.get("roce")
    
    return {
        "sector": sector,
        "roce": roce,
        "summary": f"{info.get('name', 'This company')} operates in the {sector} sector" + 
                   (f" with ROCE of {roce}%" if roce else "") + ".",
    }


def answer_business_description(company_name, memory):
    """Answer what the company does."""
    info = (memory or {}).get("company_info", {}) or {}
    summary = info.get("summary", "") or info.get("business_model", "")
    peers = info.get("peers", [])
    
    prompt = f"""What does {company_name} do?
    
Company Summary: {summary[:500] if summary else 'No description available'}

Peers: {', '.join(peers[:3]) if peers else 'Not available'}

Answer in 2-3 sentences what this company does."""
    
    llm = ChatGroq(model=os.getenv("GROQ_MODEL", "mixtral-8x7b-32768"), temperature=0)
    try:
        response = (ChatPromptTemplate.from_template(prompt) | llm).invoke({}).content
        return {"response": response, "sections_used": ["company_info"]}
    except Exception:
        return {"response": summary[:200] if summary else "Company information not available.", "sections_used": []}


def build_investment_thesis(memory, years):
    """Build investment thesis for N years."""
    info = (memory or {}).get("company_info", {}) or {}
    metrics = (memory or {}).get("financial_metrics", {}) or {}
    chart = (memory or {}).get("chart_metrics", {}) or {}
    opportunities = (memory or {}).get("opportunities", []) or []
    risks = (memory or {}).get("risks", []) or []
    
    roce = metrics.get("roce")
    trend = chart.get("trend")
    
    thesis = {
        "investor_fit": ["long-term compounding"] if roce and roce >= 15 else ["value", "income"],
        "holding_period": f"{years} years",
        "summary": "Investment suitability depends on financial health and market conditions.",
    }
    
    if roce and roce >= 15:
        thesis["summary"] = f"Strong ROCE of {roce}% supports long-term compounding potential."
    elif roce and roce < 10:
        thesis["summary"] = "Lower ROCE suggests caution for long-term holding."
    
    return thesis


def price_story_summary(memory):
    """Generate one-line price story."""
    chart = memory.get("chart_metrics", {})
    price = memory.get("price_data", {})
    current = price.get("current")
    high_52w = price.get("high_52w")
    trend = chart.get("trend", "sideways")
    
    parts = []
    if isinstance(current, (int, float)) and isinstance(high_52w, (int, float)) and high_52w != 0:
        below = ((high_52w - current) / high_52w) * 100
        parts.append(f"₹{current:,.2f} is {below:.1f}% below 52-week high")
    else:
        parts.append("Current price context is limited")
    
    trend_text = {"up": "Momentum is constructive", "down": "Momentum is weak"}.get(trend, "Price consolidating")
    parts.append(trend_text)
    
    return ". ".join(parts) + "."


def explain_forecast(memory, current_price, target_price, expected_return, analyst_rating="Hold"):
    """Explain the 12M price forecast: LLM-generated when available, deterministic fallback otherwise.

    Returns dict: {summary, drivers, assumptions, risks_to_forecast, confidence, basis}
    """
    info = (memory or {}).get("company_info", {}) or {}
    financial = (memory or {}).get("financial_metrics", {}) or {}
    peer = (memory or {}).get("peer_comparison", {}) or {}
    analyst = (memory or {}).get("analyst_data", {}) or {}
    mood = ((memory or {}).get("dashboard", {}) or {}).get("market_mood", {}) or {}
    risks = (memory or {}).get("risks", []) or []
    opportunities = (memory or {}).get("opportunities", []) or []

    company = info.get("name", "this company")
    sector = info.get("sector") or peer.get("sector") or ""
    metrics = peer.get("metrics", {}) or {}
    pe = metrics.get("pe_ratio", metrics.get("P/E", {})) or {}
    analyst_target = analyst.get("target_mean_price") or analyst.get("price_target")
    analyst_count = analyst.get("number_of_analysts") or analyst.get("analysts_count")

    def _fmt(v, suffix=""):
        return f"{v}{suffix}" if isinstance(v, (int, float)) else "N/A"

    data_digest = {
        "company": company,
        "sector": sector,
        "current_price": current_price,
        "model_target": target_price,
        "expected_return_pct": round(expected_return, 1) if isinstance(expected_return, (int, float)) else None,
        "analyst_rating": analyst_rating,
        "analyst_target": analyst_target,
        "analyst_count": analyst_count,
        "pe_ratio": pe.get("company") if isinstance(pe, dict) else None,
        "pe_sector_average": pe.get("sector_average") if isinstance(pe, dict) else None,
        "pe_percentile": pe.get("percentile") if isinstance(pe, dict) else None,
        "roe": financial.get("roe") or financial.get("return_on_equity"),
        "roce": financial.get("roce"),
        "debt_to_equity": financial.get("debt_to_equity"),
        "profit_margin": financial.get("net_margin") or financial.get("profit_margin"),
        "revenue_growth": financial.get("revenue_growth"),
        "market_sentiment": mood.get("overall_sentiment"),
        "top_opportunities": [str(o.get("explanation", o) if isinstance(o, dict) else o) for o in opportunities[:3]],
        "top_risks": [str(r.get("explanation", r) if isinstance(r, dict) else r) for r in risks[:3]],
    }

    # ── LLM explanation (best effort) ──
    try:
        prompt = f"""You are an equity research analyst. Explain the 12-month price forecast below to a retail investor.
Be specific: reference the actual numbers provided. Explain WHY the target is what it is (valuation, profitability, analyst views, sentiment) and what could prove it wrong.
Return ONLY valid JSON with keys: summary (2-3 sentences), drivers (3-4 short bullets), assumptions (2-3 bullets), risks_to_forecast (2-3 bullets), confidence ("Low"|"Moderate"|"High").

Forecast data:
{json.dumps(data_digest, indent=2)}"""

        # max_tokens headroom: reasoning models spend tokens on the <think> block
        llm = ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"), temperature=0, max_tokens=4096)
        # Plain-string invoke: a prompt template would treat the JSON braces as variables
        response = llm.invoke(prompt).content.strip()
        # Strip reasoning-model <think> blocks and code fences
        if "<think>" in response:
            response = response.split("</think>")[-1].strip()
        if response.startswith("```"):
            response = response.split("```")[1].lstrip("json").strip()
        # Parse the first JSON object, ignoring any prose before/after it
        start = response.find("{")
        if start == -1:
            raise ValueError("no JSON object in LLM response")
        parsed, _ = json.JSONDecoder().raw_decode(response[start:])
        if isinstance(parsed, dict) and parsed.get("summary"):
            parsed.setdefault("drivers", [])
            parsed.setdefault("assumptions", [])
            parsed.setdefault("risks_to_forecast", [])
            parsed.setdefault("confidence", "Moderate")
            parsed["basis"] = "Fundamental health analysis + analyst consensus + LLM synthesis"
            return parsed
    except Exception as e:
        print(f"Forecast explanation LLM failed, using fallback: {e}")

    # ── Deterministic fallback ──
    drivers, assumptions = [], []
    if isinstance(expected_return, (int, float)):
        drivers.append(f"Target implies {_fmt(round(expected_return, 1), '%')} {'upside' if expected_return >= 0 else 'downside'} from the current price of ₹{_fmt(current_price)}.")
    if analyst_target:
        drivers.append(f"Aligned with analyst consensus target of ₹{_fmt(round(analyst_target, 2))}" + (f" from {analyst_count} analysts." if analyst_count else "."))
    if isinstance(pe, dict) and pe.get("company") and pe.get("sector_average"):
        pos = "in line with" if abs(pe["company"] - pe["sector_average"]) / pe["sector_average"] < 0.2 else ("below" if pe["company"] < pe["sector_average"] else "above")
        drivers.append(f"Trailing P/E of {round(pe['company'], 1)}x is {pos} the sector average of {round(pe['sector_average'], 1)}x.")
    if financial.get("roce") is not None:
        drivers.append(f"ROCE of {_fmt(round(financial['roce'], 1), '%')} indicates capital efficiency.")
    assumptions.append(f"Analyst consensus remains '{analyst_rating}' over the next 12 months.")
    if mood.get("overall_sentiment"):
        assumptions.append(f"Market sentiment stays {str(mood['overall_sentiment']).lower()}.")
    risks = [str(r.get("explanation", r) if isinstance(r, dict) else r) for r in risks[:3]] or ["Sector or macro headwinds could delay re-rating."]

    return {
        "summary": f"The 12M target of ₹{_fmt(round(target_price, 2) if target_price else 'N/A')} for {company} is derived from fundamental health analysis cross-checked with analyst consensus.",
        "drivers": drivers or ["Fundamental health score and analyst targets."],
        "assumptions": assumptions,
        "risks_to_forecast": risks,
        "confidence": "Moderate" if analyst_rating in ("Hold",) else "Low",
        "basis": "Fundamental health analysis + analyst consensus (deterministic)",
    }
