"""RAG (Retrieval Augmented Generation) for company-specific research assistant."""
import os
import re
import logging
from groq import Groq

logger = logging.getLogger(__name__)


def is_company_relevant(question, ticker):
    """Check if question is relevant to company research.

    Deliberately lenient: scope decisions are left to the LLM (which sees the
    full question in context), so on-topic questions that merely CONTAIN words
    like "medical" or "tax" (e.g. for a hospital company) are not rejected.
    Only outright harmful/irrelevant topics are blocked here.
    """
    blocked = [
        r"(?i)\b(hack|malware|illegal|scam|gambling)\b",
    ]

    for pattern in blocked:
        if re.search(pattern, question):
            return False, "That question is outside the scope of this company research assistant. I can help with questions about the company, its financials, stock data, or calculations based on the numbers shown on screen."

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
    
    # Greetings / very short inputs are handled gracefully by the LLM prompt,
    # so don't hard-block them here.
    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        company_name = memory.get("company_info", {}).get("name", ticker)
        company_context = build_company_context(memory, agent2_output)
        
        system_prompt = f"""You are a professional investment research assistant analyzing {company_name} ({ticker}).

OUTPUT RULE (HIGHEST PRIORITY): Your reply must be ONLY the final user-facing answer —
one clean, direct response. NEVER output reasoning, thinking steps, numbered analysis
plans, drafts, revisions, or meta-commentary such as "Let me analyze", "Draft:", "Step 1:",
"Here's my thinking", "According to the data I need to...". If you need to reason, do it
silently and output only the polished answer.

HOW TO HANDLE EACH KIND OF QUESTION:
1. Company/stock questions (business, financials, metrics, valuation, risks, peers):
   Answer using the COMPANY DATA and on-screen data below. Cite concrete numbers.
2. Math/calculation questions (percentages, ratios, differences, growth, market cap
   arithmetic, "what if" computations): Understand what is being asked, compute the
   result yourself (do the arithmetic carefully, step by step, silently), and present
   the final number clearly. Use the company's actual figures from the provided data
   when the question refers to them. Show the inputs used, e.g.
   "₹8,837.5 × 2 = ₹17,675". Do NOT refuse math questions just because they are not
   a standard metric.
3. Questions about what is on the screen: If an on-screen data block is provided,
   answer from it first — it reflects exactly what the user sees right now.
4. Out-of-scope questions (unrelated companies with no comparison intent, general
   trivia, weather, sports, coding help, personal opinions, etc.): Reply politely and
   briefly, e.g. "That's outside what I can help with here — I'm focused on
   {company_name} ({ticker}) and its financial data. Try asking about its business,
   financials, valuation, or the numbers shown on screen."
5. Greetings ("hi", "hello"): Greet back in one line and say what you can help with.

IMPORTANT RULES:
- Always reference {ticker} specifically - never discuss other companies unless directly asked for comparison
- Use concrete numbers and metrics from the company data when available
- Explain financial concepts in simple, clear terms
- If data is unavailable for {ticker}, say "This metric is not available for {ticker}"
- Never provide personal investment advice (don't say "you should buy" or "you should sell")
- Instead use neutral language: "Based on the data, this company shows..." or "This metric suggests..."
- If unsure about something, say "I don't have enough reliable data to answer that accurately"

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
                model=model, messages=messages, temperature=0, max_tokens=700,
            )

        try:
            response = _call(os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"))
        except Exception as llm_err:
            # Rate-limited on the primary model — retry once on a fallback model (separate quota)
            if "rate_limit" in str(llm_err).lower() or "429" in str(llm_err):
                response = _call("llama3-8b-8192")
            else:
                raise

        answer = response.choices[0].message.content or ""
        
        # Reasoning models (e.g. qwen) prepend a <think> block — strip it
        if "<think>" in answer:
            answer = answer.split("</think>")[-1].strip()
        
        # Remove markdown formatting markers
        answer = answer.replace("**", "").replace("__", "").replace("*", "")

        # Strip any leaked reasoning preamble — keep only what follows the LAST marker
        reasoning_markers = [
            "Here's a thinking process", "Here's my thinking", "Let me analyze",
            "Here's my analysis", "Let me think about this", "Here's my approach",
            "Here's how I", "Draft", "Analysis of the question", "Thinking process",
            "Step 1:", "First, let me", "Let's analyze", "According to the data",
            "✅ Proceed. Output generation.", "[Self-Correction/Verification during thought]",
            "✅ Proceed.", "Final answer:", "Answer:", "Response:",
        ]
        for marker in reasoning_markers:
            if marker.lower() in answer.lower():
                idx = answer.lower().rfind(marker.lower())
                rest = answer[idx + len(marker):].lstrip(" :\n-").strip()
                # Only use the tail if a substantial final answer remains after the marker
                if len(rest) > 20:
                    answer = rest

        # If multiple large paragraphs remain and the earliest ones look like
        # reasoning scaffolding, keep the last coherent paragraph.
        paragraphs = [p.strip() for p in answer.split("\n\n") if p.strip()]
        if len(paragraphs) > 2 and any(
            p.lower().startswith(("step", "draft", "here's", "let me", "first,", "1.", "2.", "analysis", "my thinking", "reasoning"))
            for p in paragraphs[:-1]
        ):
            answer = paragraphs[-1]
        
        # Clean up excessive newlines and spacing
        answer = "\n".join([p.strip() for p in answer.split("\n") if p.strip()])
        answer = answer.strip()
        
        # Ensure we don't return empty or truncated responses
        if not answer or len(answer) < 5:
            answer = "I could not generate a response. Please try rephrasing your question."
        
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
