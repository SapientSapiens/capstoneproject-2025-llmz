# interface_app/app.py

"""
Streamlit entry point for the Survival Guidance Assistant.

Author: Siddhartha Gogoi

Purpose:
This file should remain thin.

It only:
1. configures the Streamlit page,
2. initializes session state,
3. lays out the page,
4. calls UI components.

Actual logic lives in:
- config.py
- state.py
- api_client.py
- feedback_client.py
- ui/header.py
- ui/chat_panel.py
- ui/feedback_panel.py

This keeps the Streamlit entry point clean instead of turning it into
one giant procedural swamp. We are trying to build software, not khichdi.
"""

import streamlit as st

from config import PAGE_ICON, PAGE_LAYOUT, PAGE_TITLE
from state import initialize_session_state
from ui.chat_panel import render_chat_panel
from ui.feedback_panel import render_feedback_panel
from ui.header import render_header


# -----------------------------
# Streamlit page configuration
# -----------------------------
# This must be called before rendering any Streamlit UI elements.
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=PAGE_LAYOUT,
)


# -----------------------------
# Session state initialization
# -----------------------------
# Streamlit reruns this script after user actions.
# Session state keeps chat history and feedback state alive across reruns.
initialize_session_state()


# -----------------------------
# Header section
# -----------------------------
render_header()


# -----------------------------
# Main layout
# -----------------------------
# Left column: chat interface
# Middle column: visual spacing
# Right column: feedback panel
chat_col, spacer_col, feedback_col = st.columns([3.5, 0.4, 1.6])


with chat_col:
    render_chat_panel()


with spacer_col:
    # Intentional empty spacer column for better visual separation.
    st.empty()


with feedback_col:
    render_feedback_panel()