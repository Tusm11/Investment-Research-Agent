"""Agent 4 - General-purpose financial reasoning engine (compact)."""

from __future__ import annotations
import json, ast, operator as op, os, re
from math import prod
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from agent_1.data_fetcher import fetch_all_data
from agent_1.tools.nifty50 import NIFTY50
from company_memory import build_company_memory

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agent_1", ".env"))
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")

try:
    from agent_1.data_fetcher import fetch_company_website_context
except:
    fetch_company_website_context = None

NIFTY50_MAP = {t.split(".")[0].upper(): t for t, _ in NIFTY50}
NAME_TO_TICKER = {
    "RELIANCE": "RELIANCE.NS", "INFOSYS": "INFY.NS", "INFY": "INFY.NS", "TCS": "TCS.NS",
    "HDFCBANK": "HDFCBANK.NS", "ICICIBANK": "ICICIBANK.NS", "KOTAKBANK": "KOTAKBANK.NS",
    "SBIN": "SBIN.NS", "BHARTIARTL": "BHARTIARTL.NS", "LT": "LT.NS", "ITC": "ITC.NS",
    "WIPRO": "WIPRO.NS", "HCLTECH": "HCLTECH.NS", "TECHM": "TECHM.NS", "TITAN": "TITAN.NS",
    "MARUTI": "MARUTI.NS", "HINDUNILVR": "HINDUNILVR.NS", "DMART": "DMART.NS", "ONGC": "ONGC.NS",
}

CALC_SAFE_OPS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.USub: op.neg, ast.UAdd: op.pos,
}

_planner_llm = None

def run_agent4(query, agent1_output, agent2_output=None, agent3_output=None):
    """Main entry point for Agent 4."""
    memory = build_company_memory(agent1_output, agent2_output, agent3_output)
    plan = plan_question(query, memory)
    context = retrieve_context(memory, plan["required_sections"])
    return answer_with_reasoning(query, memory, context, plan)

def _get_planner_llm():
    global _planner_llm
    if _planner_llm is None:
        _planner_llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    return _planner_llm

def _coerce_plan(data):
    if not isinstance(data, dict):
        return None
    sections = data.get("required_sections") or data.get("sections") or []
    if isinstance(sections, str):
        sections = [sections]
    time_horizon = data.get("time_horizon")
    if isinstance(time_horizon, str):
        time_horizon = time_horizon.strip().lower()
        time_horizon = None if time_horizon in {"", "null", "none"} else time_horizon
    try:
        time_horizon = int(time_horizon) if time_horizon else None
    except:
        time_horizon = None
    return {
        "required_sections": [str(s) for s in sections if s],
        "need_calculator": bool(data.get("need_calculator", False)),
        "need_general_knowledge": bool(data.get("need_general_knowledge", False)),
        "need_comparison": bool(data.get("need_comparison", False)),
        "time_horizon": time_horizon,
    }

def _fallback_plan(query):
    return {
        "required_sections": route_context(query),
        "need_calculator": False,
        "need_general_knowledge": False,
        "need_comparison": False,
        "time_horizon": _extract_time_horizon((query or "").lower()),
    }

def _extract_time_horizon(text):
    m = re.search(r"(\d+)\s*(?:year|yr|yrs|years)", text)
    if m:
        return int(m.group(1))
    return 5 if "5 year" in text or "five year" in text else None

def _extract_entities(query):
    text = (query or "").upper()
    matches = []
    for alias, ticker in {**NAME_TO_TICKER, **NIFTY50_MAP}.items():
        if re.search(rf"\b{re.escape(alias)}\b", text) and ticker not in matches:
            matches.append(ticker)
    return matches

def _safe_eval(expr):
    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in CALC_SAFE_OPS:
            return CALC_SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in CALC_SAFE_OPS:
            return CALC_SAFE_OPS[type(n.op)](_eval(n.operand))
        raise ValueError("Unsupported expression")
    return _eval(ast.parse(expr, mode="eval"))

def _parse_money_amount(text):
    m = re.search(r"([\d.]+)\s*(lakh|crore|k|m)?", text, re.IGNORECASE)
    if not m:
        return None
    amount = float(m.group(1))
    unit = (m.group(2) or "").lower()
    return amount * {"crore": 1e7, "lakh": 1e5, "k": 1e3, "m": 1e6}.get(unit, 1)

def plan_question(query, memory=None):
    """Use an LLM to plan which data/tools are needed."""
    system_prompt = (
        "You are Agent 4 Planner for a financial reasoning assistant. "
        "Convert the user's question into compact JSON only. "
        "Return keys: required_sections, need_calculator, need_general_knowledge, need_comparison, time_horizon. "
        "required_sections must be a list chosen from: company_info, financial_metrics, financial_facts, peer_comparison, "
        "price_data, chart_metrics, risk_metrics, news_articles, events, analyst_data, market_facts, market_intelligence, "
        "risks, opportunities. Use the smallest useful set. "
        "need_calculator: true for CAGR, future value, return %, P/E, PEG, upside, position sizing math. "
        "need_general_knowledge: true for conceptual questions like 'What is ROCE?'. "
        "need_comparison: true for comparing two companies or peers. "
        "time_horizon: integer for years mentioned, otherwise null."
    )
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{question}")])
    
    try:
        raw = (prompt | _get_planner_llm()).invoke({"question": query.strip()}).content.strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.IGNORECASE | re.MULTILINE).strip()
        plan = _coerce_plan(json.loads(raw))
        if plan and plan["required_sections"]:
            return plan
        if plan:
            plan["required_sections"] = ["company_info"]
            return plan
    except:
        pass
    return _fallback_plan(query)

def calculator_tool(query, memory):
    """Calculator for financial math: future value, returns, ratios, etc."""
    text = (query or "").lower()
    current = memory.get("price_data", {}).get("current")
    amount = _parse_money_amount(text) if any(u in text for u in ["lakh", "crore", "k", "m", "₹", "rs", "rupees"]) else None
    
    fv = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(?:annual(?:ly)?|per year)?\s*(?:for\s*)?(\d+)\s*years?", text)
    if ("invest" in text or "future value" in text) and fv:
        amount = amount or 100000.0
        rate = float(fv.group(1)) / 100.0
        years = int(fv.group(2))
        value = amount * ((1 + rate) ** years)
        return f"Future value: ₹{value:,.2f} (from ₹{amount:,.2f} at {fv.group(1)}% for {years}y)"
    
    if "return" in text and current is not None:
        m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        if m and "for" in text and "years" in text:
            years_m = re.search(r"(\d+)\s*years?", text)
            if years_m:
                rate = float(m.group(1)) / 100.0
                years = int(years_m.group(1))
                amount = amount or 100000.0
                value = amount * ((1 + rate) ** years)
                return f"Future value: ₹{value:,.2f}"
    
    if "cagr" in text or "compound annual" in text:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:to|→|-|years?)", text)
        if m and current:
            initial = _parse_money_amount(text.split("to")[0]) if "to" in text else None
            if initial:
                years = _extract_time_horizon(text)
                if years:
                    cagr = ((current / initial) ** (1 / years) - 1) * 100
                    return f"CAGR: {cagr:.2f}%"
    
    if "pe" in text and current:
        eps_m = re.search(r"eps\s*[=:]\s*([\d.]+)", text)
        if eps_m:
            eps = float(eps_m.group(1))
            pe = current / eps if eps else None
            return f"P/E Ratio: {pe:.2f}" if pe else "Invalid EPS"
    
    if "peg" in text and current:
        eps_m = re.search(r"eps\s*[=:]\s*([\d.]+)", text)
        growth_m = re.search(r"growth\s*[=:]\s*([\d.]+)", text)
        if eps_m and growth_m:
            eps, growth = float(eps_m.group(1)), float(growth_m.group(1))
            pe = current / eps if eps else None
            peg = pe / growth if pe and growth else None
            return f"PEG: {peg:.2f}" if peg else "Invalid inputs"
    
    if "upside" in text and current:
        target_m = re.search(r"target\s*[=:]\s*([\d.]+)", text)
        if target_m:
            target = float(target_m.group(1))
            upside = ((target - current) / current) * 100
            return f"Upside: {upside:.2f}% (to ₹{target:,.2f})"
    
    return None

def route_context(query):
    """Route query to required memory sections."""
    text = (query or "").lower()
    sections = []
    
    kw_map = {
        ("pe", "eps", "price to book", "div", "margin", "roe", "roce", "asset"): ["financial_metrics"],
        ("price", "chart", "trend", "volatility", "52w", "support", "resistance"): ["price_data", "chart_metrics"],
        ("news", "headline", "event", "announcement"): ["news_articles", "events"],
        ("sentiment", "analyst", "bull", "bear", "upside"): ["analyst_data", "market_intelligence"],
        ("peer", "competitor", "compare", "vs", "versus"): ["peer_comparison"],
        ("risk", "anomaly", "red flag", "concern"): ["risk_metrics"],
        ("opportunity", "catalyst", "upside"): ["opportunities"],
    }
    
    for keywords, section_list in kw_map.items():
        if any(kw in text for kw in keywords):
            sections.extend(section_list)
    
    if not sections:
        sections = ["company_info", "financial_metrics"]
    
    return list(set(sections))

def retrieve_context(memory, required_sections):
    """Retrieve context from memory for specified sections."""
    context = {}
    for section in set(required_sections):
        if section in memory:
            context[section] = memory[section]
    return context

def answer_with_reasoning(query, memory, context, plan):
    """Generate answer using LLM reasoning."""
    prompt = _build_reasoning_prompt(query, context, plan)
    llm = _get_planner_llm()
    try:
        response = (ChatPromptTemplate.from_template(prompt) | llm).invoke({}).content
        return {"response": response, "sections_used": list(context.keys())}
    except Exception as e:
        return {"response": f"Error generating response: {str(e)}", "sections_used": []}

def _build_reasoning_prompt(query, context, plan):
    """Build the reasoning prompt for the LLM."""
    parts = [f"User Question: {query}\n"]
    
    if plan.get("need_calculator"):
        calc = calculator_tool(query, context)
        if calc:
            parts.append(f"Calculation: {calc}\n")
    
    if context:
        parts.append("Context Data:\n")
        for section, data in context.items():
            if isinstance(data, dict):
                parts.append(f"  {section}: {json.dumps(data, indent=2)}\n")
            else:
                parts.append(f"  {section}: {data}\n")
    
    parts.append("\nProvide a concise, well-reasoned answer using the context and any calculations above.")
    return "".join(parts)

def _explain_section(section_name, memory):
    """Generate explanation for a given section."""
    explanations = {
        "business_quality": lambda: {
            "reasoning": ["Strong ROCE" if memory.get("financial_metrics", {}).get("roce", 0) > 15 else "Moderate returns"],
            "evidence": [f"ROCE: {memory.get('financial_metrics', {}).get('roce')}%"]
        },
        "price_story": lambda: {
            "evidence": [
                f"6M Return: {memory.get('chart_metrics', {}).get('returns', {}).get('6M')}%",
                f"Distance from 52W High: {memory.get('chart_metrics', {}).get('distance_from_52w_high')}%"
            ]
        },
        "market_sentiment": lambda: {
            "reasoning": [f"{len(memory.get('events', []))} recent events"],
            "evidence": [memory.get('analyst_data', {}).get('recommendation_key', 'N/A')]
        }
    }
    return explanations.get(section_name, lambda: {}).get() if section_name in explanations else {}

def explain_business_quality(memory):
    return _explain_section("business_quality", memory)

def explain_chart(memory):
    return _explain_section("price_story", memory)

def explain_sentiment(memory):
    return _explain_section("market_sentiment", memory)

def top_news_summary(memory):
    """Summarize top news articles with sentiment labels."""
    articles = memory.get("news_articles", [])
    picks = []
    for art in articles[:6]:
        headline = art.get("headline") or art.get("title") or ""
        summary = (art.get("summary") or "").lower()
        
        bullish = any(k in summary for k in ["upside", "bullish", "value", "growth", "unlock"])
        bearish = any(k in summary for k in ["slip", "down", "pressure", "risk", "concern", "weak"])
        label = "🟢" if bullish else "🔴" if bearish else "⚪"
        
        if headline:
            picks.append(f"{label} {headline}")
    return picks

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

def generate_price_interpretation(memory):
    """Generate AI interpretation for price section."""
    chart = memory.get("chart_metrics", {})
    company = memory.get("company_info", {}).get("name", "the company")
    trend = chart.get("trend", "sideways")
    distance_high = chart.get("distance_from_52w_high", 0)
    
    msgs = {
        "up": f"{company} has maintained positive momentum, trading closer to yearly highs.",
        "down": f"{company} has declined and trades closer to 52-week lows.",
        "sideways": f"{company} is trading in a sideways range."
    }
    
    result = msgs.get(trend, msgs["sideways"])
    if distance_high > 15:
        result += f" Currently {distance_high:.0f}% below 52-week high."
    return result

def company_snapshot_html(memory):
    """Generate HTML snapshot of company."""
    company = memory.get("company_info", {})
    metrics = memory.get("financial_metrics", {})
    market = memory.get("price_data", {})
    snapshot = memory.get("company_snapshot", {})
    mood = memory.get("market_intelligence", {})
    price_view = memory.get("chart_metrics", {})
    news = memory.get("news_articles", [])
    risks = memory.get("risks", [])
    opportunities = memory.get("opportunities", [])
    
    response = f"<h2>{company.get('name', 'Company')}</h2>"
    response += f"<p><strong>Sector:</strong> {company.get('sector', 'N/A')}</p>"
    
    if market.get("current"):
        response += f"<p><strong>Price:</strong> ₹{market['current']:,.2f}</p>"
    if market.get("market_cap"):
        response += f"<p><strong>Market Cap:</strong> ₹{market['market_cap']:,.2f}</p>"
    
    response += f"<p>{snapshot.get('summary', '')}</p>"
    
    if mood.get("consensus"):
        response += f"<p><strong>Market View:</strong> {mood['consensus']}</p>"
    
    response += "<h3>Recent News:</h3><ul>"
    for art in news[:3]:
        headline = art.get("headline") or art.get("title")
        if headline:
            response += f"<li>{headline}</li>"
    response += "</ul>"
    
    return response

def route_query(query):
    """Route query for backward compatibility."""
    sections = route_context(query)
    if "price_data" in sections or "chart_metrics" in sections:
        return "price_chart"
    elif "news_articles" in sections or "analyst_data" in sections:
        return "market_sentiment"
    elif "financial_metrics" in sections:
        return "fundamentals"
    return "general"


def answer_business_description(company_name, memory):
    """Return a compact business-description answer used by the UI report."""
    info = (memory or {}).get("company_info", {}) or {}
    summary = info.get("summary") or ""
    website = (memory or {}).get("website_context", {}) or {}
    pages = website.get("pages", []) if isinstance(website, dict) else []

    if pages:
        snippets = []
        for page in pages[:2]:
            text = (page.get("text") or "").strip()
            if text:
                snippets.append(text[:300])
        if snippets:
            body = " ".join(snippets)
            return {"response": body[:900]}

    if summary:
        return {"response": summary[:900]}

    sector = info.get("sector") or "its sector"
    industry = info.get("industry") or "its industry"
    return {
        "response": (
            f"{company_name} operates in {sector}, with a primary focus in {industry}. "
            "The available structured data is limited, but the company is being tracked through "
            "price history, financial metrics, news, and other market signals."
        )
    }


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
        mood = "🟢 Positive"
        label = "Positive"
    elif bearish > bullish:
        mood = "🔴 Negative"
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
        "confidence": min(0.9, 0.5 + abs(bullish - bearish) * 0.1),
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


def explain_business_snapshot(memory):
    """Return a short snapshot used by the report UI."""
    info = (memory or {}).get("company_info", {}) or {}
    summary = info.get("summary") or ""
    if summary:
        return {"summary": summary[:900]}
    return {
        "summary": (
            f"{info.get('name', 'The company')} operates in {info.get('sector', 'its sector')} "
            f"and {info.get('industry', 'its industry')}."
        )
    }


def build_investment_thesis(memory, horizon_years=5):
    """Generate a compact thesis object for report generation."""
    info = (memory or {}).get("company_info", {}) or {}
    financial = (memory or {}).get("financial_metrics", {}) or {}
    news = (memory or {}).get("news_articles", []) or []
    risks = list((memory or {}).get("risks", []) or [])
    opportunities = list((memory or {}).get("opportunities", []) or [])

    positive_signals = []
    if info.get("summary"):
        positive_signals.append("Diversified business model")
    if info.get("market_cap"):
        positive_signals.append("Large scale and market leadership")
    if financial.get("cash_flow") is not None:
        positive_signals.append("Cash flow visibility")
    if news:
        positive_signals.append("Recent news flow is available for context")

    growth_drivers = opportunities[:5] or [
        "Business expansion themes are being tracked from company data and recent news.",
    ]

    investor_fit = ["long-term compounding", "stable growth", "research-driven investors"]
    less_suitable = ["short-term traders", "investors needing very low volatility"]

    if financial.get("debt_to_equity") is not None and financial.get("debt_to_equity") > 1:
        risks.append("Leverage should be monitored")
    if financial.get("operating_margin") is not None and financial.get("operating_margin") < 10:
        risks.append("Margins look thin versus stronger peers")

    return {
        "positive_signals": positive_signals,
        "growth_drivers": growth_drivers,
        "risks": risks[:6],
        "investor_fit": investor_fit,
        "less_suitable": less_suitable,
        "profile": "strong" if len(positive_signals) >= len(risks) else "moderate",
        "horizon_years": horizon_years,
    }
