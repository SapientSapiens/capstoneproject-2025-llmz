from qdrant_client import models

EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"

# set confidence threshold for avoiding chunks with lesser relevance to the user question
CONFIDENCE_THRESHOLD = 0.50
#CONFIDENCE_THRESHOLD = 0.68

COLLECTION_NAME = "survival_strategies"

# Global conversation state
last_user_message = ""
last_assistant_answer = ""
last_turn_status = None
last_resolved_user_query = ""


def reset_conversation():
    global last_user_message, last_assistant_answer, last_turn_status, last_resolved_user_query
    last_user_message = ""
    last_assistant_answer = ""
    last_turn_status = None
    last_resolved_user_query = ""


def update_conversation(user_msg, assistant_answer, turn_status=None, resolved_user_query=None):
    global last_user_message, last_assistant_answer, last_turn_status, last_resolved_user_query
    last_user_message = user_msg
    last_assistant_answer = assistant_answer
    last_turn_status = turn_status
    last_resolved_user_query = resolved_user_query if resolved_user_query is not None else user_msg


def update_turn_status(turn_status):
    global last_turn_status
    last_turn_status = turn_status

    
def format_chunks_for_prompt(chunks):
    """Format retrieved chunks for LLM prompt"""
    if not chunks:
        return ""
    
    formatted_chunks = []
    for i, chunk in enumerate(chunks, 1):
        chunk_text = f"""
        Source {i}:
        Video: {chunk.payload['video_title']}
        Chapter: {chunk.payload['chapter_title']}  
        Content: {chunk.payload['text']}
        """
        formatted_chunks.append(chunk_text)
    
    return "\n".join(formatted_chunks)

async def retrieve_chunks(query, qdrant_client, top_k=20):   
    print(f"**********Question for chunk retrival {query} **************")

    # Using models.Document for Qdrant client nativev embedding generation (Internally with FastEmbed)
    # This sends a raw vector to Qdrant server, avoiding server-side named vector issues.
    response = await qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=models.Document(
            text=query,
            model=EMBEDDING_MODEL,
        ),
        limit=top_k,
        with_payload=True,
    )

    results = response.points

    print(f"**********Raw points returned from Qdrant: {len(results)} **************")
    print()

    filtered_results = []
    for p in results:
        print(f"Chunk ID: {p.id}, Score: {p.score:.4f}")
        if p.score >= CONFIDENCE_THRESHOLD:
            filtered_results.append({
                "id": p.id,
                "text": (p.payload or {}).get("text", ""),
                "score": p.score,
                "payload": p.payload or {},
            })

    print(f"**********Retrieved chunks of length {len(filtered_results)} **************")
    print()

    return filtered_results