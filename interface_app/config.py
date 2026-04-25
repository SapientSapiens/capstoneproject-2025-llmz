# interface_app/config.py

"""
Central configuration for the Streamlit interface.
Author: Siddhartha Gogoi

This file keeps Streamlit secrets and local fallback values in one place,
instead of scattering st.secrets across the app like confetti at a bad wedding.
"""

import os
import streamlit as st


# -----------------------------
# Page configuration
# -----------------------------

PAGE_TITLE = "Survival Guidance Assistant"
PAGE_ICON = "🧭"
PAGE_LAYOUT = "wide"


# -----------------------------
# API configuration
# -----------------------------

def get_rag_api_url() -> str:
    """
    Return the RAG API URL.

    Priority:
    1. Streamlit Cloud secret: rag_api_url
    2. Local environment variable: RAG_API_URL
    3. Local fallback: http://localhost:8010
    """
    try:
        return st.secrets["rag_api_url"]
    except (KeyError, FileNotFoundError):
        return os.getenv("RAG_API_URL", "http://localhost:8010/query")


def get_feedback_api_url() -> str:
    """
    Return the feedback API URL.

    Priority:
    1. Streamlit Cloud secret: feedback_api_url
    2. Local environment variable: FEEDBACK_API_URL
    3. Empty string fallback

    Empty string is intentional so the calling function can raise a clear error.
    """
    try:
        return st.secrets["feedback_api_url"]
    except (KeyError, FileNotFoundError):
        return os.getenv("FEEDBACK_API_URL", "")


def get_api_key() -> str:
    """
    Return the API key used for both RAG and feedback API calls.

    Priority:
    1. Streamlit Cloud secret: api_key
    2. Local environment variable: RAG_API_KEY
    3. Empty string fallback

    Empty string is intentional so API client code can fail clearly.
    """
    try:
        return st.secrets["api_key"]
    except (KeyError, FileNotFoundError):
        return os.getenv("RAG_API_KEY", "")