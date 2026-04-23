import os
import uuid
from typing import cast
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response, Header, Depends
from pydantic import BaseModel
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

import rag_control

@dataclass
class SessionState:
    last_user_message: str = ""
    last_assistant_answer: str = ""
    last_turn_status: str | None = None
    last_resolved_user_query: str = ""


@dataclass
class SessionRecord:
    state: SessionState = field(default_factory=SessionState)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# --- simple request model ---
class QueryRequest(BaseModel):
    question: str

# --- init service & clients once (persist across requests) ---
app = FastAPI(title="Survival Service RAG")

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

# Session record (lives in app.state.sessions)
app.state.sessions = cast(dict[str, SessionRecord], {})
app.state.sessions_lock = asyncio.Lock()


async def get_or_create_session(
    request: Request,
    response: Response,
    x_session_id: str | None = Header(default=None, alias="X-Session-ID"),
) -> tuple[str, SessionRecord]:
    """
    Resolve the session record for the current request.
    - Read the X-Session-ID header.
    - Create a new session if the header is missing or unknown.
    - Update last_accessed on the resolved session.
    - Set the resolved X-Session-ID in the response header.
    """
    incoming_session_id = (x_session_id or "").strip()
    created_new_session = False

    print()
    print(f"[rag_service] incoming_x_session_id = {incoming_session_id!r}")

    async with request.app.state.sessions_lock:
        if not incoming_session_id or incoming_session_id not in request.app.state.sessions:
            session_id = str(uuid.uuid4())
            request.app.state.sessions[session_id] = SessionRecord()
            created_new_session = True
        else:
            session_id = incoming_session_id

        session_record = request.app.state.sessions[session_id]
        session_record.last_accessed = datetime.now(timezone.utc)

    print(f"[rag_service] resolved_session_id = {session_id!r}")
    print(f"[rag_service] created_new_session = {created_new_session}")
    print()

    response.headers["X-Session-ID"] = session_id
    return session_id, session_record


# --- health endpoint ---
@app.get("/")
async def read_root():
    return {"status": "ready"}

# --- main query endpoint ---   
@app.post("/query")
async def query(
    request: QueryRequest,
    response: Response,
    session_info: tuple[str, SessionRecord] = Depends(get_or_create_session),
):
    """Receive a user question, forward to rag_pipeline, return answer."""
    question = request.question.strip()
    if not question:
        return {"error": "empty question"}

    session_id, session_record = session_info
    print(f"[rag_service] query_session_id = {session_id!r}")

    try:
        async with session_record.lock:
            answer = await rag_control.rag_pipeline(
                question,
                qdrant_client,
                llm_client,
                session_record.state,
            )

        response.headers["X-Session-ID"] = session_id
        return {"answer": answer, "status": "ok"}

    except Exception as e:
        response.headers["X-Session-ID"] = session_id
        return {"error": str(e), "status": "error"}