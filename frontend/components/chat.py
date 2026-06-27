"""Chat component - Simple chat display."""

import streamlit as st


def render_chat(messages):
    if not messages:
        return
    
    for msg in messages[-8:]:
        role = "You" if msg["role"] == "user" else "Assistant"
        if role == "You":
            st.markdown(f"**{role}**: {msg['content']}")
        else:
            st.markdown(msg["content"])
