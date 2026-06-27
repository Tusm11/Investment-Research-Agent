from agent_2.fundamentals import analyze_fundamentals, generate_fundamental_profile


def build_fundamental_profile(peer_comparison, red_flags):
    """Build comprehensive fundamental profile."""
    analysis = analyze_fundamentals(peer_comparison, red_flags)
    
    quality = generate_fundamental_profile(
        analysis["strengths"], 
        analysis["weaknesses"], 
        peer_comparison
    )
    
    return {
        "financial_quality": quality,
        "summary": _generate_summary(quality, analysis, peer_comparison),
        "strengths": analysis["strengths"],
        "weaknesses": analysis["weaknesses"]
    }


def _generate_summary(quality, analysis, peer_comparison):
    if not peer_comparison or not peer_comparison.get("metrics"):
        return "Sector comparison data is currently unavailable."

    if quality == "High":
        return "The company exhibits strong financial fundamentals with profitability, efficient capital utilization, and healthy cash generation that outperforms sector peers."
    elif quality == "Moderate":
        return "The company shows acceptable financial fundamentals with some areas of strength but also notable room for improvement relative to peers."
    elif quality == "Weak":
        return "The company demonstrates financial weaknesses including marginal profitability, higher leverage, or operational inefficiencies compared to peers."
    else:
        return "Financial fundamentals analysis is based on partial data; some metrics could not be computed from available sources."
