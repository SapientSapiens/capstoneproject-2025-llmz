import retrieval
from llm_augment import rewrite_query_for_qdrant, generate_response
# from openai import OpenAI
# from qdrant_client import QdrantClient
# from fastembed import TextEmbedding

INFORMATION_NOT_FOUND_MSG = "I don't have information on that survival topic in my knowledge base."

# Configuration
# QDRANT_URL = "https://5ef7d200-3b5c-4874-8f95-e621d3d5d429.eu-central-1-0.aws.cloud.qdrant.io"
# QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
# EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
# EMBEDDING_DIMENSION = 768

# Initialize LLM client
# llm_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Qdrant Client initializer
# def initialize_qdrant_client():
#    """Initialize Qdrant client and embedding model"""
#    try:
#        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=60)
#        embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
#    except Exception as e:
#        raise RuntimeError(f"Failed initializing Qdrant/Embedding clients: {e}") from e
#    print("✅ Clients initialized successfully")
#    return qdrant_client, embedding_model


# Initialize Qdrant Client
# qdrant_client, embedding_model = initialize_qdrant_client()


def rag_pipeline(user_query, qdrant_client, embedding_model, llm_client):
    """Main RAG pipeline from user query to final answer (corrected wiring)."""

    # Step 1: Retrieve chunks for the raw user query
    chunks = retrieval.retrieve_chunks(user_query, qdrant_client, embedding_model, top_k=5)
    chunks_retrieved = len(chunks) > 0

    # Step 2: Determine query type (uses global last_user_message/last_assistant_answer)
    query_type = retrieval.determine_query_type(user_query, chunks_retrieved)

    # Step 3: Branch on query_type
    if query_type == "NOT_IN_CONTEXT":
        # No relevant chunks for a first query or follow-up -> safe failure & reset
        retrieval.reset_conversation()
        return INFORMATION_NOT_FOUND_MSG

    elif query_type == "FIRST_QUERY":
        # We have initial chunks; call generate_response with the chunks list (not formatted string).
        # generate_response expects: (user_query, context_chunks, llm_client, ...)
        try:
            response = generate_response(user_query, chunks, llm_client)
        except Exception:
            retrieval.reset_conversation()
            return INFORMATION_NOT_FOUND_MSG

        retrieval.update_conversation(user_query, response)
        return response

    elif query_type == "FOLLOW_UP":
        # We have conversation history: try to rewrite into a standalone retrieval query
        # Use the simple rewrite function signature:
        # rewrite_query_for_qdrant(latest_user_message, last_llm_reply, current_user_question, llm_client)
        rewritten_query = rewrite_query_for_qdrant(
            retrieval.last_user_message,            # previous user message
            retrieval.last_assistant_answer,        # previous assistant reply
            user_query,                   # current question that returned no/low chunks
            llm_client
        )

        # If rewrite fails it should return current_user_question per your rewrite function.
        # Now re-run retrieval with rewritten query
        new_chunks = retrieval.retrieve_chunks(rewritten_query, qdrant_client, embedding_model, top_k=5)

        if not new_chunks:
            # Nothing found after rewriting -> safe failure and reset conversation
            retrieval.reset_conversation()
            return INFORMATION_NOT_FOUND_MSG

        # Otherwise, generate a grounded response from the retrieved chunks
        response = generate_response(rewritten_query, new_chunks, llm_client)
        # Update conversation with the user's original message and the assistant's response.
        # (Optionally you could also store rewritten_query somewhere for debugging.)
        retrieval.update_conversation(user_query, response)
        return response

    else:
        # defensive fallback
        return INFORMATION_NOT_FOUND_MSG
    

if __name__ == "__main__":

    user_query = "What was the recorded damages to life and property in the wake of the world's largest hurricane or tornado?"
    # follow_up_query = "If I ever find my self near such things you just mentioned, what survival tips would you for me?"
    print("-" * 50)
    print(f"🧪 User: {user_query}")
    print("-" * 50)
    response = rag_pipeline(user_query)
    print("-" * 50)
    print(f"🤖 Assistant: {response}")
    print("-" * 50)
    