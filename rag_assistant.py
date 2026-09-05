"""RAG (Retrieval Augmented Generation) for company-specific research assistant."""
import os
import re
import logging
from groq import Groq

logger = logging.getLogger(__name__)


def is_company_relevant(question, ticker):
    """Check if question is relevant to company research."""
    # Blocked keywords/patterns
    blocked = [
        r"(?i)(crypto|bitcoin|nft|forex|trading bot|gambling)",
        r"(?i)(personal advice|should i buy|will you manage)",
        r"(?i)(legal advice|tax|medical|political)",
        r"(?i)(hack|malware|illegal|scam)",
    ]
    
    for pattern in blocked:
        if re.search(pattern, question):
            return False, "I can only answer questions about company fundamentals and stock research."
    
    # Check if question is about a different company
    if re.search(r"(?i)(compare|vs|versus|different|other)\s+(?!to\s+)", question):
        # Allow comparisons to this company
        if re.search(rf"(?i){re.escape(ticker.split('.')[0])}", question):
            return True, None
        # Comparisons to peers OK
        if "peer" in question.lower() or "competitor" in question.lower():
            return True, None
        # General comparison OK
        return True, None
    
    return True, None


def build_company_context(memory: dict, agent2_output: dict) -> str:
    """Extract company knowledge base for RAG."""
    info = memory.get("company_info", {})
    metrics = memory.get("financial_metrics", {})
    price_data = memory.get("price_data", {})
    risks = memory.get("risks", [])
    opps = memory.get("opportunities", [])
    
    context = f"""
COMPANY: {info.get('name', 'Unknown')} ({info.get('ticker', 'N/A')})
SECTOR: {info.get('sector', 'N/A')}
INDUSTRY: {info.get('industry', 'N/A')}

KEY METRICS:
- Current Price: ₹{price_data.get('current', 'N/A')}
- Market Cap: ₹{info.get('market_cap', 'N/A')}
- P/E Ratio: {info.get('pe_ratio', 'N/A')}
- ROE: {metrics.get('roe', 'N/A')}%
- Operating Margin: {metrics.get('operating_margin', 'N/A')}%
- Debt/Equity: {metrics.get('debt_to_equity', 'N/A')}
- Current Ratio: {metrics.get('current_ratio', 'N/A')}
- 52W High: ₹{price_data.get('high_52w', 'N/A')}
- 52W Low: ₹{price_data.get('low_52w', 'N/A')}

BUSINESS:
{info.get('summary', 'No summary available')[:400]}...

RED FLAGS:
{chr(10).join(f"- {f.get('metric')}: {f.get('explanation')}" for f in agent2_output.get('red_flags', [])[:5]) if agent2_output.get('red_flags') else "None identified"}

RISKS:
{chr(10).join(f"- {r}" for r in risks[:5]) if risks else "None identified"}

OPPORTUNITIES:
{chr(10).join(f"- {o}" for o in opps[:5]) if opps else "None identified"}

PEERS:
{chr(10).join(f"- {p}" for p in agent2_output.get('peer_comparison', {}).get('peers', [])[:5]) if agent2_output.get('peer_comparison', {}).get('peers') else "No peer data available"}
"""
    return context


def rag_chat(question: str, memory: dict, agent2_output: dict, ticker: str = None, tab_context: str = None):
    """
    Process chat query with company context.

    Args:
        question: User's question
        memory: Company memory from unified pipeline
        agent2_output: Agent 2 analysis output
        ticker: Company ticker (REQUIRED - ensures correct company context)
        tab_context: Optional description of the tab the user is currently viewing,
                     including the exact values rendered on screen.
    
    Returns:
        {
            "response": "Answer text",
            "status": "success|error|blocked",
            "error_reason": "...",
            "company": ticker,
        }
    """
    if not question or not question.strip():
        return {
            "response": "Please ask a question about the company.",
            "status": "error",
            "error_reason": "Empty question",
            "company": ticker,
        }
    
    # Get ticker from memory or parameter
    if not ticker:
        ticker = memory.get("company_info", {}).get("ticker")
    
    # CRITICAL: Validate that we have company context
    if not ticker:
        return {
            "response": "Error: No company context provided for chat.",
            "status": "error",
            "error_reason": "Missing ticker - cannot answer without knowing which company",
            "company": None,
        }
    
    # Check question relevance
    is_relevant, block_reason = is_company_relevant(question, ticker)
    if not is_relevant:
        return {
            "response": block_reason or "That question is outside the scope of company research.",
            "status": "blocked",
            "error_reason": block_reason,
            "company": ticker,
        }
    
    # If question too short
    if len(question.strip()) < 5:
        return {
            "response": f"Please ask a more specific question about {ticker}'s fundamentals or financial health.",
            "status": "error",
            "error_reason": "Question too vague",
            "company": ticker,
        }
    
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        company_name = memory.get("company_info", {}).get("name", ticker)
        company_context = build_company_context(memory, agent2_output)
        
        system_prompt = f"""You are a professional investment research assistant analyzing {company_name} ({ticker}).

Your role is to answer questions about this specific company using the provided financial data.

CRITICAL: Respond with ONLY the final answer. Do not include your reasoning process, analysis steps, drafts, or meta-commentary about how you constructed the answer. Output the direct response only.

IMPORTANT RULES:
1. Always reference {ticker} specifically - never discuss other companies unless directly asked for comparison
2. Use concrete numbers and metrics from the company data when available
3. Explain financial concepts in simple, clear terms
4. If data is unavailable for {ticker}, say "This metric is not available for {ticker}"
5. Never provide personal investment advice (don't say "you should buy" or "you should sell")
6. Instead use neutral language: "Based on the data, this company shows..." or "This metric suggests..."
7. Always cite sources: "According to the financial data..." or "Red flags include..."
8. If unsure about something, say "I don't have enough reliable data to answer that accurately"
9. Answer BOTH kinds of questions: metric-specific ones (ground every number in the
   on-screen tab data when provided) and general questions about the company
   (business model, strategy, sector position, history) using the COMPANY DATA below.

COMPANY DATA:
{company_context}
"""
        if tab_context:
            system_prompt += f"""

WHAT THE USER IS CURRENTLY VIEWING:
The user asked this question while on a specific tab of the research page. The data
below is EXACTLY what is rendered on their screen right now — ground it in these
numbers first before reaching for other data.

{tab_context}
"""
        
        messages = [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": f"Question about {ticker}: {question}",
            },
        ]
        
        def _call(model):
            return client.chat.completions.create(
                model=model, messages=messages, temperature=0.3, max_tokens=500,
            )

        try:
            response = _call(os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        except Exception as llm_err:
            # Rate-limited on the primary model — retry once on a fallback model (separate quota)
            if "rate_limit" in str(llm_err).lower() or "429" in str(llm_err):
                response = _call("openai/gpt-oss-20b")
            else:
                raise

        answer = response.choices[0].message.content or ""
        # Reasoning models (e.g. qwen) prepend a <think> block — strip it
        if "<think>" in answer:
            answer = answer.split("</think>")[-1].strip()
        
        # Strip any leaked reasoning that starts with "Here's a thinking process", "Let me think", etc.
        reasoning_markers = ["Here's a thinking process:", "Here's my thinking:", "Let me analyze:", 
                            "Here's my analysis:", "Let me think about this:", "Here's my approach:",
                            "Draft:", "Analysis:"]
        for marker in reasoning_markers:
            if marker in answer:
                # Take only content after the marker if it looks like preamble, else keep all
                parts = answer.split(marker, 1)
                if len(parts) > 1:
                    rest = parts[1].strip()
                    # If the rest looks like reasoning continuation, skip it
                    if rest.lower().startswith(("1.", "step", "first", "then", "next", "finally")):
                        answer = answer  # Keep original if it seems like reasoning steps
                    else:
                        answer = rest  # Use the part after the marker
        
        # Final sanity: if answer still has multiple paragraphs that look like thinking, extract the last coherent one
        if answer.count("\n\n") > 2:
            paragraphs = answer.split("\n\n")
            # Take the longest final paragraph that doesn't look like reasoning
            for para in reversed(paragraphs):
                if not any(p in para.lower() for p in ["step", "process", "draft", "here's", "analysis"]):
                    answer = para.strip()
                    break
        
        logger.info(f"RAG chat successful for {ticker}")
        return {
            "response": answer,
            "status": "success",
            "error_reason": None,
            "company": ticker,
        }
        
    except Exception as e:
        logger.error(f"RAG chat error for {ticker}: {e}")
        return {
            "response": f"I encountered an error processing your question about {ticker}. Please try again.",
            "status": "error",
            "error_reason": str(e),
            "company": ticker,
        }
