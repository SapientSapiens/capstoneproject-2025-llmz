import os
import streamlit as st
import requests
import monitoring

# ---- App Configuration ----
st.set_page_config(
    page_title="Survival Guidance Assistant",
    page_icon="🧭",
    layout="wide",  # Changed to wide for side-by-side layout
)

# Get RAG API URL from secrets (Streamlit Cloud) or env var (local)
try:
    # For Streamlit Cloud - from secrets
    API_BASE_URL = st.secrets["rag_api"]["url"]
except (KeyError, FileNotFoundError):
    # For local development - from environment variable or default
    API_BASE_URL = os.getenv("RAG_API_URL", "http://localhost:8010")

API_URL = f"{API_BASE_URL}/query"

# Initialize database tables for the very first time
# monitoring.init_tables()

# ---- UI Header ----
st.title("🧭 Survival Guidance Assistant")
st.caption("Ask about survival — storms, jungles, quicksand, disasters, health, diseases or epidemics. Get data-driven answers.")

# Create two columns for the layout
# col1, col2 = st.columns([3, 2])  # 3:2 ratio as requested
col1, spacer, col2 = st.columns([3.5, 0.5, 1.5])

with col1:
    # ---- Session State Initialization ----
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "feedback_submitted" not in st.session_state:
        st.session_state.feedback_submitted = False

    # ---- Display Conversation History ----
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ---- User Input ----
    if user_input := st.chat_input("Ask your survival question..."):
        # Reset feedback state for new conversation
        st.session_state.feedback_submitted = False
        
        # Show user message
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # ---- Send to API ----
        try:
            response = requests.post(API_URL, json={"question": user_input})
            if response.status_code == 200:
                data = response.json()
                assistant_reply = data.get("answer", "⚠️ No answer returned by service.")
            else:
                assistant_reply = f"❌ Error: {response.status_code} - {response.text}"
        except Exception as e:
            assistant_reply = f"🚨 Failed to connect to API: {e}"

        # ---- Display Assistant Reply ----
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        with st.chat_message("assistant"):
            st.markdown(assistant_reply)

with col2:
    # ---- Feedback Section ----
    st.header("Feedback")
    
    # Only show feedback form if there's a conversation and feedback hasn't been submitted
    if st.session_state.messages and not st.session_state.feedback_submitted:
        with st.form("feedback_form"):
            st.subheader("Usage Sentiment")
            sentiment_options = ["inaccurate", "unclear", "too_long", "too_short", "helpful", "irrelevant"]
            selected_sentiment = st.radio(
                "Select sentiment:",
                options=sentiment_options,
                key="sentiment_radio",
                label_visibility="collapsed"
            )
            
            st.subheader("Positive Negative")
            pos_neg_option = st.radio(
                "Select rating:",
                options=["Positive", "Negative"],
                key="pos_neg_radio",
                label_visibility="collapsed",
                horizontal=True
            )
            
            st.subheader("Satisfaction Level")
            satisfaction_level = st.slider(
                "Satisfaction Level (1 = very poor, 5 = excellent):",
                min_value=1,
                max_value=5,
                value=3,
                key="satisfaction_slider",
                label_visibility="collapsed"
            )
            
            # Submit button
            submit_button = st.form_submit_button("Submit Feedback")
            
            if submit_button:
                # Validate that all feedback is provided
                if not selected_sentiment:
                    st.error("Please select a sentiment distribution option")
                elif not pos_neg_option:
                    st.error("Please select positive or negative")
                else:
                    # Insert feedback into database
                    try:
                        monitoring.insert_feedback(
                            senti_text=selected_sentiment,
                            pos_neg=pos_neg_option,
                            satis_level=satisfaction_level
                        )
                        st.session_state.feedback_submitted = True
                        st.success("Thank you for your feedback!")
                    except Exception as e:
                        st.error(f"Error submitting feedback: {e}")
    
    elif st.session_state.feedback_submitted:
        st.success("✅ Feedback submitted successfully! Thank you.")
    
    else:
        st.info("💡 Have a conversation first, then provide your feedback here.")