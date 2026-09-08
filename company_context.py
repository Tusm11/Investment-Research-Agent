"""Company context validation."""

from agent_1.tools.nifty50 import NIFTY50, get_nifty50_data

# Build NIFTY50 lookup
NIFTY50_TICKERS = {ticker.split(".")[0]: ticker for ticker, _ in NIFTY50}


class CompanyContext:
    """Validate and store company context (ticker + name)."""

    def __init__(self, ticker: str, name: str = None):
        """Initialize with ticker (e.g., 'TCS.NS') and optional name."""
        if not ticker:
            raise ValueError("Ticker required")
        
        # Normalize ticker
        if not ticker.endswith(".NS"):
            ticker = f"{ticker}.NS"
        
        # Validate ticker exists in NIFTY50
        ticker_base = ticker.split(".")[0]
        if ticker_base not in NIFTY50_TICKERS:
            raise ValueError(f"Ticker {ticker} not in NIFTY50")
        
        self.ticker = ticker
        self.name = name or ticker_base
    
    def __str__(self):
        return f"{self.name} ({self.ticker})"


def validate_company_data(company_ctx: CompanyContext, agent1_output: dict) -> dict:
    """Validate that agent1 output matches requested company context.
    
    Returns:
        {
            "status": "ok|mismatch",
            "issues": [list of mismatches if status == "mismatch"]
        }
    """
    issues = []
    
    agent_ticker = agent1_output.get("ticker", "")
    if agent_ticker != company_ctx.ticker:
        issues.append(f"Ticker mismatch: requested {company_ctx.ticker}, got {agent_ticker}")
    
    agent_company_info = agent1_output.get("company_info", {})
    agent_name = agent_company_info.get("company_name", "")
    if agent_name and company_ctx.name not in agent_name and agent_name not in company_ctx.name:
        issues.append(f"Company name mismatch: requested {company_ctx.name}, got {agent_name}")
    
    if issues:
        return {"status": "mismatch", "issues": issues}
    
    return {"status": "ok", "issues": []}
