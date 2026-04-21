import retrieval
from llm_augment import (
    rewrite_query_for_qdrant,
    generate_response,
    FAILURE_MESSAGE_MAP,
    NO_CONTEXT_CHUNKS,
    NOT_IN_CONTEXT_TYPE,
    UNKNOWN_RETRIEVAL_ERROR,
    LLM_AUTH_ERROR,
    LLM_QUOTA_ERROR,
    LLM_RATE_LIMIT,
    LLM_PARSE_ERROR,
    LLM_UNKNOWN_ERROR,
)

ERROR_STATUSES = {
    UNKNOWN_RETRIEVAL_ERROR,
    LLM_AUTH_ERROR,
    LLM_QUOTA_ERROR,
    LLM_RATE_LIMIT,
    LLM_PARSE_ERROR,
    LLM_UNKNOWN_ERROR,
}

MESSAGE_TO_STATUS = {message: status for status, message in FAILURE_MESSAGE_MAP.items()}


def _clear_previous_turn_state():
    """
    Clear only the previous-turn state, as requested.
    This is done only for the explicit operational error statuses.
    """
    try:
        retrieval.reset_conversation()
    except Exception:
        pass

    setattr(retrieval, "last_user_message", "")
    setattr(retrieval, "last_assistant_answer", "")


def _stop_with_status(status: str) -> str:
    """
    Return the mapped user-facing string.
    Clear previous-turn state only for the explicit operational errors.
    """
    if status in ERROR_STATUSES:
        _clear_previous_turn_state()

    return FAILURE_MESSAGE_MAP[status]


def _retrieve_chunks_safe(query, qdrant_client, embedding_model, top_k):
    """
    Distinguish:
    - retrieval operational error -> UNKNOWN_RETRIEVAL_ERROR
    - retrieval success with 0 chunks -> []
    """
    try:
        chunks = retrieval.retrieve_chunks(query, qdrant_client, embedding_model, top_k=top_k)
    except Exception as e:
        print(f"[rag_control] retrieval_status={UNKNOWN_RETRIEVAL_ERROR}")
        print(f"[rag_control] retrieval_detail={type(e).__name__}: {e}")
        return UNKNOWN_RETRIEVAL_ERROR, []

    if chunks is None:
        print(f"[rag_control] retrieval_status={UNKNOWN_RETRIEVAL_ERROR}")
        print("[rag_control] retrieval_detail=retrieve_chunks returned None")
        return UNKNOWN_RETRIEVAL_ERROR, []

    return None, list(chunks)


def _finalize_generation_result(user_query: str, response: str) -> str:
    """
    Handle generate_response() output according to the agreed rules:
    - real answer -> return answer and update conversation
    - explicit operational error mapped string -> return it, stop, clear state
    - NOT_IN_CONTEXT / no-answer style outcome -> return NOT_IN_CONTEXT_TYPE mapped string
    """
    if response is None:
        return FAILURE_MESSAGE_MAP[NOT_IN_CONTEXT_TYPE]

    response = str(response).strip()
    if not response:
        return FAILURE_MESSAGE_MAP[NOT_IN_CONTEXT_TYPE]

    returned_status = MESSAGE_TO_STATUS.get(response)

    if returned_status in ERROR_STATUSES:
        return _stop_with_status(returned_status)

    if returned_status == NOT_IN_CONTEXT_TYPE:
        return FAILURE_MESSAGE_MAP[NOT_IN_CONTEXT_TYPE]

    if returned_status == NO_CONTEXT_CHUNKS:
        return FAILURE_MESSAGE_MAP[NOT_IN_CONTEXT_TYPE]

    retrieval.update_conversation(user_query, response)
    return response


def rag_pipeline(user_query, qdrant_client, embedding_model, llm_client):
    """
    Orchestration rules implemented exactly as discussed:

    1. First retrieval on the raw user query.
    2. Retrieval operational error -> UNKNOWN_RETRIEVAL_ERROR mapped string, stop, clear previous-turn state.
    3. If raw retrieval returns 0 chunks, always attempt query rewrite (including the first question in the session).
    4. Rewrite LLM error -> mapped LLM error string, stop, clear previous-turn state.
    5. Rewritten query is used for second retrieval.
    6. Second retrieval returns 0 chunks -> NO_CONTEXT_CHUNKS mapped string, stop.
    7. Second retrieval operational error -> UNKNOWN_RETRIEVAL_ERROR mapped string, stop, clear previous-turn state.
    8. Second retrieval succeeds -> generate_response().
    9. Real answer -> return answer.
    10. NOT_IN_CONTEXT / no-answer style generation outcome -> NOT_IN_CONTEXT_TYPE mapped string.
    11. generate_response() operational error -> mapped error string, stop, clear previous-turn state.
    """

    # First retrieval on the raw user query
    retrieval_status, chunks = _retrieve_chunks_safe(
        user_query,
        qdrant_client,
        embedding_model,
        top_k=20,
    )

    if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
        return _stop_with_status(UNKNOWN_RETRIEVAL_ERROR)

    # Raw retrieval returned 0 chunks -> always candidate for query rewrite
    if not chunks:
        previous_user_query = getattr(retrieval, "last_user_message", "") or ""
        previous_llm_reply = getattr(retrieval, "last_assistant_answer", "") or ""

        rewritten_query_or_message = rewrite_query_for_qdrant(
            previous_user_query,
            previous_llm_reply,
            user_query,
            llm_client,
        )

        rewritten_query_or_message = str(rewritten_query_or_message).strip()
        rewrite_status = MESSAGE_TO_STATUS.get(rewritten_query_or_message)

        # Rewrite LLM operational failure -> stop immediately
        if rewrite_status in ERROR_STATUSES:
            return _stop_with_status(rewrite_status)

        # Defensive guard: blank rewrite output counts as parse-like failure
        if not rewritten_query_or_message:
            return _stop_with_status(LLM_PARSE_ERROR)

        # Second retrieval using the rewritten query
        rewritten_retrieval_status, rewritten_chunks = _retrieve_chunks_safe(
            rewritten_query_or_message,
            qdrant_client,
            embedding_model,
            top_k=5,
        )

        if rewritten_retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
            return _stop_with_status(UNKNOWN_RETRIEVAL_ERROR)

        if not rewritten_chunks:
            return FAILURE_MESSAGE_MAP[NO_CONTEXT_CHUNKS]

        response = generate_response(
            rewritten_query_or_message,
            rewritten_chunks,
            llm_client,
        )
        return _finalize_generation_result(user_query, response)

    # Raw retrieval succeeded with chunks -> generate directly
    response = generate_response(
        user_query,
        chunks,
        llm_client,
    )
    return _finalize_generation_result(user_query, response)