# interface_app/ui/header.py

"""
Header UI component for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file renders the top section of the app:
- author credit
- app title
- short description

For now, this keeps the header isolated from app.py so the main file does not become a landfill.
"""

import streamlit as st

from config import PAGE_TITLE


def render_header() -> None:
    """
    Render the application header.

    This is intentionally kept as a separate function so the visual identity
    of the app can evolve without disturbing chat, feedback, or API logic.
    """

    st.markdown(
        """
        <div style="
            font-size: 13px;
            color: #d4af37;
            font-weight: 700;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        ">
            Authored by Siddhartha Gogoi
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.title(f"🧭 {PAGE_TITLE}")

    st.caption(
        "Ask about survival — storms, jungles, quicksand, disasters, health, "
        "diseases, or epidemics. Get data-driven answers grounded in the current "
        "RAG knowledge base."
    )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)