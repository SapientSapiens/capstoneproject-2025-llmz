# set confidence threshold for avoiding chunks with lesser relevance to the user question
CONFIDENCE_THRESHOLD = 0.68

COLLECTION_NAME = "survival_strategies"

# Global conversation state
last_user_message = None
last_assistant_answer = None

def reset_conversation():
    global last_user_message, last_assistant_answer
    last_user_message = None
    last_assistant_answer = None

def update_conversation(user_msg, assistant_answer):
    global last_user_message, last_assistant_answer
    last_user_message = user_msg
    last_assistant_answer = assistant_answer

def determine_query_type(query, chunks_retrieved):
    """Determine query type based on conversation state and retrieval results"""
    has_history = (last_user_message is not None and 
                   last_assistant_answer is not None)
    
    if not has_history:
        return "NOT_IN_CONTEXT" if not chunks_retrieved else "FIRST_QUERY"
    else:
        return "NOT_IN_CONTEXT" if not chunks_retrieved else "FOLLOW_UP"
    
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

def retrieve_chunks(query, qdrant_client, embedding_model, top_k=5):
    query_embedding = list(embedding_model.embed([query]))[0]
    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_embedding.tolist(),
        limit=top_k
    )

    filtered_results = []
    for p in results.points:
        if p.score >= CONFIDENCE_THRESHOLD:
            filtered_results.append({
                "id": p.id,
                "text": p.payload.get("text", ""),
                "score": p.score,
                "payload": p.payload
            })
    return filtered_results