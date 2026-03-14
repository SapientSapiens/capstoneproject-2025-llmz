import streamlit as st
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def insert_feedback(senti_text, pos_neg, satis_level):
    """Send feedback to the proxy endpoint"""
    try:
        url = st.secrets["feedback_api_url"]
        headers = {"X-API-Key": st.secrets["api_key"]}
        payload = {
            "senti_text": senti_text,
            "pos_neg": pos_neg,
            "satis_level": satis_level
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("Feedback submitted successfully")
            return True
        else:
            error_msg = f"Proxy returned {response.status_code}: {response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise