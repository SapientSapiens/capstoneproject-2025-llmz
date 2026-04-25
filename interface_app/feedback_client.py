# interface_app/feedback_client.py

"""
Feedback / monitoring API client for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file sends user feedback from the Streamlit app to the existing
feedback API endpoint.

Important:
The feedback payload remains unchanged for now:

    {
        "senti_text": "...",
        "pos_neg": "...",
        "satis_level": ...
    }

Later, this can be expanded when we implement the robust observability
framework. For now, we are not pretending this is LangSmith, Phoenix, MLflow,
and NASA telemetry stitched together by divine intervention.
"""

import logging
import requests

from config import get_api_key, get_feedback_api_url


# Basic logger for feedback submission success/failure.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def submit_feedback(
    senti_text: str,
    pos_neg: str,
    satis_level: int,
) -> bool:
    """
    Submit user feedback to the feedback API.

    Args:
        senti_text:
            Selected usage sentiment.
            Current allowed examples:
            inaccurate, unclear, too_long, too_short, helpful, irrelevant

        pos_neg:
            Overall feedback polarity.
            Current allowed values:
            Positive, Negative

        satis_level:
            User satisfaction level.
            Current expected range:
            1 to 5

    Returns:
        True if the feedback API accepts the submission.

    Notes:
        If feedback_api_url is missing, local development fallback mode is used.
        In that mode, feedback is logged locally and treated as successfully submitted,
        but it is not sent to the backend.

    Raises:
        Exception:
            If the feedback API URL exists but returns a non-200 status, or if the request fails.
    """

    feedback_api_url = get_feedback_api_url()
    api_key = get_api_key()

    # Fail clearly if feedback_api_url is not configured.
    #if not feedback_api_url:
    #    raise ValueError(
    #        "Feedback API URL is missing. Set feedback_api_url in Streamlit secrets "
    #        "or FEEDBACK_API_URL in your local environment."
    #    )

    # Local development fallback:
    # In production, feedback_api_url should exist in Streamlit secrets.
    # In local development, the feedback API/proxy may not be available.
    # Instead of breaking UI testing, accept the feedback locally and log it.
    if not feedback_api_url:
        logger.warning(
            "Feedback API URL is missing. Running in local dev fallback mode. "
            "Feedback was not sent to backend. Payload: %s",
            {
                "senti_text": senti_text,
                "pos_neg": pos_neg,
                "satis_level": satis_level,
            },
        )
        return True

    headers = {
        "X-API-Key": api_key,
    }

    payload = {
        "senti_text": senti_text,
        "pos_neg": pos_neg,
        "satis_level": satis_level,
    }

    try:
        response = requests.post(
            feedback_api_url,
            json=payload,
            headers=headers,
            timeout=10,
        )

        if response.status_code == 200:
            logger.info("Feedback submitted successfully.")
            return True

        error_msg = f"Feedback API returned {response.status_code}: {response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)

    except requests.exceptions.RequestException as exc:
        logger.error("Error submitting feedback: %s", exc)
        raise