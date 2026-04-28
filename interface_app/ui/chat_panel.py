# interface_app/ui/chat_panel.py

"""
Chat panel UI component for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file renders:
- top-positioned user question input
- newest question-answer pairs first
- older question-answer pairs below
- RAG API request trigger
- assistant response display
- temporary blocking overlay while the API request is processing

So this file uses st.form() + st.text_area() instead. It keeps chat-related
UI away from app.py, because app.py should orchestrate, not personally do every office 
chore like an overworked clerk. Yes, Streamlit made this more awkward than necessary.
Civilization marches sideways.
"""

import streamlit as st

from api_client import ask_rag_api
from state import (
    add_assistant_message,
    add_user_message,
    mark_processing_finished,
    mark_processing_started,
    reset_feedback_for_new_question,
)

def _render_processing_overlay(placeholder: st.delta_generator.DeltaGenerator) -> None:
    """
    Render a thin grey blocking overlay while the backend is processing.

    Args:
        placeholder:
            Streamlit placeholder where the overlay HTML is inserted.

    Why a placeholder?
        So we can remove the overlay after the API response is received by calling:
            placeholder.empty()
    """

    placeholder.markdown(
        """
        <style>
            .processing-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(230, 230, 230, 0.45);
                z-index: 999998;
                display: flex;
                align-items: center;
                justify-content: center;
                backdrop-filter: blur(1.5px);
            }

            .processing-card {
                background: rgba(20, 24, 31, 0.94);
                color: white;
                padding: 1.4rem 1.8rem;
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.18);
                box-shadow: 0 14px 40px rgba(0, 0, 0, 0.35);
                min-width: 330px;
                text-align: center;
                font-family: sans-serif;
            }

            .processing-spinner {
                margin: 0 auto 0.85rem auto;
                width: 34px;
                height: 34px;
                border: 4px solid rgba(255, 255, 255, 0.25);
                border-top: 4px solid #ff4b4b;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }

            .processing-title {
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .processing-subtitle {
                font-size: 0.86rem;
                color: rgba(255, 255, 255, 0.72);
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>

        <div class="processing-overlay">
            <div class="processing-card">
                <div class="processing-spinner"></div>
                <div class="processing-title">Processing your survival question...</div>
                <div class="processing-subtitle">
                    Generating response from the retrieved knowledge chunks.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def _build_conversation_turns(messages: list[dict]) -> list[dict]:
    """
    Convert flat message history into question-answer turns.

    Current stored format:
        [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."},
            ...
        ]

    Returned format:
        [
            {"user": "...", "assistant": "..."},
            ...
        ]

    This makes it easier to display newest Q/A pairs first.
    """

    turns = []
    pending_user_message = None

    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "user":
            # If a previous user message had no assistant response, preserve it.
            if pending_user_message is not None:
                turns.append(
                    {
                        "user": pending_user_message,
                        "assistant": None,
                    }
                )

            pending_user_message = content

        elif role == "assistant":
            if pending_user_message is None:
                # Defensive handling: assistant message without a matching user.
                turns.append(
                    {
                        "user": None,
                        "assistant": content,
                    }
                )
            else:
                turns.append(
                    {
                        "user": pending_user_message,
                        "assistant": content,
                    }
                )
                pending_user_message = None

    # Preserve a final pending user message if it exists.
    if pending_user_message is not None:
        turns.append(
            {
                "user": pending_user_message,
                "assistant": None,
            }
        )

    return turns


def _render_turn(turn: dict) -> None:
    """
    Render one question-answer turn.

    Within a turn:
    1. user question appears first
    2. assistant answer appears below it
    """

    user_message = turn.get("user")
    assistant_message = turn.get("assistant")

    if user_message:
        with st.chat_message("user"):
            st.markdown(user_message)

    if assistant_message:
        with st.chat_message("assistant"):
            st.markdown(assistant_message)


def render_question_input() -> str | None:
    """
    Render the user question input at the top of the chat panel.

    Returns:
        The submitted user question, or None if nothing was submitted.
    """

    with st.form("question_form", clear_on_submit=True):
        user_input = st.text_area(
            "Ask your survival question:",
            placeholder="Example: What should I do during a hurricane?",
            height=90,
            key="question_text_area",
        )

        submitted = st.form_submit_button(
            "Ask Away..",
            type="primary",
        )

    if not submitted:
        return None

    cleaned_input = user_input.strip()

    if not cleaned_input:
        st.warning("Please enter a question before submitting.")
        return None

    return cleaned_input


def render_chat_history(exclude_latest_turn: bool = False) -> None:
    """
    Render stored chat history with newest Q/A pairs first.

    Args:
        exclude_latest_turn:
            If True, skip the newest turn from stored history.

            This is used immediately after a new question is submitted because
            the latest turn is rendered live during the same run, while older
            turns are rendered from stored history below it.
    """

    turns = _build_conversation_turns(st.session_state.messages)

    if exclude_latest_turn and turns:
        turns = turns[:-1]

    # Newest Q/A pair should appear first.
    for turn in reversed(turns):
        _render_turn(turn)


def handle_new_question(user_input: str) -> None:
    """
    Process a newly submitted question and render it immediately.

    Flow:
    1. Reset feedback state.
    2. Store and render the user question immediately.
    3. Show a blocking overlay.
    4. Call the RAG API.
    5. Remove the overlay.
    6. Render and store the assistant answer.

    This keeps the submitted question visible while preventing the user from
    casually assaulting the button during processing.
    """

    # New question means old feedback state must be reset.
    reset_feedback_for_new_question()

    # Store the user message in session state.
    add_user_message(user_input)

    # Render the submitted question immediately.
    with st.chat_message("user"):
        st.markdown(user_input)

    # Create a placeholder for the overlay so it can be removed after the API call.
    overlay_placeholder = st.empty()

    # Mark processing before calling the backend.
    mark_processing_started()

    # Render the blocking overlay before the API call.
    _render_processing_overlay(overlay_placeholder)

    try:
        assistant_reply, status = ask_rag_api(user_input)

    except Exception as exc:
        # Defensive fallback so the Streamlit UI does not crash.
        assistant_reply = f"🚨 Unexpected error while calling API: {exc}"
        status = "CONNECTION_ERROR"

    finally:
        # Always clear processing state, success or failure.
        mark_processing_finished()

        # Remove the blocking overlay after the backend returns.
        overlay_placeholder.empty()

    # Render the assistant answer immediately after the API returns.
    with st.chat_message("assistant"):
        st.markdown(assistant_reply)

    # Store the assistant response after rendering it.
    add_assistant_message(assistant_reply, status=status)



def render_chat_panel() -> None:
    """
    Render the full chat panel.

    Final layout:
        1. question input at top
        2. newest Q/A pair below input
        3. older Q/A pairs below, newest to oldest
    """

    user_input = render_question_input()

    # st.markdown("---")
    # Soft spacing between the question box and the chat thread.
    # This looks cleaner than a hard horizontal divider.
    st.markdown(
        "<div style='height: 1.25rem;'></div>",
        unsafe_allow_html=True,
    )

    if user_input:
        # Render the new Q/A live.
        handle_new_question(user_input)

        # Render older Q/A pairs below it.
        render_chat_history(exclude_latest_turn=True)

    else:
        # No new question submitted, so render all stored history.
        render_chat_history()