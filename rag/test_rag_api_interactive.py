import requests

API_URL = "http://localhost:8010/query"

session = requests.Session()
current_session_id = None

print("🌍 Connected to RAG Survival Service at", API_URL)
print("Type 'exit' to quit.\n")

while True:
    user_query = input("🧪 You: ").strip()
    if user_query.lower() in {"exit", "quit"}:
        print("👋 Goodbye!")
        break
    if not user_query:
        continue

    try:
        headers = {}
        if current_session_id:
            headers["X-Session-ID"] = current_session_id

        response = session.post(API_URL, json={"question": user_query}, headers=headers)

        returned_session_id = response.headers.get("X-Session-ID")
        if returned_session_id:
            current_session_id = returned_session_id

        data = response.json()

        print(f"🆔 Session ID: {current_session_id}")
        print(f"🤖 Assistant: {data.get('answer', data)}\n")

    except Exception as e:
        print("⚠️ Error:", e)