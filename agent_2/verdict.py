import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "agent_1", ".env"))


def _fallback_verdict():
    return {
        "financial_summary": "System error. Unable to generate the financial summary."
    }


def generate_verdict(health_score, red_flags, peer_comparison, fundamental_profile=None, strengths=None, weaknesses=None):
    try:
        health_summary = {
            "Current Score": health_score.get("current"),
            "Next Year Score": health_score.get("next_year"),
            "Features": health_score.get("report", {}).get("feature_vector", {})
        }

        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        prompt = ChatPromptTemplate.from_template(
            """You are an objective financial reporting system. Convert the structured data below into a clear, evidence-based financial summary.

RULES:
- Do NOT make predictions (except citing the provided next year score).
- Do NOT assign new scores.
- Do NOT make buy/sell recommendations.
- Do NOT output target prices, "Strong Buy", "Undervalued", or hard-coded labels like "Excellent Company".
- Do NOT invent facts. Only use the provided data.
- Explain what the previous components discovered.

STRUCTURE YOUR OUTPUT EXACTLY AS FOLLOWS:
Financial Summary

[Paragraph 1: Explain Future Health based on the Health Score and prominent features]

[Paragraph 2: Explain Risks based on Red Flags]

[Paragraph 3: Explain Peer Position based on Peer Comparison percentiles]

[Paragraph 4: Integrated Summary integrating strengths and weaknesses]

DATA INPUTS:
Health Prediction: {health_score}
Red Flag Detection: {red_flags}
Peer Comparison: {peer_comparison}
Fundamental Profile: {fundamental_profile}
Strengths: {strengths}
Weaknesses: {weaknesses}
"""
        )
        chain = prompt | llm
        response = chain.invoke({
            "health_score": json.dumps(health_summary),
            "red_flags": json.dumps(red_flags) if red_flags else "No critical flags detected.",
            "peer_comparison": json.dumps(peer_comparison),
            "fundamental_profile": json.dumps(fundamental_profile) if fundamental_profile else "N/A",
            "strengths": json.dumps(strengths) if strengths else [],
            "weaknesses": json.dumps(weaknesses) if weaknesses else [],
        })

        text = response.content.strip()
        return {"financial_summary": text}
    except Exception as e:
        print(f"Verdict generation fallback: {e}")
        
        # Generate fallback verdict with better analysis
        fallback_text = _generate_fallback_verdict(health_score, red_flags, peer_comparison, fundamental_profile)
        return {"financial_summary": fallback_text}


def _generate_fallback_verdict(health_score, red_flags, peer_comparison, fundamental_profile=None):
    if not peer_comparison or not peer_comparison.get("metrics"):
        return f"System error. Unable to generate the financial summary. Information is insufficient or corrupted."
    
    sector = peer_comparison.get("sector", "Unknown")
    metrics = peer_comparison.get("metrics", {})
    
    strength_count = 0
    weakness_count = 0
    
    for metric_name, data in metrics.items():
        company_val = data.get("company")
        percentile = data.get("percentile", 50)
        
        if metric_name == "ROCE" and company_val and company_val > 20:
            strength_count += 1
        elif metric_name == "OPM %" and company_val and company_val > 20:
            strength_count += 1
        elif percentile > 70 and metric_name not in ["Debtor Days", "Working Capital Days", "Inventory Days"]:
            strength_count += 1
        elif percentile < 30 and metric_name not in ["Debtor Days", "Working Capital Days", "Inventory Days"]:
            weakness_count += 1
    
    verdict_parts = []
    
    verdict_parts.append(f"Company operates in the {sector} sector.")
    
    if red_flags:
        verdict_parts.append(f"Key concerns identified: {', '.join([f['explanation'] for f in red_flags])}")
    else:
        verdict_parts.append("No critical red flags detected in financial statements.")
    
    if fundamental_profile:
        verdict_parts.append(f"Fundamental Quality: {fundamental_profile.get('financial_quality', 'Unknown')}")
    
    if strength_count > weakness_count:
        verdict_parts.append(f"Company shows strong performance relative to peers in key areas including profitability metrics.")
    elif weakness_count > strength_count:
        verdict_parts.append("Company lags behind peers in several key financial metrics.")
    else:
        verdict_parts.append("Company performance is mixed relative to sector peers.")
    
    verdict_parts.append(f"Overall assessment: The company's financial position should be evaluated considering both its fundamental quality rating and sector positioning.")
    
    return "\n".join(verdict_parts)
