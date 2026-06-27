import numpy as np


def analyze_fundamentals(peer_comparison, red_flags):
    """Identify strengths and weaknesses from financial metrics."""
    strengths = []
    weaknesses = []
    
    if not peer_comparison or not peer_comparison.get("metrics"):
        return {"strengths": [], "weaknesses": []}
    
    metrics = peer_comparison.get("metrics", {})
    
    # Check profitability metrics
    if "ROCE" in metrics:
        roce = metrics["ROCE"].get("company", 0)
        if roce and roce > 20:
            strengths.append("Strong profitability (ROCE > 20%)")
        elif roce and roce < 10:
            weaknesses.append("Weak profitability (ROCE < 10%)")
    
    if "OPM %" in metrics:
        opm = metrics["OPM %"].get("company", 0)
        if opm and opm > 20:
            strengths.append("Healthy operating margins (> 20%)")
        elif opm and opm < 10:
            weaknesses.append("Low operating margins (< 10%)")
    
    if "Net Profit" in metrics:
        net_profit = metrics["Net Profit"].get("company", 0)
        if net_profit and net_profit > 200000000000:
            strengths.append("Strong net profit generation")
    
    # Check leverage
    if "Debt" in metrics:
        debt = metrics["Debt"].get("company", 0)
        peers = metrics["Debt"].get("percentile", 50)
        if peers < 30:
            strengths.append("Low debt relative to peers")
        elif peers > 70:
            weaknesses.append("Higher debt than peers")
    
    # Check cash flow
    if "Cash from Operating Activity" in metrics:
        pct = metrics["Cash from Operating Activity"].get("percentile", 50)
        if pct > 70:
            strengths.append("Strong cash generation")
    
    # Check efficiency (lower is better for days metrics)
    if "Debtor Days" in metrics:
        pct = metrics["Debtor Days"].get("percentile", 50)
        if pct < 30:
            strengths.append("Efficient receivables management")
        elif pct > 70:
            weaknesses.append("Slow receivables collection")
    
    # Check red flags
    if not red_flags:
        strengths.append("No financial anomalies detected")
    
    return {
        "strengths": strengths,
        "weaknesses": weaknesses
    }


def generate_fundamental_profile(strengths, weaknesses, peer_comparison):
    """Generate high-level fundamental quality assessment."""
    if not peer_comparison or not peer_comparison.get("metrics"):
        return "Unknown"
    
    metrics = peer_comparison.get("metrics", {})
    
    positive_factors = 0
    negative_factors = 0
    
    # ROCE check
    if "ROCE" in metrics:
        roce = metrics["ROCE"].get("company", 0)
        pct = metrics["ROCE"].get("percentile", 50)
        if roce and roce > 20 and pct > 50:
            positive_factors += 2
        elif roce and roce < 10:
            negative_factors += 1
    
    # OPM check
    if "OPM %" in metrics:
        opm = metrics["OPM %"].get("company", 0)
        pct = metrics["OPM %"].get("percentile", 50)
        if opm and opm > 15 and pct > 50:
            positive_factors += 2
        elif opm and opm < 10:
            negative_factors += 1
    
    # Debt check
    if "Debt" in metrics:
        pct = metrics["Debt"].get("percentile", 50)
        if pct < 50:
            positive_factors += 1
    
    # Cash flow check
    if "Cash from Operating Activity" in metrics:
        pct = metrics["Cash from Operating Activity"].get("percentile", 50)
        if pct > 70:
            positive_factors += 2
    
    # Determine quality level
    if positive_factors >= 4:
        return "High"
    elif positive_factors >= 2 and negative_factors <= 1:
        return "Moderate"
    elif negative_factors >= 2:
        return "Weak"
    else:
        return "Moderate"
