import requests

API_URL = "http://localhost:8010/query"

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
        response = requests.post(API_URL, json={"question": user_query})
        data = response.json()
        print(f"🤖 Assistant: {data.get('answer', data)}\n")
    except Exception as e:
        print("⚠️ Error:", e)