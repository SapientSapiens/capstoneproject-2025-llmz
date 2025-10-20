import streamlit as st
import requests

# ---- App Configuration ----
st.set_page_config(
    page_title=" Survival Guidance Assistant",
    page_icon="🧭",
    layout="centered",
)

API_URL = "http://localhost:8010/query"

# ---- UI Header ----
st.title("🧭 Survival Guidance Assistant")
st.caption("Ask about survival — storms, jungles, quicksand, disasters, health, diseases or epidemics. Get data-driven answers.")

# ---- Session State Initialization ----
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- Display Conversation History ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ---- User Input ----
if user_input := st.chat_input("Ask your survival question..."):
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
