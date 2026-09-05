from agent_2.fundamentals import analyze_fundamentals
from agent_2.fundamental_profile import build_fundamental_profile
from agent_2.red_flags import detect_red_flags, assess_isolation_forest
from agent_2.peer_comparison import compare_peers
from agent_2.final_agent2_router import route_query
from agent_2.health_data import build_health_features
#main function for Agent 2, which processes the output from Agent 1 to analyze the fundamentals of a given stock ticker. It detects red flags, assesses the stock using an isolation forest model, compares it with peers, and builds a fundamental profile. The function returns a structured dictionary containing financial facts, red flags, model assessment, peer comparison, fundamental profile, and signals indicating strengths and weaknesses.

def run_agent2(agent1_payload, question=""):
    ticker = agent1_payload.get("ticker")
    red_flags = []
    peer_comparison = {}
    model_assessment = {}
    financial_facts = {}

    route = route_query(question, ticker)
    
    # Run red flags detection
    if "red_flags" in route.get("modules", []) or "fundamentals" in route.get("modules", []):
        try:
            red_flags = detect_red_flags(ticker)
            model_assessment = assess_isolation_forest(ticker)
        except Exception as e:
            print(f"Agent2 red flags failed: {e}")

    # Run peer comparison
    if "peer_comparison" in route.get("modules", []) or "fundamentals" in route.get("modules", []):
        try:
            company_features = build_health_features(ticker)["feature_vector"]
            peer_comparison = compare_peers(ticker, company_features)
            financial_facts = {
                "ROCE": company_features.get("ROCE"),
                "OperatingMargin": company_features.get("OPM %"),
                "Debt": company_features.get("Debt"),
                "CurrentRatio": company_features.get("Current Ratio"),
                "NetProfit": company_features.get("Net Profit"),
                "CashFromOperatingActivity": company_features.get("Cash from Operating Activity"),
                "DebtorDays": company_features.get("Debtor Days"),
                "InventoryDays": company_features.get("Inventory Days"),
                "WorkingCapitalDays": company_features.get("Working Capital Days"),
            }
        except Exception as e:
            print(f"Agent2 peer comparison failed: {e}")

    # Build fundamental profile
    profile = build_fundamental_profile(peer_comparison, red_flags)
    
    # Get analysis with strengths/weaknesses
    analysis = analyze_fundamentals(peer_comparison, red_flags)
    
    return {
        "ticker": ticker,
        "financial_facts": financial_facts,
        "red_flags": red_flags,
        "model_assessment": model_assessment,
        "peer_comparison": peer_comparison,
        "fundamental_profile": profile,
        "fundamental_signals": {
            "strengths": analysis["strengths"],
            "weaknesses": analysis["weaknesses"],
        },
    }
