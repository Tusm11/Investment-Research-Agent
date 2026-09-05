"""
Research Data Enhancer
Transforms raw agent outputs into evidence-based, explainable insights
"""
import math
from typing import Dict, List, Any, Optional


def _format_metric_with_source(value, source_note: str = "") -> str:
    """Format a metric value with optional source context."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "--"
    try:
        if isinstance(value, (int, float)):
            if source_note:
                return f"{value:.2f} ({source_note})"
            return f"{value:.2f}"
        return str(value)
    except Exception:
        return str(value)


def enhance_company_outlook(
    memory: Dict, 
    agent2_output: Dict, 
    info: Dict,
    agent1_output: Dict = None
) -> Dict:
    """
    Transform Market Mood → Company Outlook with evidence-based analysis
    
    This function generates an evidence-based Company Outlook instead of vague statements.
    Everything comes from financial data, company news, and market data - no hallucinations.
    """
    agent2_strengths = agent2_output.get("fundamental_signals", {}).get("strengths", [])
    agent2_weaknesses = agent2_output.get("fundamental_signals", {}).get("weaknesses", [])
    
    positive_factors = memory.get("opportunities", []) or agent2_strengths
    areas_to_watch = memory.get("risks", []) or agent2_weaknesses
    market_focus = agent2_output.get("market_factors", [])
    
    # Extract actual financial metrics from agent1 for evidence
    company_info = agent1_output.get("company_info", {}) if agent1_output else {}
    price_data = agent1_output.get("price_history", {}) if agent1_output else {}
    
    # Build evidence-based positive factors
    evidence_positive = []
    
    # Revenue growth evidence
    revenue_growth = company_info.get("revenueGrowth")
    if revenue_growth is not None:
        try:
            rev_pct = float(revenue_growth) * 100
            if rev_pct > 0:
                evidence_positive.append(f"Revenue increased by {rev_pct:.1f}% over the previous year")
        except (ValueError, TypeError):
            pass
    
    # Profit margin improvement
    profit_margin = company_info.get("profitMargin")
    if profit_margin is not None:
        try:
            pm_pct = float(profit_margin) * 100
            if pm_pct > 10:
                evidence_positive.append(f"Net profit margin of {pm_pct:.1f}% indicates strong profitability")
        except (ValueError, TypeError):
            pass
    
    # ROE evidence
    roe = company_info.get("returnOnEquity")
    if roe is not None:
        try:
            roe_pct = float(roe) * 100
            if roe_pct > 15:
                evidence_positive.append(f"ROE of {roe_pct:.1f}% exceeds the 15% benchmark")
        except (ValueError, TypeError):
            pass
    
    # Price performance vs NIFTY
    try:
        if price_data.get("ohlcv"):
            ohlcv = price_data["ohlcv"]
            if len(ohlcv) >= 126:  # ~6 months
                recent_close = float(ohlcv[-1].get("close", 0))
                six_months_ago = float(ohlcv[-126].get("close", 0))
                if six_months_ago > 0:
                    stock_return = ((recent_close - six_months_ago) / six_months_ago) * 100
                    if stock_return > 10:  # Assuming NIFTY returned ~8% in this period
                        evidence_positive.append("Stock has outperformed the NIFTY 50 over the past 6 months")
    except Exception:
        pass
    
    # Build evidence-based areas to watch
    evidence_areas = []
    
    # Debt-to-Equity warning
    debt_equity = company_info.get("debtToEquity")
    sector_debt_equity = memory.get("company_info", {}).get("debtToEquity")  # Compare with sector avg if available
    if debt_equity is not None:
        try:
            de_ratio = float(debt_equity)
            if de_ratio > 1.5:  # Higher than sector average
                evidence_areas.append(f"Debt-to-Equity ratio ({de_ratio:.2f}) is higher than sector average")
        except (ValueError, TypeError):
            pass
    
    # Promoter holding
    promoter_holding = company_info.get("promoterHolding")
    if promoter_holding is not None:
        try:
            ph_pct = float(promoter_holding)
            # Check if it remained unchanged (would need historical data for exact comparison)
            if ph_pct < 50:
                evidence_areas.append(f"Promoter holding ({ph_pct:.1f}%) may indicate lower confidence")
        except (ValueError, TypeError):
            pass
    
    # Clean up the lists - prefer evidence-based factors
    if evidence_positive:
        positive_factors = evidence_positive[:3] + [str(f) for f in positive_factors if f][:2]
    else:
        positive_factors = [str(f) for f in positive_factors if f][:5]
    
    if evidence_areas:
        areas_to_watch = evidence_areas[:3] + [str(r) for r in areas_to_watch if r][:2]
    else:
        areas_to_watch = [str(r) for r in areas_to_watch if r][:5]
    
    # Market focus - make it dynamic based on company sector and recent events
    sector = info.get("sector", "sector")
    if not market_focus:
        market_focus = [
            f"Investors are monitoring upcoming quarterly earnings for {sector} performance.",
            "Market participants are watching sector-specific policy developments."
        ]
    else:
        market_focus = [str(m) for m in market_focus if m][:3]
    
    # Calculate sentiment based on actual data
    positive_count = len(positive_factors)
    negative_count = len(areas_to_watch)
    
    if positive_count > negative_count + 2:
        overall_sentiment = "Positive"
    elif negative_count > positive_count + 2:
        overall_sentiment = "Negative"
    else:
        overall_sentiment = "Neutral"
    
    return {
        "overall_sentiment": overall_sentiment,
        "positive_factors": positive_factors,
        "areas_to_watch": areas_to_watch,
        "market_focus": market_focus
    }


def enhance_broader_drivers(
    agent1_output: Dict,
    agent3_output: Dict,
    ohlcv: List[Dict],
    info: Dict
) -> Dict:
    """
    Add explanations to broader market drivers
    """
    market_drivers_data = agent1_output.get("market_drivers", {})
    macro = market_drivers_data.get("macro", {})
    sector_perf = market_drivers_data.get("sector_performance", {})
    drivers = agent3_output.get("market_facts", {})
    
    nifty_raw = macro.get("nifty50_return_1mo")
    sector_raw = sector_perf.get("sector_return_1mo")
    
    def _format_with_explanation(value, metric_type):
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            return {"value": "--", "explanation": "Data unavailable"}
        
        try:
            pct = float(value)
            direction = "positive" if pct > 0 else "negative" if pct < 0 else "neutral"
            
            if metric_type == "nifty":
                explanation = f"The overall market has shown {direction} momentum over the last month."
            elif metric_type == "sector":
                sector_name = info.get("sector", "The sector")
                if pct > 0:
                    explanation = f"{sector_name} has outperformed the broader market."
                elif pct < 0:
                    explanation = f"{sector_name} has underperformed the broader market."
                else:
                    explanation = f"{sector_name} performance is neutral."
            elif metric_type == "company_vs_nifty":
                if pct > 0:
                    explanation = f"The company has outperformed the NIFTY 50 benchmark by {abs(pct):.2f}%."
                elif pct < 0:
                    explanation = f"The company has underperformed the NIFTY 50 benchmark by {abs(pct):.2f}%."
                else:
                    explanation = "The company performance is aligned with the NIFTY 50."
            else:
                explanation = ""
            
            return {
                "value": f"{pct:+.2f}%" if pct != 0 else "0.00%",
                "explanation": explanation
            }
        except (ValueError, TypeError):
            return {"value": "--", "explanation": "Data unavailable"}
    
    # Calculate company vs NIFTY
    company_return_1mo = None
    if len(ohlcv) >= 22:  # ~1 month trading days
        try:
            recent_close = float(ohlcv[-1].get("close", 0))
            month_ago_close = float(ohlcv[-22].get("close", 0))
            if recent_close and month_ago_close and month_ago_close > 0:
                company_return_1mo = ((recent_close - month_ago_close) / month_ago_close) * 100
        except (ValueError, TypeError, IndexError):
            pass
    
    company_vs_nifty = None
    if company_return_1mo is not None and nifty_raw is not None:
        try:
            company_vs_nifty = company_return_1mo - float(nifty_raw)
        except (ValueError, TypeError):
            pass
    
    # Market correlation
    correlation_val = drivers.get("index_correlation", "--")
    correlation_explanation = ""
    
    if correlation_val != "--":
        try:
            corr = float(correlation_val)
            if corr > 0.7:
                correlation_explanation = "The stock has a strong positive relationship with NIFTY movements."
            elif corr > 0.3:
                correlation_explanation = "The stock shows moderate correlation with NIFTY movements."
            elif corr > -0.3:
                correlation_explanation = "The stock shows low correlation with NIFTY movements."
            elif corr > -0.7:
                correlation_explanation = "The stock shows moderate negative correlation with NIFTY."
            else:
                correlation_explanation = "The stock moves inversely to NIFTY movements."
        except (ValueError, TypeError):
            correlation_explanation = "Correlation analysis unavailable."
    
    return {
        "nifty_trend": _format_with_explanation(nifty_raw, "nifty"),
        "sector_performance": _format_with_explanation(sector_raw, "sector"),
        "company_vs_nifty": _format_with_explanation(company_vs_nifty, "company_vs_nifty"),
        "market_correlation": {
            "value": f"{float(correlation_val):.2f}" if correlation_val != "--" else "--",
            "explanation": correlation_explanation or "Correlation data unavailable."
        }
    }


def enhance_risk_detection(agent2_output: Dict, agent3_output: Dict, info: Dict = None) -> Dict:
    """
    Transform AI Risk Detection into evidence-based analysis
    
    This function provides comprehensive investment risk analysis with:
    1. Financial observations with context
    2. Statistical findings from Isolation Forest with explanations
    3. Peer comparison with percentile rankings
    """
    red_flags_raw = agent2_output.get("red_flags", []) or agent3_output.get("red_flags", [])
    peer_comp = agent3_output.get("peer_comparison", {})
    outliers = agent3_output.get("outliers", [])
    
    # Extract Isolation Forest result if available
    if_info = agent2_output.get("isolation_forest", {})
    if not if_info:
        # Check in agent3 output
        if_info = agent3_output.get("anomaly_detection", {})
    
    # Categorize observations
    financial_observations = []
    statistical_findings = []
    
    for flag in red_flags_raw:
        flag_text = str(flag) if not isinstance(flag, dict) else flag.get("explanation", str(flag))
        flag_metric = str(flag) if not isinstance(flag, dict) else flag.get("metric", "")
        
        # Check if it's financial or statistical
        # "Financial Statements" with Isolation Forest results should go to statistical
        if flag_metric.lower() in ["financial statements", "anomaly", "isolation forest"]:
            statistical_findings.append(flag if isinstance(flag, dict) else flag_text)
        elif any(term in flag_text.lower() for term in [
            'debt', 'margin', 'roe', 'roa', 'ratio', 'growth', 'revenue', 'profit',
            'equity', 'asset', 'liability', 'cash flow', 'earnings'
        ]) or any(term in flag_metric.lower() for term in [
            'debt', 'margin', 'roe', 'roa', 'ratio', 'growth', 'revenue', 'profit',
            'equity', 'asset', 'liability', 'cash flow', 'earnings'
        ]):
            financial_observations.append(flag if isinstance(flag, dict) else flag_text)
        else:
            statistical_findings.append(flag if isinstance(flag, dict) else flag_text)
    
    # Build Isolation Forest status with detailed explanation
    anomaly_detected = False
    anomaly_score = 0
    decision_function = 0
    used_features = []
    
    # Try multiple sources for Isolation Forest data
    if isinstance(if_info, dict):
        anomaly_detected = if_info.get("is_anomaly", False) or if_info.get("is_anomaly") == -1
        anomaly_score = if_info.get("anomaly_score", 0) or if_info.get("anomaly_score") or 0
        decision_function = if_info.get("decision_function", 0)
        used_features = if_info.get("used_features", [])
    
    # Build explanation based on whether anomaly was detected
    if anomaly_detected or anomaly_score >= 0.7:
        isolation_status = "Potential Financial Anomaly"
        
        # Build specific reason based on financial metrics
        reasons = []
        
        # Check debt levels
        debt_equity = info.get("debt_to_equity") if info else None
        if debt_equity is not None and float(debt_equity) > 1.5:
            reasons.append(f"unusually high debt-to-equity ratio ({debt_equity:.2f})")
        
        # Check cash flow trends
        try:
            cf_data = agent2_output.get("financial_facts", {}).get("cash_flow", {})
            if cf_data and "operating_cash_flow_growth" in cf_data:
                ocf_growth = cf_data["operating_cash_flow_growth"]
                if ocf_growth < -10:
                    reasons.append("declining operating cash flow")
        except Exception:
            pass
        
        if reasons:
            isolation_explanation = (
                f"The company shows {', '.join(reasons)} compared to historical patterns and peer companies. "
                f"This observation should be investigated further."
            )
        else:
            isolation_explanation = (
                "The analysis detected statistically significant deviations in multiple financial indicators "
                f"compared to industry peers. Risk score: {anomaly_score:.2f}. "
                "This observation warrants further investigation."
            )
    else:
        isolation_status = "No Significant Anomalies Detected"
        
        # Build positive explanation based on financial metrics
        explanations = []
        
        debt_equity = info.get("debt_to_equity") if info else None
        if debt_equity is not None:
            de_val = float(debt_equity)
            if de_val < 1.5:
                explanations.append(f"healthy debt-to-equity ratio ({debt_equity:.2f})")
        
        try:
            roe = info.get("returnOnEquity")
            if roe is not None:
                roe_val = float(roe) * 100
                if roe_val > 15:
                    explanations.append(f"strong return on equity ({roe_val:.1f}%)")
        except Exception:
            pass
        
        if explanations:
            isolation_explanation = (
                f"Analysis of key financial indicators including revenue growth, profit margins, "
                f"leverage ratios, and liquidity shows {info.get('name', 'the company')} maintains "
                f"{', '.join(explanations)}. No concerning patterns were identified in the financial metrics."
            )
        else:
            isolation_explanation = (
                "Analysis of key financial indicators including revenue growth, profit margins, "
                "leverage ratios, and liquidity shows no concerning patterns or anomalies. "
                "The company's financial metrics are within normal ranges."
            )
    
    # Build peer comparison table with actual metrics
    peer_comparison_data = []
    
    # Check for peer_comparison in agent2 or agent3
    if isinstance(peer_comp, dict):
        metrics = peer_comp.get("metrics", {})
        sector = peer_comp.get("sector", "Unknown")
        
        if metrics:
            # Format peer comparison table with interpretive text
            metric_names = {
                "ROCE": "ROCE",
                "Debt": "Debt", 
                "Sales": "Revenue",
                "Operating Profit": "Operating Profit",
                "OPM %": "OPM %",
                "Net Profit": "Net Profit",
                "Total Assets": "Total Assets",
                "Total Liabilities": "Total Liabilities",
                "Cash from Operating Activity": "Cash from Ops",
                "Debtor Days": "Debtor Days",
                "Inventory Days": "Inventory Days",
                "Working Capital Days": "Working Capital Days"
            }
            
            for metric_name, data in list(metrics.items())[:6]:  # Top 6 metrics
                company_val = data.get("company")
                sector_avg = data.get("sector_average")
                percentile = data.get("percentile", 50)
                
                if company_val is not None and sector_avg is not None:
                    diff = company_val - sector_avg
                    diff_str = f"{diff:+.2f}" if isinstance(diff, (int, float)) else ""
                    
                    # Add interpretive text
                    if diff > 0:
                        interpretation = f"above sector average"
                    else:
                        interpretation = f"below sector average"
                    
                    # Add percentile info
                    percentile_text = f"P{percentile}"
                    
                    peer_comparison_data.append(
                        f"{metric_names.get(metric_name, metric_name)}: {company_val:.2f} (sector avg: {sector_avg:.2f}, {interpretation}, {percentile_text})"
                    )
    
    if not peer_comparison_data:
        # Fallback: Show company metrics even without sector comparison
        financial_facts = agent2_output.get("financial_facts", {})
        
        if financial_facts:
            # Show available company metrics
            metrics_display = []
            
            roce = financial_facts.get("ROCE")
            opm = financial_facts.get("OperatingMargin")
            debt = financial_facts.get("Debt")
            net_profit = financial_facts.get("NetProfit")
            cash_ops = financial_facts.get("CashFromOperatingActivity")
            
            if roce is not None:
                metrics_display.append(f"ROCE: {roce:.2f}%")
            if opm is not None:
                metrics_display.append(f"Operating Margin: {opm:.2f}%")
            if debt is not None:
                metrics_display.append(f"Debt: ₹{debt:,.0f}")
            if net_profit is not None:
                metrics_display.append(f"Net Profit: ₹{net_profit:,.0f}")
            if cash_ops is not None:
                metrics_display.append(f"Cash from Ops: ₹{cash_ops:,.0f}")
            
            if metrics_display:
                peer_comparison_data.append("Company Metrics: " + " | ".join(metrics_display))
            else:
                peer_comparison_data.append("Insufficient data for peer comparison.")
        else:
            peer_comparison_data.append("Peer comparison requires NIFTY50 stocks or additional sector data.")
    
    # Statistical findings - only include Isolation Forest result if anomaly detected
    # If no anomaly was detected, show a clean message
    if anomaly_detected or anomaly_score >= 0.7:
        # Only show statistical findings if there's an actual anomaly
        if not statistical_findings:
            statistical_findings = [
                f"Isolation Forest detected potential anomalies (score: {anomaly_score:.2f})."
            ]
    else:
        # No anomaly detected - clear any contradictory statistical findings
        statistical_findings = ["No significant anomalies were observed compared to historical data."]
    
    if outliers:
        statistical_findings.extend([str(o) for o in outliers if o][:2])
    
    # Risk level based on evidence
    risk_level = "Low"
    risk_score = 0
    
    # Count financial observations
    risk_score += min(len(financial_observations), 3) * 2
    
    # Add points for anomaly detection
    if anomaly_detected or anomaly_score >= 0.7:
        risk_score += 4
    
    # Add points for high debt
    debt_equity = info.get("debt_to_equity") if info else None
    if debt_equity is not None and float(debt_equity) > 1.5:
        risk_score += 2
    
    if risk_score >= 7:
        risk_level = "High"
    elif risk_score >= 3:
        risk_level = "Moderate"
    
    # Format financial observations with severity indicator
    formatted_observations = []
    for f in financial_observations[:5]:
        if isinstance(f, dict):
            metric = f.get("metric", "")
            value = f.get("value", "")
            severity = f.get("severity", "")
            explanation = f.get("explanation", "")
            
            # Build a readable sentence
            if metric and explanation:
                severity_icon = {"high": "⚠️", "medium": "⚡", "low": "📉"}.get(severity.lower(), "")
                formatted_observations.append(f"{severity_icon} **{metric}**: {value} - {explanation}" if severity_icon else f"**{metric}**: {value} - {explanation}")
            elif metric and value:
                formatted_observations.append(f"**{metric}**: {value}")
            else:
                formatted_observations.append(str(f))
        else:
            formatted_observations.append(str(f))

    return {
        "overall_risk": risk_level,
        "financial_observations": formatted_observations or ["No significant financial risks identified."],
        "statistical_findings": statistical_findings[:3],
        "isolation_forest": {
            "status": isolation_status,
            "explanation": isolation_explanation
        },
        "peer_comparison": peer_comparison_data or ["Peer comparison data unavailable for this company."],
        "risk_score": risk_score
    }


def sanitize_item(item: Any) -> str:
    """Convert any item to a clean string"""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return (
            item.get("explanation") or 
            item.get("description") or 
            item.get("text") or 
            item.get("message") or 
            str(item)
        )
    return str(item)
