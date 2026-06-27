"""Main Frontend - Company Workspace Interface."""

import io
import sys
import importlib
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import agent_4.agent as agent4

agent4 = importlib.reload(agent4)
import company_memory as company_memory_module
from agent_1.data_fetcher import fetch_all_data
try:
    from agent_1.data_fetcher import fetch_company_website_context
except Exception:
    fetch_company_website_context = None
from agent_2.agent import run_agent2
from agent_3.agent import run_agent3
from pipeline import run_pipeline, CACHE
from agent_1.tools.nifty50 import NIFTY50

st.set_page_config(page_title="AI Investment Research Assistant", layout="wide")

COMPANIES = {
    ticker.split(".")[0]: ticker for ticker, _ in NIFTY50
}


def init_session():
    st.session_state.setdefault("selected_company", None)
    st.session_state.setdefault("company_memory", {})
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("news_refresh_attempted", False)
    st.session_state.setdefault("period", "MAX")


def safe_display(value, prefix="", suffix=""):
    if value is None or (isinstance(value, float) and (pd.isna(value) or value != value)):
        return "N/A"
    if isinstance(value, (int, float)):
        return f"{prefix}{value:,.2f}{suffix}" if isinstance(value, float) else f"{prefix}{value}{suffix}"
    return f"{prefix}{value}{suffix}"


def format_large_number(value):
    if value is None or pd.isna(value):
        return "N/A"
    if value >= 1e12:
        return f"₹{value/1e12:.2f} L Cr"
    elif value >= 1e7:
        return f"₹{value/1e7:.2f} Cr"
    else:
        return f"₹{value:,.0f}"


def _first_number(*values):
    for value in values:
        if isinstance(value, (int, float)) and not pd.isna(value):
            return float(value)
    return None


def _as_number(value):
    if isinstance(value, (int, float)) and not pd.isna(value):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("%", "").strip()
        try:
            return float(cleaned)
        except Exception:
            return None
    return None


def _has_financial_signal(memory):
    metrics = (memory or {}).get("financial_metrics", {}) or {}
    info = (memory or {}).get("company_info", {}) or {}
    return any(
        _as_number(value) is not None
        for value in [
            metrics.get("roce"),
            metrics.get("operating_margin"),
            metrics.get("debt_to_equity"),
            metrics.get("current_ratio"),
            info.get("return_on_equity"),
            info.get("returnOnEquity"),
            info.get("operating_margins"),
            info.get("operatingMargins"),
            info.get("debtToEquity"),
            info.get("currentRatio"),
        ]
    )


def _stability_message(memory, model, red_flags):
    # Use Agent 4's context-aware pattern analysis
    pattern_analysis = agent4.explain_financial_pattern(memory)
    
    info = (memory or {}).get("company_info", {}) or {}
    metrics = (memory or {}).get("financial_metrics", {}) or {}
    facts = (memory or {}).get("financial_facts", {}) or {}
    news = (memory or {}).get("news_articles", []) or []
    peers = (memory or {}).get("peer_comparison", {}) or {}

    prediction = model.get("prediction")
    anomaly_score = model.get("anomaly_score")
    is_anomaly = pattern_analysis.get("status") == "unusual"

    reasons = []
    for label, value in [
        ("ROCE", _as_number(metrics.get("roce")) or _as_number(facts.get("ROCE")) or _as_number(info.get("returnOnEquity"))),
        ("Operating margin", _as_number(metrics.get("operating_margin")) or _as_number(facts.get("OperatingMargin")) or _as_number(info.get("operatingMargins"))),
        ("Debt to equity", _as_number(metrics.get("debt_to_equity")) or _as_number(info.get("debtToEquity"))),
        ("Current ratio", _as_number(metrics.get("current_ratio")) or _as_number(info.get("currentRatio"))),
    ]:
        if value is not None:
            reasons.append(f"{label}: {value:.2f}")

    for flag in red_flags[:3]:
        explanation = flag.get("explanation") or flag.get("metric")
        if explanation:
            reasons.append(explanation)

    news_items = []
    for article in news[:3]:
        headline_text = article.get("headline") or article.get("title")
        if headline_text:
            news_items.append(headline_text)

    peer_text = peers.get("sector") or info.get("sector")
    if peer_text:
        reasons.append(f"Peer context: {peer_text}")

    if news_items:
        reasons.append("Recent news:")
        reasons.extend([f"• {item}" for item in news_items])

    model_view = pattern_analysis.get("headline", "⚪ Limited data")
    
    # Build conclusion from Agent 4's analysis
    why_noticed = pattern_analysis.get("why_noticed", [])
    what_this_means = pattern_analysis.get("what_this_means", "")
    
    # Format why_noticed sections
    why_sections = []
    for item in why_noticed:
        if item:
            # Clean up and format each section
            why_sections.append(item.strip())
    
    if why_sections:
        conclusion = "\n\n".join(why_sections) + "\n\n" + what_this_means
    else:
        conclusion = what_this_means

    return model_view, reasons, conclusion


def render_company_selection():
    st.title("AI Investment Research Assistant")
    st.markdown("Select a NIFTY50 Company")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        company_name = st.selectbox(
            "",
            options=list(COMPANIES.keys()),
            index=0,
            label_visibility="collapsed"
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("Open Workspace"):
            st.session_state.selected_company = company_name
            load_company_data(company_name)
            st.rerun()


def load_company_data(company_name):
    ticker = COMPANIES.get(company_name)
    if not ticker:
        return
    
    with st.spinner("Loading company data..."):
        CACHE.pop(ticker.split(".")[0], None)
        agent1_output = fetch_all_data(ticker, days=30, news_limit=10)
        agent1_output["entities"] = [ticker]
        agent2_output = run_agent2(agent1_output, f"Give a full analysis of {company_name}.")
        agent3_output = run_agent3(agent1_output, f"Give a full analysis of {company_name}.")
        memory = company_memory_module.build_company_memory(
            agent1_output,
            agent2_output,
            agent3_output
        )
        company_memory_module.save_company_memory(memory)
        
        st.session_state.company_memory = memory
        st.session_state.chat_history = []
        st.session_state.news_refresh_attempted = False


def render_workspace():
    company = st.session_state.selected_company
    memory = st.session_state.company_memory

    if not memory.get("news_articles") and not st.session_state.get("news_refresh_attempted"):
        st.session_state.news_refresh_attempted = True
        load_company_data(company)
        memory = st.session_state.company_memory
    
    render_header(memory, company)
    
    st.markdown("---")
    
    col_left, col_right = st.columns([1.35, 0.85])
    
    with col_left:
        render_business_snapshot(memory, company)
        render_market_mood(memory, company)
    
    st.markdown("---")

    with col_left:
        render_price_story(memory, company)
    
    with col_right:
        render_news_evidence(memory)
        st.markdown("---")
        render_broader_drivers(memory)
        st.markdown("---")
        render_smart_prompts(memory, company)
    
    st.markdown("---")
    
    render_ai_assistant(company)
    
    st.markdown("---")
    
    if st.button("📄 Generate Investment Report PDF", type="primary", width="stretch"):
        st.session_state.show_report = True
        st.rerun()


def render_header(memory, company):
    info = memory.get('company_info', {})
    price = memory.get('price_data', {})
    chart = memory.get('chart_metrics', {})
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.header(f"{info.get('name', company.upper())}")
        st.caption(f"NSE: {info.get('ticker', company)}")
    
    with col2:
        current = price.get('current')
        if current is None:
            info_current = memory.get("company_info", {}).get("currentPrice")
            if info_current is None:
                info_current = memory.get("company_info", {}).get("regularMarketPrice")
            current = info_current
        if current is not None:
            returns = chart.get('returns', {})
            change_1d = returns.get('1D', 0) if returns else 0
            change_str = f"+{change_1d}%" if change_1d >= 0 else f"{change_1d}%"
            st.metric("", f"₹{current:,.2f}", change_str)
    
    st.caption(f"{datetime.now().strftime('%d %b, %I:%M %p')} IST")


def render_business_snapshot(memory, company):
    st.subheader("Business Fundamentals")
    metrics = memory.get("financial_metrics", {})
    facts = memory.get("financial_facts", {})
    peer = memory.get("peer_comparison", {})
    info = memory.get("company_info", {})
    anomaly = memory.get("anomaly_detection", {})
    red_flags = anomaly.get("red_flags", [])
    model = anomaly.get("model_assessment", {}) or {}

    roce = _first_number(
        metrics.get("roce"),
        facts.get("ROCE"),
        _as_number(info.get("return_on_equity")),
        info.get("return_on_equity"),
        info.get("returnOnEquity"),
    )
    opm = _first_number(
        metrics.get("operating_margin"),
        facts.get("OperatingMargin"),
        _as_number(info.get("operating_margins")),
        _as_number(info.get("operatingMargins")),
        info.get("operatingMargins"),
    )
    debt = _first_number(
        metrics.get("debt_to_equity"),
        facts.get("Debt"),
        _as_number(info.get("debt_to_equity")),
        _as_number(info.get("debtToEquity")),
        info.get("debtToEquity"),
    )
    current_ratio = _first_number(
        metrics.get("current_ratio"),
        facts.get("CurrentRatio"),
        _as_number(info.get("current_ratio")),
        _as_number(info.get("currentRatio")),
        info.get("currentRatio"),
    )
    cash_flow = _first_number(metrics.get("cash_flow"), facts.get("CashFromOperatingActivity"))

    with st.container(border=True):
        # Overall Assessment
        st.markdown("**Overall Assessment**")
        if roce is not None and debt is not None:
            if roce >= 15 and (isinstance(debt, (int, float)) and debt < 1):
                st.markdown("🟢 Strong")
                st.caption(f"{info.get('name', 'The company')} has strong financial fundamentals with healthy returns on capital and manageable debt levels.")
            elif roce >= 10:
                st.markdown("🟡 Moderate")
                st.caption(f"{info.get('name', 'The company')} has financially stable operations with reasonable returns on capital, though debt levels should be monitored.")
            else:
                st.markdown("🟡 Moderate")
                st.caption(f"{info.get('name', 'The company')} has financially stable operations supported by cash generation, though returns on capital remain below sector peers.")
        else:
            st.markdown("🟡 Moderate")
            st.caption(f"{info.get('name', 'The company')} has financially stable operations supported by available data.")

        # Strengths
        strengths = []
        if cash_flow is not None and isinstance(cash_flow, (int, float)) and cash_flow > 0:
            strengths.append("Strong Cash Generation")
            strengths.append("The company consistently generates healthy operating cash flow, helping fund investments and support existing debt.")
        
        if info.get("summary"):
            summary = info.get("summary", "").lower()
            if any(k in summary for k in ["diversified", "multiple", "various"]):
                strengths.append("Diversified Business Model")
                strengths.append("Revenue comes from multiple business lines, reducing dependence on a single segment.")
        
        if roce is not None and roce >= 20:
            strengths.append("High Capital Efficiency")
            strengths.append("Returns generated from invested capital are above many peers in the sector.")
        
        if debt is not None and isinstance(debt, (int, float)) and debt < 0.5:
            strengths.append("Conservative Leverage")
            strengths.append("Borrowing levels are low relative to equity, providing financial flexibility.")

        if strengths:
            st.markdown("**🏆 Strengths**")
            for i in range(0, len(strengths), 2):
                st.markdown(f"✅ {strengths[i]}")
                if i + 1 < len(strengths):
                    st.caption(strengths[i + 1])

        # Areas to Watch
        areas_to_watch = []
        if roce is not None and roce < 15:
            areas_to_watch.append("Capital Efficiency")
            areas_to_watch.append(f"Returns generated from invested capital are currently below many peers in the sector.")
        
        if debt is not None and isinstance(debt, (int, float)) and debt > 2:
            areas_to_watch.append("Debt Levels")
            areas_to_watch.append("Borrowing is relatively high, although current cash generation helps support these obligations.")
        
        if current_ratio is not None and isinstance(current_ratio, (int, float)) and current_ratio < 1.2:
            areas_to_watch.append("Liquidity")
            areas_to_watch.append("Short-term obligations may need monitoring as liquidity metrics are below healthy thresholds.")
        
        if opm is not None and opm < 10:
            areas_to_watch.append("Profit Margins")
            areas_to_watch.append("Operating margins are below 10%, indicating weaker profitability compared to stronger peers.")

        if areas_to_watch:
            st.markdown("**⚠ Areas to Watch**")
            for i in range(0, len(areas_to_watch), 2):
                st.markdown(f"⚠ {areas_to_watch[i]}")
                if i + 1 < len(areas_to_watch):
                    st.caption(areas_to_watch[i + 1])

        # AI Pattern Analysis
        st.markdown("**🤖 AI Pattern Analysis**")
        pattern_analysis = agent4.explain_financial_pattern(memory)
        headline = pattern_analysis.get("headline", "⚪ Limited data")
        
        st.markdown(headline)
        st.caption("**What stood out**")
        
        why_noticed = pattern_analysis.get("why_noticed", [])
        for item in why_noticed[:5]:
            if item:
                # Clean up the item and make it concise
                item = item.replace("**Why this stood out**", "").strip()
                item = item.replace(f"{info.get('name', 'The company')} operates as", "It operates as").strip()
                st.caption(f"• {item}")
        
        st.caption("**Interpretation**")
        what_this_means = pattern_analysis.get("what_this_means", "")
        if what_this_means:
            st.caption(what_this_means)

        # Overall
        st.markdown("**Overall**")
        overall_parts = []
        if roce is not None:
            if roce >= 20:
                overall_parts.append("profitability is strong")
            elif roce >= 10:
                overall_parts.append("profitability is moderate")
            else:
                overall_parts.append("profitability is weak")
        if debt is not None:
            if isinstance(debt, (int, float)) and debt < 1:
                overall_parts.append("debt looks comfortable")
            else:
                overall_parts.append("debt is elevated")
        if current_ratio is not None:
            overall_parts.append("liquidity is acceptable" if current_ratio >= 1.2 else "liquidity needs monitoring")
        if pattern_analysis.get("status") == "normal":
            overall_parts.append("financial profile is typical for the sector")
        
        if not overall_parts:
            overall_parts.append("the available data suggests stable fundamentals")
        
        st.markdown(f"The company appears financially stable overall, with {', '.join(overall_parts)}.")


def get_market_mood(memory):
    mood = agent4.interpret_market_intelligence(memory)
    label = mood["label"]
    if label == "Positive":
        return "🟢 Positive", mood["confidence"], mood["explanation"]
    if label == "Negative":
        return "🔴 Negative", mood["confidence"], mood["explanation"]
    if label == "Mixed":
        return "⚪ Mixed", mood["confidence"], mood["explanation"]
    return "⚪ Neutral", mood["confidence"], mood["explanation"]


def render_market_mood(memory, company):
    st.subheader("Market Mood")

    # Get market intelligence from Agent 4
    market_intel = agent4.explain_market(memory)
    
    # Get overall view from interpret_market_intelligence
    market_intel_struct = agent4.interpret_market_intelligence(memory)
    
    # Determine overall sentiment
    label = market_intel["label"]
    if label == "Positive":
        mood_label = "🟢 Positive"
    elif label == "Negative":
        mood_label = "🔴 Negative"
    elif label == "Mixed":
        mood_label = "🟡 Mixed"
    else:
        mood_label = "🟡 Cautiously Positive"

    st.markdown(f"**Overall View**")
    st.caption(mood_label)
    st.caption(market_intel.get("explanation", "The market view is mixed and should be read alongside the fundamentals."))

    # Positive Signals
    opportunities = memory.get("opportunities", [])
    news = memory.get("news_articles", [])
    analyst = memory.get("analyst_data", {})
    risks = memory.get("risks", [])

    positive_signals = []
    
    if analyst.get("recommendation_key") or analyst.get("recommendationKey"):
        rec = (analyst.get("recommendation_key") or analyst.get("recommendationKey") or "").title()
        positive_signals.append(("Analyst consensus", f"Analyst consensus is {rec}"))
    
    if opportunities:
        positive_signals.append(("Business momentum", opportunities[0] if opportunities else ""))
    
    # Check for positive news
    for article in news[:3]:
        headline = article.get("headline") or article.get("title") or ""
        summary = article.get("summary") or ""
        text = (headline + " " + summary).lower()
        if any(k in text for k in ["upside", "growth", "expansion", "launch", "strong", "beat", "increase"]):
            positive_signals.append(("Recent news", headline))

    if positive_signals:
        st.markdown("**✅ Positive Signals**")
        for item in positive_signals[:3]:
            st.caption(f"• {item[1]}")

    # Things Creating Uncertainty
    uncertainty_factors = []
    
    # Check for negative signals
    for article in news[:3]:
        headline = article.get("headline") or article.get("title") or ""
        summary = article.get("summary") or ""
        text = (headline + " " + summary).lower()
        if any(k in text for k in ["fall", "slip", "decline", "weak", "pressure", "risk", "down"]):
            uncertainty_factors.append(("Recent news", headline))
    
    if risks:
        uncertainty_factors.append(("Financial risk", risks[0]))
    
    # Check chart trend
    chart = memory.get("chart_metrics", {})
    if chart.get("trend") == "down":
        uncertainty_factors.append(("Price trend", "Stock has underperformed recently"))
    
    # Check sector performance
    market_drivers = memory.get("market_drivers", {})
    sector = market_drivers.get("sector_performance", {})
    if sector.get("sector_return_1mo") is not None and sector.get("sector_return_1mo", 0) < 0:
        uncertainty_factors.append(("Sector trends", "Sector has lagged the broader market"))

    if uncertainty_factors:
        st.markdown("**⚠ Things Creating Uncertainty**")
        for item in uncertainty_factors[:3]:
            st.caption(f"• {item[1]}")

    # What the Market is Watching
    st.markdown("**What the Market is Watching**")
    watch_items = []
    
    # Upcoming events
    events = memory.get("events", [])
    if events:
        watch_items.append(("Upcoming events", events[0].get("title", "Corporate developments")))
    
    # Analyst targets
    analyst = memory.get("analyst_data", {})
    target_price = analyst.get("target_mean_price") or analyst.get("targetMeanPrice")
    if target_price:
        watch_items.append(("Analyst target price", f"Target: ₹{target_price:,.0f}"))
    
    # Sector performance
    if sector.get("sector_return_1mo") is not None:
        watch_items.append(("Sector trends", f"Sector return: {sector['sector_return_1mo']}%"))
    
    # Recent events
    if events:
        watch_items.append(("Upcoming quarterly results", "Market awaitst quarterly earnings"))
    
    if watch_items:
        for item in watch_items[:4]:
            st.caption(f"• {item[1]}")
    else:
        st.caption("• Recent earnings and business developments")
        st.caption("• Sector performance trends")

    # Bottom Line
    st.markdown("**Bottom Line**")
    bottom_line_parts = []
    
    if label in ["Positive", "Mixed"]:
        bottom_line_parts.append("Market sentiment remains constructive")
    else:
        bottom_line_parts.append("Market sentiment is cautious")
    
    if analyst.get("recommendation_key") in ["buy", "strong_buy"]:
        bottom_line_parts.append("supported by positive analyst views")
    
    if chart.get("trend") != "up":
        bottom_line_parts.append("but weaker price momentum indicates investors are waiting for stronger evidence")
    
    st.caption(" ".join(bottom_line_parts) + ".")


def render_price_story(memory, company):
    st.subheader("Price Story")
    
    price = memory.get('price_data', {})
    chart = memory.get('chart_metrics', {})
    market = memory.get('market_stats', {})
    price_view = agent4.explain_chart(memory)
    
    if price.get('ohlcv'):
        df = pd.DataFrame(price['ohlcv'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        
        # Get selected period from session state or default to MAX
        period = st.session_state.get('period', 'MAX')
        st.caption(f"Showing {period} price history")
        
        # Filter dataframe based on period
        if period == '1D':
            df = df.tail(2)
        elif period == '1W':
            df = df.tail(7)
        elif period == '1M':
            df = df.tail(22)
        elif period == '6M':
            df = df.tail(126)
        elif period == '1Y':
            df = df.tail(252)
        elif period == '5Y':
            df = df.tail(1260)
        # MAX shows all data (default)
        
        col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
        with col1:
            if st.button("1D", key="btn_1d"):
                st.session_state.period = "1D"
                st.rerun()
        with col2:
            if st.button("1W", key="btn_1w"):
                st.session_state.period = "1W"
                st.rerun()
        with col3:
            if st.button("1M", key="btn_1m"):
                st.session_state.period = "1M"
                st.rerun()
        with col4:
            if st.button("6M", key="btn_6m"):
                st.session_state.period = "6M"
                st.rerun()
        with col5:
            if st.button("1Y", key="btn_1y"):
                st.session_state.period = "1Y"
                st.rerun()
        with col6:
            if st.button("5Y", key="btn_5y"):
                st.session_state.period = "5Y"
                st.rerun()
        with col7:
            if st.button("MAX", key="btn_max"):
                st.session_state.period = "MAX"
                st.rerun()

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            increasing_line_color="#1f9d55",
            decreasing_line_color="#e11d48",
            name="Price"
        ))
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["close"],
                mode="lines",
                name="Close",
                line=dict(color="#2563eb", width=2),
                fill="tozeroy",
                fillcolor="rgba(37, 99, 235, 0.12)",
                hoverinfo="skip",
            )
        )

        fig.update_layout(
            height=460,
            margin=dict(l=10, r=10, t=24, b=10),
            xaxis_title="",
            yaxis_title="Price (₹)",
            xaxis_rangeslider_visible=False,
            showlegend=False,
            template="plotly_white",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            hovermode="x unified",
        )
        fig.update_xaxes(
            showgrid=False,
            tickformat="%b %d",
            rangeselector=dict(
                buttons=list([
                    dict(count=7, label="1W", step="day", stepmode="backward"),
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(step="all", label="MAX"),
                ])
            ),
        )
        fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.06)")

        st.plotly_chart(fig, use_container_width=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open", safe_display(price.get('open'), prefix="₹"))
    with col2:
        st.metric("Day High", safe_display(price.get('day_high'), prefix="₹"))
    with col3:
        st.metric("Day Low", safe_display(price.get('day_low'), prefix="₹"))
    with col4:
        st.metric("Market Cap", format_large_number(market.get('market_cap')))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("P/E Ratio", safe_display(market.get('pe_ratio')))
    with col2:
        st.metric("52W High", safe_display(price.get('high_52w'), prefix="₹"))
    with col3:
        st.metric("52W Low", safe_display(price.get('low_52w'), prefix="₹"))
    with col4:
        st.metric("Dividend Yield", safe_display(market.get('dividend_yield'), suffix="%"))
    
    st.markdown("**Price Story**")
    st.info(agent4.price_story_summary(memory))
    
    returns = chart.get('returns', {})
    if returns:
        st.markdown("**Returns**")
        cols = st.columns(5)
        def _fmt_return(value):
            return "N/A" if value is None else f"{value}%"
        with cols[0]:
            st.metric("1D", _fmt_return(returns.get('1D')))
        with cols[1]:
            st.metric("1M", _fmt_return(returns.get('1M')))
        with cols[2]:
            st.metric("6M", _fmt_return(returns.get('6M')))
        with cols[3]:
            st.metric("1Y", _fmt_return(returns.get('1Y')))
        with cols[4]:
            st.metric("5Y", _fmt_return(returns.get('5Y')))
    
    ma = chart.get('moving_averages', {})
    sr = chart.get('support_resistance', {})
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Support / Resistance**")
        if sr.get('support_1') is not None:
            st.write(f"Support: ₹{sr['support_1']:,.2f}")
        if sr.get('resistance_1') is not None:
            st.write(f"Resistance: ₹{sr['resistance_1']:,.2f}")
        if ma.get('50dma') is not None:
            st.write(f"50 DMA: ₹{ma['50dma']:,.2f}")
        if ma.get('200dma') is not None:
            st.write(f"200 DMA: ₹{ma['200dma']:,.2f}")

    with col2:
        st.markdown("**Trend**")
        if chart.get('trend'):
            st.write(chart['trend'].title())
        if chart.get('volatility') is not None:
            st.write(f"Volatility: {chart['volatility']:.2f}")


def render_news_evidence(memory):
    st.subheader("News & Events")

    articles = memory.get('news_articles', [])
    intelligence = memory.get('market_intelligence', {})
    top = agent4.top_news_summary(memory)
    if top:
        st.markdown("**Top Developments**")
        for item in top[:3]:
            st.caption(item)
    
    if not articles:
        st.info("No recent news was returned by the available sources.")
        st.caption("That usually means the source feed was empty or the article text could not be parsed cleanly.")
        return

    with st.expander("Show all news ↓"):
        for article in articles:
            headline = article.get('headline', 'No title')
            source = article.get('source', 'Source')
            summary = article.get('summary', '')
            url = article.get('url', '')
            date = article.get('date', '')

            with st.container(border=True):
                st.markdown(f"**{headline}**")
                meta = source
                if date:
                    meta = f"{meta} | {date}"
                st.caption(meta)
                if summary:
                    st.caption(summary if len(summary) <= 220 else summary[:220] + "...")
                if url:
                    st.markdown(f"[Read →]({url})")


def render_broader_drivers(memory):
    st.subheader("Broader Drivers")
    drivers = memory.get("market_drivers", {})
    macro = drivers.get("macro", {})
    sector = drivers.get("sector_performance", {})
    earnings = drivers.get("earnings", {})
    corp = drivers.get("corporate_actions", {})
    promoter = drivers.get("promoter_activity", {})

    with st.container(border=True):
        st.markdown("**Macro**")
        if macro:
            if macro.get("nifty50_return_1mo") is not None:
                st.caption(f"Nifty 50 1M: {macro['nifty50_return_1mo']}%")
            if macro.get("usd_inr") is not None:
                st.caption(f"USD/INR: {macro['usd_inr']}")
            if macro.get("crude") is not None:
                st.caption(f"Crude: {macro['crude']}")
        else:
            st.caption("No macro feed available.")

        st.markdown("**Sector**")
        if sector:
            if sector.get("sector_return_1mo") is not None:
                st.caption(f"Sector 1M return: {sector['sector_return_1mo']}%")
            if sector.get("peer_count") is not None:
                st.caption(f"Peer count: {sector['peer_count']}")
        else:
            st.caption("No sector feed available.")

        st.markdown("**Ownership / Actions**")
        if earnings.get("earnings_date"):
            st.caption(f"Earnings reference: {earnings['earnings_date']}")
        if corp.get("dividend_rate") is not None:
            st.caption(f"Dividend rate: {corp['dividend_rate']}")
        if corp.get("recent_actions"):
            st.caption(f"Recent corporate actions: {len(corp['recent_actions'])}")

        st.markdown("**Ownership**")
        if promoter.get("held_percent_insiders") is not None:
            st.caption(f"Insiders: {promoter['held_percent_insiders']}")
        if promoter.get("held_percent_institutions") is not None:
            st.caption(f"Institutions: {promoter['held_percent_institutions']}")
        if not any([macro, sector, earnings, corp, promoter]):
            st.caption("No broader driver data available yet.")


def render_ai_assistant(company):
    st.subheader("AI Assistant")
    
    user_input = st.text_input(
        f"Ask anything about {company}...",
        key="chat_input",
        placeholder="Ask about the company..."
    )
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("Ask", key="ask_button"):
            if user_input:
                answer_question(user_input, company)
    
    history = st.session_state.chat_history
    if history:
        for msg in history[-4:]:
            role = "You" if msg["role"] == "user" else "Assistant"
            if role == "You":
                st.markdown(f"**You**: {msg['content']}")
            else:
                st.markdown(msg["content"])
            st.markdown("---")
    
    st.markdown("**Try asking:**")
    examples = [
        f"Why is debt high for {company}?",
        "What is ROCE?",
        f"Can {company} do well over 5 years?",
        "Why has the stock fallen?",
    ]
    for ex in examples:
        st.write(f"- {ex}")


def answer_question(question, company):
    ticker = COMPANIES.get(company)
    
    with st.spinner("Thinking..."):
        result = run_pipeline(question, ticker=ticker)
        
        # Agent 4 is now called inside run_pipeline
        response = result.get("agent4_output", {}).get("response", "Unable to answer")
        
        st.session_state.chat_history.append({"role": "user", "content": question})
        st.session_state.chat_history.append({"role": "assistant", "content": response})


def _needs_website_fallback(question, response, memory):
    text = (question or "").lower()
    response_text = (response or "").lower()
    if any(k in text for k in ["biggest investment", "where is", "capital allocated", "putting most of its capital", "capital allocation"]):
        if any(k in response_text for k in ["does not point to one single biggest investment bucket", "could not", "limited", "diversified capital program"]):
            return True
        if not memory.get("website_context", {}).get("pages"):
            return True
    return False


def render_smart_prompts(memory, company):
    st.subheader("💡 Smart Prompts")
    
    # Generate suggested questions based on company data
    suggested_questions = agent4.generate_suggested_questions(memory, company)
    
    for question in suggested_questions:
        if st.button(f"💬 {question}"):
            answer_question(question, company)


def render_report():
    memory = st.session_state.company_memory
    company = st.session_state.selected_company
    info = memory.get("company_info", {})
    market = memory.get("market_stats", {})
    drivers = memory.get("market_drivers", {})
    price = memory.get("price_data", {})
    chart = memory.get("chart_metrics", {})
    news = memory.get("news_articles", [])
    risks = memory.get("risks", [])
    opportunities = memory.get("opportunities", [])
    thesis = agent4.build_investment_thesis(memory, 5)
    business_model = info.get("business_model", [])
    peers = info.get("peers", [])
    market_view = agent4.explain_market(memory)
    price_story = agent4.price_story_summary(memory)
    business_snapshot = agent4.explain_business_snapshot(memory)
    price_mood = agent4.explain_chart(memory)

    st.title(f"Investment Report: {company}")
    
    if st.button("Back to Workspace"):
        st.session_state.show_report = False
        st.rerun()
    
    st.markdown("---")
    pdf_bytes = build_report_pdf_bytes(memory, company)
    st.download_button(
        "Download PDF",
        data=pdf_bytes,
        file_name=f"{company}_investment_report.pdf",
        mime="application/pdf",
        width="stretch",
    )
    st.markdown("---")
    render_report_section(
        "1. Executive Summary",
        [
            f"Company Name: {info.get('name', company)}",
            f"Sector: {info.get('sector', 'N/A')}",
            f"Industry: {info.get('industry', 'N/A')}",
            f"Current Price: ₹{price.get('current'):,.2f}" if price.get("current") is not None else "Current Price: N/A",
            f"Overall View: {market_view.get('mood', 'Mixed')}",
            "",
            f"{info.get('name', company)} is a leading player in the {info.get('industry', 'its industry')} industry. Recent developments, financial performance, and market sentiment suggest a {market_view.get('mood', 'Mixed')} outlook. Investors should balance growth opportunities against the key risks discussed below.",
        ],
    )
    render_report_section(
        "2. Business Overview",
        [
            f"What does the company do? {agent4.answer_business_description(info.get('name', company), memory)['response']}",
            "Competitive Advantages:",
            *(_bulletize_list([
                "Brand strength" if any(term in (info.get("summary", "").lower()) for term in ["brand", "consumer", "retail"]) else None,
                "Market leadership" if info.get("sector") else None,
                "Distribution network" if any(term in (info.get("summary", "").lower()) for term in ["stores", "distribution", "network", "retail"]) else None,
                "Technology leadership" if any(term in (info.get("summary", "").lower()) for term in ["digital", "technology", "platform"]) else None,
                "Cost advantages" if any(term in (info.get("summary", "").lower()) for term in ["scale", "efficient", "integrated"]) else None,
            ])),
        ],
    )
    render_report_section(
        "3. Business Strengths",
        _bulletize_list(_business_strengths(memory)),
    )
    render_report_section(
        "4. Key Risks",
        _bulletize_list(_key_risks(memory)),
    )
    render_report_section(
        "5. Financial Health",
        _financial_health_lines(memory) + ["", "Stability:", *_stability_lines(memory)],
    )
    render_report_section(
        "6. Market Intelligence",
        _market_intelligence_lines(memory),
    )
    render_report_section(
        "7. Price Story",
        [
            f"Current valuation: P/E {market.get('pe_ratio', 'N/A')}",
            f"Trend: {chart.get('trend', 'sideways').title()}",
            price_story,
        ],
    )
    render_report_section(
        "8. Long-Term Outlook (0-5 Years)",
        _long_term_outlook_lines(memory, thesis),
    )
    render_report_section(
        "9. Suitable For",
        _suitable_for_lines(thesis),
    )
    render_report_section(
        "10. Things To Monitor",
        _things_to_monitor_lines(memory, thesis),
    )
    render_report_section(
        "11. Counter Arguments",
        _counter_arguments_lines(memory, thesis),
    )
    render_report_section(
        "12. Final Investment Thesis",
        [_final_thesis_line(memory, thesis, market_view)],
    )
    
    st.markdown("*Note: This is not investment advice. Consult a financial advisor.*")


def build_report_pdf_bytes(memory, company):
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        sections = build_report_sections(memory, company)
        for section_title, section_lines in sections:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.patch.set_facecolor("white")
            text = f"{section_title}\n\n" + "\n".join(section_lines)
            fig.text(0.06, 0.96, text, va="top", fontsize=10, family="DejaVu Sans")
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()


def render_report_section(title, lines):
    st.markdown(f"## {title}")
    for line in lines:
        if not line:
            st.markdown("")
        elif line.startswith("• ") or line.startswith("✓ ") or line.startswith("✗ "):
            st.markdown(line)
        else:
            st.markdown(line)


def build_report_sections(memory, company):
    info = memory.get("company_info", {})
    market = memory.get("market_stats", {})
    price = memory.get("price_data", {})
    chart = memory.get("chart_metrics", {})
    news = memory.get("news_articles", [])
    thesis = agent4.build_investment_thesis(memory, 5)
    market_view = agent4.explain_market(memory)
    business_desc = agent4.answer_business_description(info.get("name", company), memory)["response"]
    price_story = agent4.price_story_summary(memory)

    executive = [
        f"Company Name: {info.get('name', company)}",
        f"Sector: {info.get('sector', 'N/A')}",
        f"Industry: {info.get('industry', 'N/A')}",
        f"Current Price: ₹{price.get('current'):,.2f}" if price.get("current") is not None else "Current Price: N/A",
        f"Overall View: {market_view.get('mood', 'Mixed')}",
        "",
        f"{info.get('name', company)} is a leading player in the {info.get('industry', 'its industry')} industry. Recent developments, financial performance, and market sentiment suggest a {market_view.get('mood', 'Mixed')} outlook. Investors should balance growth opportunities against the key risks discussed below.",
    ]

    business_overview = [
        f"What does the company do? {business_desc}",
        "",
        "Competitive Advantages:",
        *_bulletize_list([
            "Brand strength" if any(term in (info.get("summary", "").lower()) for term in ["brand", "consumer", "retail"]) else None,
            "Market leadership" if info.get("sector") else None,
            "Distribution network" if any(term in (info.get("summary", "").lower()) for term in ["stores", "distribution", "network", "retail"]) else None,
            "Technology leadership" if any(term in (info.get("summary", "").lower()) for term in ["digital", "technology", "platform"]) else None,
            "Cost advantages" if any(term in (info.get("summary", "").lower()) for term in ["scale", "efficient", "integrated"]) else None,
        ]),
    ]

    sections = [
        ("1. Executive Summary", executive),
        ("2. Business Overview", business_overview),
        ("3. Business Strengths", _business_strengths(memory)),
        ("4. Key Risks", _key_risks(memory)),
        ("5. Financial Health", _financial_health_lines(memory)),
        ("6. Market Intelligence", _market_intelligence_lines(memory)),
        ("7. Price Story", [
            f"Current valuation: P/E {market.get('pe_ratio', 'N/A')}",
            f"Trend: {chart.get('trend', 'sideways').title()}",
            price_story,
        ]),
        ("8. Long-Term Outlook (0-5 Years)", _long_term_outlook_lines(memory, thesis)),
        ("9. Suitable For", _suitable_for_lines(thesis)),
        ("10. Things To Monitor", _things_to_monitor_lines(memory, thesis)),
        ("11. Counter Arguments", _counter_arguments_lines(memory, thesis)),
        ("12. Final Investment Thesis", [_final_thesis_line(memory, thesis, market_view)]),
    ]
    return sections


def _bulletize_list(items):
    return [f"• {item}" for item in items if item]


def _business_strengths(memory):
    strengths = []
    thesis = agent4.build_investment_thesis(memory, 5)
    for item in thesis.get("positive_signals", [])[:4]:
        strengths.append(item)
    if memory.get("company_info", {}).get("summary"):
        strengths.append("Diversified business model")
    if memory.get("market_stats", {}).get("market_cap"):
        strengths.append("Scale advantage")
    return strengths or ["Limited structured strengths data was available, but the company remains covered by recent market and financial signals."]


def _key_risks(memory):
    thesis = agent4.build_investment_thesis(memory, 5)
    risks = thesis.get("risks", [])[:5]
    return risks or ["No major structured red flags were returned, but execution, valuation, and sector cycles should still be monitored."]


def _financial_health_lines(memory):
    metrics = memory.get("financial_metrics", {})
    info = memory.get("company_info", {})
    facts = memory.get("financial_facts", {})
    question = []

    def _assessment(value, strong, moderate):
        if value is None:
            return None
        return strong if strong(value) else moderate if moderate(value) else "Weak"

    roce = metrics.get("roce") or facts.get("ROCE") or info.get("returnOnEquity")
    opm = metrics.get("operating_margin") or facts.get("OperatingMargin") or info.get("operatingMargins")
    debt = metrics.get("debt_to_equity") or info.get("debtToEquity")
    current_ratio = metrics.get("current_ratio") or info.get("currentRatio")
    cash_flow = metrics.get("cash_flow") or info.get("freeCashflow")

    question.append(f"Profitability: {'Strong' if _as_number(opm) and _as_number(opm) >= 15 or _as_number(roce) and _as_number(roce) >= 20 else 'Moderate' if _as_number(opm) or _as_number(roce) else 'Weak'}")
    question.append(f"Debt Position: {'Elevated' if _as_number(debt) and _as_number(debt) >= 1 else 'Healthy' if _as_number(debt) is not None else 'Moderate'}")
    question.append(f"Liquidity: {'Healthy' if _as_number(current_ratio) and _as_number(current_ratio) >= 1.5 else 'Moderate' if _as_number(current_ratio) else 'Weak'}")
    question.append(f"Cash Generation: {'Strong' if cash_flow is not None and cash_flow > 0 else 'Moderate' if cash_flow is not None else 'Weak'}")
    question.append(f"Financial Stability: {'Warning' if memory.get('anomaly_detection', {}).get('anomaly_score') not in (None, 0) else 'Normal'}")
    return question


def _market_intelligence_lines(memory):
    drivers = memory.get("market_drivers", {})
    news = memory.get("news_articles", [])
    analyst = memory.get("analyst_data", {})
    positives = []
    concerns = []
    if news:
        for art in news[:4]:
            headline = art.get("headline") or art.get("title")
            if headline:
                positives.append(headline)
    if analyst.get("recommendation_key") or analyst.get("recommendationKey"):
        positives.append(f"Analyst recommendation: {(analyst.get('recommendation_key') or analyst.get('recommendationKey')).title()}")
    if drivers.get("market_drivers"):
        positives.append("Broader market drivers are available.")
    if memory.get("risks"):
        concerns.extend(memory.get("risks")[:4])
    if not positives:
        positives = ["No recent positive drivers were returned."]
    if not concerns:
        concerns = ["No major negative drivers were returned."]
    return ["Positive Drivers:"] + _bulletize_list(positives) + ["", "Concerns:"] + _bulletize_list(concerns)


def _long_term_outlook_lines(memory, thesis):
    lines = []
    for item in thesis.get("growth_drivers", [])[:5]:
        lines.append(f"• {item}")
    if not lines:
        lines.append("• Growth drivers are still being refined from the available news and financial data.")
    for item in thesis.get("risks", [])[:3]:
        lines.append(f"• Challenge: {item}")
    return lines


def _suitable_for_lines(thesis):
    return _bulletize_list(thesis.get("investor_fit", [])[:4]) + ["" ] + _bulletize_list(thesis.get("less_suitable", [])[:3])


def _things_to_monitor_lines(memory, thesis):
    items = []
    info = memory.get("company_info", {})
    market = memory.get("market_stats", {})
    chart = memory.get("chart_metrics", {})
    if info.get("revenue_growth") is not None:
        items.append(f"Earnings / revenue growth: {info.get('revenue_growth')}")
    if market.get("pe_ratio") is not None:
        items.append(f"Valuation (P/E): {market.get('pe_ratio')}")
    if chart.get("volatility") is not None:
        items.append(f"Volatility: {chart.get('volatility')}")
    if info.get("debtToEquity") is not None:
        items.append(f"Debt: {info.get('debtToEquity')}")
    for item in thesis.get("risks", [])[:3]:
        items.append(item)
    return _bulletize_list(items) or ["• Watch earnings, margins, debt, and news flow."]


def _counter_arguments_lines(memory, thesis):
    args = []
    market = memory.get("market_stats", {})
    info = memory.get("company_info", {})
    if market.get("pe_ratio") and market.get("pe_ratio") > 25:
        args.append("Expensive valuation.")
    if info.get("debtToEquity") and info.get("debtToEquity") >= 1:
        args.append("High debt.")
    if memory.get("chart_metrics", {}).get("trend") == "down":
        args.append("Weak price momentum.")
    if not args:
        args.extend(["Execution risk.", "Sector cyclicality.", "Broader market volatility."])
    return _bulletize_list(args)


def _final_thesis_line(memory, thesis, market_view):
    profile = "fundamentally strong" if len(thesis.get("positive_signals", [])) >= len(thesis.get("risks", [])) else "moderate"
    outlook = "positive" if market_view.get("mood", "").startswith("🟢") else "mixed" if market_view.get("mood", "").startswith("🟡") else "cautious"
    comp = memory.get("company_info", {}).get("name", "The company")
    sector = memory.get("company_info", {}).get("sector", "its sector")
    return (
        f"{comp} appears to be a fundamentally {profile} business with several long-term growth opportunities. "
        f"While risks such as valuation, leverage, and sector cycles deserve monitoring, the company's competitive position "
        f"and financial profile support a {outlook} long-term outlook. It may be suitable for investors seeking "
        f"{thesis.get('investor_fit', ['long-term compounding'])[0] if thesis.get('investor_fit') else 'long-term compounding'}, "
        f"although future returns will depend on execution and broader market conditions."
    )


def _stability_lines(memory):
    model = memory.get("anomaly_detection", {}) or {}
    red_flags = model.get("red_flags", []) or []
    headline, reasons, conclusion = _stability_message(memory, model, red_flags)
    lines = [headline, conclusion]
    lines.extend(reasons[:8])
    return lines


def main():
    init_session()
    
    if st.session_state.get("show_report"):
        render_report()
        return
    
    if not st.session_state.selected_company:
        render_company_selection()
    else:
        render_workspace()


if __name__ == "__main__":
    main()
