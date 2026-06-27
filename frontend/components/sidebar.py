"""Sidebar component - Minimal UI for company selection."""

import streamlit as st
from agent_1.tools.nifty50 import NIFTY50

COMPANIES = [ticker.split(".")[0] for ticker, _ in NIFTY50]


def render_sidebar():
    with st.sidebar:
        st.title("Research Assistant")
        st.caption("AI-powered investment research for retail investors")
        
        st.markdown("---")
        
        st.markdown("### How it works")
        st.markdown("1. Select a company")
        st.markdown("2. View the workspace")
        st.markdown("3. Ask questions")
        st.markdown("4. Generate report if needed")
        
        st.markdown("---")
        
        if st.button("Start Fresh"):
            st.session_state.selected_company = None
            st.session_state.company_memory = {}
            st.session_state.chat_history = []
            st.session_state.show_report = False
            st.rerun()
    
    return ""
