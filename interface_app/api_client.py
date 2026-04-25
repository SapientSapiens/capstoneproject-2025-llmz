# interface_app/api_client.py

"""
RAG API client for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file isolates all HTTP/HTTPS communication with the existing RAG backend.
No backend fantasy renovation is happening here. Civilization gets one mercy.

"""

import requests
import streamlit as st
from config import get_api_key, get_rag_api_url

# Header name expected by the backend for session continuity.
SESSION_HEADER_NAME = "X-Session-ID"

# Streamlit session_state key where the frontend stores the current RAG session ID.
SESSION_STATE_KEY = "rag_session_id"

def _get_current_session_id() -> str:
    """
    Return the current RAG session ID stored in Streamlit session state.

    If this is the first request, no session ID exists yet, so return an empty string.
    """

    return st.session_state.get(SESSION_STATE_KEY, "")

def _store_session_id_from_response(response: requests.Response, data: dict | None = None) -> None:
    """
    Store the RAG session ID returned by the backend.

    The backend may return the session ID in a response header or in the JSON body.
    This function checks both, without changing the backend contract.

    Checked locations:
    1. Response header: X-Session-ID
    2. Response header: x-session-id
    3. JSON body: session_id
    4. JSON body: query_session_id
    5. JSON body: x_session_id
    """

    session_id = (
        response.headers.get("X-Session-ID")
        or response.headers.get("x-session-id")
    )

    if not session_id and isinstance(data, dict):
        session_id = (
            data.get("session_id")
            or data.get("query_session_id")
            or data.get("x_session_id")
        )

    if session_id:
        st.session_state[SESSION_STATE_KEY] = session_id


def ask_rag_api(question: str) -> tuple[str, str]:
    """
    Send the user's question to the existing RAG API.

    Args:
        question:
            The raw user question entered in the Streamlit chat input.

    Returns:
        A tuple:
            (assistant_reply, status)

        status can be:
            SUCCESS
            API_ERROR
            CONNECTION_ERROR
    """

    api_url = get_rag_api_url()
    api_key = get_api_key()
    session_id = _get_current_session_id()

    headers = {
        "X-API-Key": api_key,
    }

    # Send the previous backend session ID if one exists.
    # This is what enables backend-side conversation history and query rewriting.
    if session_id:
        headers[SESSION_HEADER_NAME] = session_id

    payload = {
        "question": question,
    }

    try:
        response = requests.post(
            api_url,
            json=payload,
            headers=headers,
            timeout=60,
        )

        data = None

        # Try to parse JSON only if possible.
        try:
            data = response.json()
        except ValueError:
            data = None

        # Store session ID even if the response is non-200.
        # Some backends still return useful headers on error.
        _store_session_id_from_response(response, data)

        if response.status_code == 200:
            if isinstance(data, dict):
                assistant_reply = data.get(
                    "answer",
                    "⚠️ No answer returned by service.",
                )
            else:
                assistant_reply = "⚠️ Invalid JSON response returned by service."

            return assistant_reply, "SUCCESS"

        error_message = f"❌ Error: {response.status_code} - {response.text}"
        return error_message, "API_ERROR"

    except requests.exceptions.RequestException as exc:
        error_message = f"🚨 Failed to connect to API: {exc}"
        return error_message, "CONNECTION_ERROR"