# interface_app/ui/feedback_panel.py

"""
Feedback panel UI component for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file renders the feedback form and sends feedback through feedback_client.py.

Current feedback payload remains unchanged:

    senti_text
    pos_neg
    satis_level

Control logic:
1. Feedback is available only after a successful assistant answer.
2. Feedback is unavailable after technical/API/connection errors.
3. After feedback submission, the submit button remains disabled until the next
   successful answer returns.
4. If Positive is selected:
      - enabled sentiment options: too_long, too_short, helpful
      - satisfaction slider is enabled
5. If Negative is selected:
      - enabled sentiment options: inaccurate, unclear, irrelevant
      - satisfaction slider is frozen at 1

Native Streamlit radio widgets do not support disabling individual options.
So the form shows only the valid sentiment options for the selected polarity.
Apparently even radio buttons have opinions. Later, when a stronger observability
framework is added, this panel can be expanded without turning app.py into boiled khichdi.
"""

import streamlit as st

from feedback_client import submit_feedback
from state import has_assistant_answer, mark_feedback_submitted


# Sentiment options allowed for Positive feedback.
POSITIVE_SENTIMENT_OPTIONS = [
    "too_long",
    "too_short",
    "helpful",
]


# Sentiment options allowed for Negative feedback.
NEGATIVE_SENTIMENT_OPTIONS = [
    "inaccurate",
    "unclear",
    "irrelevant",
]


def _latest_turn_is_successful() -> bool:
    """
    Return True only if the latest assistant turn completed successfully.
    """

    return st.session_state.get("last_turn_status") == "SUCCESS"


def _render_disabled_submit_button(help_text: str) -> None:
    """
    Render a disabled Submit Feedback button.
    """

    st.button(
        "Submit Feedback",
        disabled=True,
        help=help_text,
        key="submit_feedback_disabled_button",
    )


def render_feedback_panel() -> None:
    """
    Render the feedback section.

    The submit button becomes active only when:
    - there is a successful assistant answer,
    - feedback has not already been submitted for that answer.
    """

    st.header("Feedback")

    # No assistant answer exists yet.
    if not has_assistant_answer():
        st.info("💡 Ask a question first, then provide feedback here.")
        _render_disabled_submit_button(
            "Feedback becomes available after a successful answer."
        )
        return

    # Latest assistant turn exists, but it was not successful.
    if not _latest_turn_is_successful():
        st.warning(
            "Feedback is unavailable because the latest response did not complete successfully."
        )
        _render_disabled_submit_button(
            "Feedback is disabled for technical/API errors."
        )
        return

    # Feedback already submitted for the latest successful answer.
    if st.session_state.feedback_submitted:
        st.success("✅ Feedback submitted successfully! Thank you.")
        _render_disabled_submit_button(
            "Feedback has already been submitted for the latest answer."
        )
        return

    # -----------------------------
    # Active feedback controls
    # -----------------------------

    with st.container(border=True):
        st.subheader("Positive / Negative")

        pos_neg_option = st.radio(
            "Select rating:",
            options=["Positive", "Negative"],
            key="pos_neg_radio",
            label_visibility="collapsed",
            horizontal=True,
        )

        # Update the available sentiment choices immediately based on polarity.
        if pos_neg_option == "Positive":
            sentiment_options = POSITIVE_SENTIMENT_OPTIONS
            sentiment_key = "sentiment_radio_positive"
            slider_key = "satisfaction_slider_positive"
            slider_disabled = False
            slider_value = 3
        else:
            sentiment_options = NEGATIVE_SENTIMENT_OPTIONS
            sentiment_key = "sentiment_radio_negative"
            slider_key = "satisfaction_slider_negative"
            slider_disabled = True
            slider_value = 1

        st.subheader("Usage Sentiment")

        selected_sentiment = st.radio(
            "Select sentiment:",
            options=sentiment_options,
            key=sentiment_key,
            label_visibility="collapsed",
        )

        st.subheader("Satisfaction Level")

        satisfaction_level = st.slider(
            "Satisfaction Level (1 = very poor, 5 = excellent):",
            min_value=1,
            max_value=5,
            value=slider_value,
            key=slider_key,
            label_visibility="collapsed",
            disabled=slider_disabled,
        )

        submit_button = st.button(
            "Submit Feedback",
            type="primary",
            key="submit_feedback_active_button",
        )

        if submit_button:
            try:
                submit_feedback(
                    senti_text=selected_sentiment,
                    pos_neg=pos_neg_option,
                    satis_level=satisfaction_level,
                )

                # Disable feedback for this answer.
                # chat_panel.py resets this when the next question is asked.
                mark_feedback_submitted()

                # Force immediate rerun so the disabled button appears right away.
                st.rerun()

            except Exception as exc:
                st.error(f"Error submitting feedback: {exc}")