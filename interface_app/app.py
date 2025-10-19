import re
import html
import streamlit as st
import requests

# ---- App Configuration ----
st.set_page_config(
    page_title=" Survival Guidance Assistant",
    page_icon="🧭",
    layout="centered",
)

API_URL = "http://localhost:8010/query"

def sanitize_text_client(s: str) -> str:
    """Robust client-side sanitizer that also detects per-character-line corruption."""
    if not isinstance(s, str):
        return s

    # basic unicode + newline cleanup
    s = html.unescape(s)
    s = s.replace("\u200b", "").replace("\ufeff", "")
    s = s.replace("\r", "")
    s = re.sub(r"\n{3,}", "\n\n", s)                # collapse many blank lines
    s = re.sub(r"[ \t]{2,}", " ", s)               # normalize spaces

    # join stray single newlines between non-space chars
    s = re.sub(r"(?<=\S)\n(?=\S)", "", s)

    # If a lot of the lines are single characters, this is a per-char newline corruption:
    lines = s.splitlines()
    if len(lines) >= 6:
        single_count = sum(1 for L in lines if len(L.strip()) == 1)
        if single_count / len(lines) > 0.30:
            # Join all lines (remove per-line breaks), then fix obvious squashes
            s = "".join(line.strip() for line in lines)
            # add space between digit+letter squashes (125billion -> 125 billion)
            s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
            # add space between a lowercase + uppercase (CamelCase -> Camel Case)
            s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
            # ensure periods have a space after them
            s = re.sub(r"\.([A-Za-z0-9])", r". \1", s)

    # finally, normalize remaining newlines/space
    s = re.sub(r"\n{2,}", "\n\n", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()

# ---- UI Header ----
st.title("🧭 Survival Guidance Assistant")
st.caption("Ask about survival — storms, jungles, quicksand, disasters, health, diseases or epidemics. Get data-driven answers.")

# ---- Session State Initialization ----
if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- Display Conversation History ----
for msg in st.session_state.messages:
    content = msg.get("content", "")
    if isinstance(content, str):
        content = sanitize_text_client(content)
    with st.chat_message(msg["role"]):
        st.markdown(content)

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

    # ---- Clean and Display Assistant Reply ----
    assistant_reply = sanitize_text_client(assistant_reply)
    st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
    with st.chat_message("assistant"):
        st.markdown(assistant_reply)
