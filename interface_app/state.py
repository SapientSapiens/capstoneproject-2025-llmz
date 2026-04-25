# interface_app/state.py

"""
Session-state helpers for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file centralizes all Streamlit session state initialization and updates.
Streamlit reruns the script after user interactions, so session_state is where
we preserve chat history, feedback status, and frontend-side conversation memory.

"""

import streamlit as st


def initialize_session_state() -> None:
    """
    Initialize all session state keys used by the interface.

    Keeping these keys in one place prevents random session_state keys from
    spreading across the app like invasive weeds.
    """

    # Stores visible chat messages shown in the Streamlit chat interface.
    # Expected format:
    # [
    #     {"role": "user", "content": "..."},
    #     {"role": "assistant", "content": "..."}
    # ]
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Tracks whether feedback has already been submitted for the latest answer.
    if "feedback_submitted" not in st.session_state:
        st.session_state.feedback_submitted = False

    # Tracks whether the app is currently waiting for the RAG API response.
    # This will become useful when we add the loading overlay later.
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    # Stores the latest user message.
    # Useful for frontend-side session continuity similar to your terminal script.
    if "last_user_message" not in st.session_state:
        st.session_state.last_user_message = None

    # Stores the latest assistant response.
    if "last_assistant_answer" not in st.session_state:
        st.session_state.last_assistant_answer = None

    # Stores the latest turn status.
    # For now, the frontend can use values such as:
    # SUCCESS, API_ERROR, CONNECTION_ERROR
    if "last_turn_status" not in st.session_state:
        st.session_state.last_turn_status = None

    # Reserved for the resolved/reformulated query if the frontend later needs
    # to mirror terminal-script style handling more closely.
    if "last_resolved_user_query" not in st.session_state:
        st.session_state.last_resolved_user_query = None


def reset_feedback_for_new_question() -> None:
    """
    Reset feedback state whenever the user asks a new question.
    """

    st.session_state.feedback_submitted = False


def add_user_message(content: str) -> None:
    """
    Add a user message to visible chat history and update latest user state.
    """

    st.session_state.messages.append(
        {
            "role": "user",
            "content": content,
        }
    )

    st.session_state.last_user_message = content


def add_assistant_message(content: str, status: str = "SUCCESS") -> None:
    """
    Add an assistant message to visible chat history and update latest answer state.
    """

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": content,
        }
    )

    st.session_state.last_assistant_answer = content
    st.session_state.last_turn_status = status


def mark_processing_started() -> None:
    """
    Mark the interface as waiting for an API response.
    """

    st.session_state.is_processing = True


def mark_processing_finished() -> None:
    """
    Mark the interface as no longer waiting for an API response.
    """

    st.session_state.is_processing = False


def mark_feedback_submitted() -> None:
    """
    Mark feedback as submitted for the latest assistant answer.
    """

    st.session_state.feedback_submitted = True


def has_conversation_started() -> bool:
    """
    Return True if at least one message exists in chat history.
    """

    return len(st.session_state.messages) > 0


def has_assistant_answer() -> bool:
    """
    Return True if the latest assistant answer exists.
    """

    return st.session_state.last_assistant_answer is not None