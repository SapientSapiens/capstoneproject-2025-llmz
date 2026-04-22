import os
from fastapi import FastAPI
from pydantic import BaseModel
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
import rag_control


# --- simple request model ---
class QueryRequest(BaseModel):
    question: str

# --- init service & clients once (persist across requests) ---
app = FastAPI(title="RAG Survival Service")

# Configuration
QDRANT_URL = "https://5ef7d200-3b5c-4874-8f95-e621d3d5d429.eu-central-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

if not OPENAI_API_KEY or not QDRANT_API_KEY:
    raise RuntimeError("OPENAI_API_KEY and QDRANT_API_KEY must be set in environment")

# Initialize once (persistent)
llm_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
qdrant_client = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
# qdrant_client.set_model(EMBEDDING_MODEL)

# --- health endpoint ---
@app.get("/")
async def read_root():
    return {"status": "ready"}

# --- main query endpoint ---
@app.post("/query")
async def query(request: QueryRequest):
    """Receive a user question, forward to rag_pipeline, return answer."""
    question = request.question.strip()
    if not question:
        return {"error": "empty question"}

    try:
        response = await rag_control.rag_pipeline(
            question,
            qdrant_client,
            llm_client,
        )
        return {"answer": response, "status": "ok"}
    except Exception as e:
        return {"error": str(e), "status": "error"}