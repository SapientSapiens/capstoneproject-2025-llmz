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
    SUCCESS,
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


def _stop_with_status(status: str) -> str:
    """
    Return mapped user message.
    For operational errors, only record the status.
    Do NOT wipe the previous semantic turn.
    """
    try:
        retrieval.update_turn_status(status)
    except Exception:
        retrieval.last_turn_status = status

    return FAILURE_MESSAGE_MAP[status]


def _return_semantic_failure(user_query: str, status: str, resolved_user_query: str = None) -> str:
    """
    Record the current user turn as the latest semantic turn,
    while preserving the resolved semantic query for future rewrites.
    """
    try:
        retrieval.update_conversation(
            user_query,
            "",
            status,
            resolved_user_query=resolved_user_query if resolved_user_query is not None else user_query,
        )
    except Exception:
        retrieval.last_user_message = user_query
        retrieval.last_assistant_answer = ""
        retrieval.last_turn_status = status
        retrieval.last_resolved_user_query = resolved_user_query if resolved_user_query is not None else user_query

    return FAILURE_MESSAGE_MAP[status]


def _retrieve_chunks_safe(query, qdrant_client, embedding_model, top_k=20):
    """
    Returns:
        (None, chunks)                 on success (chunks may be empty)
        (UNKNOWN_RETRIEVAL_ERROR, [])   on error
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


def _conversation_history_is_usable() -> bool:
    """
    History is usable if we have any preserved semantic conversation state.
    We may have:
    - previous user only
    - previous assistant only
    - or both

    Generic operational failure text is never stored as assistant semantic context,
    so we do not need to reject history here.
    """
    last_user = (getattr(retrieval, "last_user_message", "") or "").strip()
    last_reply = (getattr(retrieval, "last_assistant_answer", "") or "").strip()

    return bool(last_user or last_reply)


def _perform_rewrite(user_query: str, llm_client, use_history: bool):
    """
    Perform query rewrite.
    Returns:
        (True, rewritten_query)   on success
        (False, error_message)    on failure
    """
    if use_history:
        previous_user = (
            getattr(retrieval, "last_resolved_user_query", "") or
            getattr(retrieval, "last_user_message", "")
        )
        previous_reply = getattr(retrieval, "last_assistant_answer", "") or ""
    else:
        previous_user = ""
        previous_reply = ""

    print(f"[rag_control] rewrite_previous_user = {previous_user!r}")
    print(f"[rag_control] rewrite_previous_reply = {previous_reply!r}")

    rewrite_result = rewrite_query_for_qdrant(
        previous_user,
        previous_reply,
        user_query,
        llm_client,
    )

    rewrite_result_str = str(rewrite_result).strip()
    rewrite_status = MESSAGE_TO_STATUS.get(rewrite_result_str)

    if rewrite_status in ERROR_STATUSES:
        return False, _stop_with_status(rewrite_status)

    if not rewrite_result_str:
        return False, _stop_with_status(LLM_PARSE_ERROR)

    return True, rewrite_result_str


def rag_pipeline(user_query, qdrant_client, embedding_model, llm_client):
    """
    Corrected flow with:
    - original input query logging
    - single-rewrite guard
    - generation aligned to retrieval query
    - semantic failures updating the latest turn state
    - operational failures updating status only, without wiping semantic history
    - resolved rewritten query preserved for future rewrites
    """

    # --- log original input query ---
    print(f"[rag_control] user_query = {user_query!r}")
    print()    

    last_user = (getattr(retrieval, "last_user_message", "") or "").strip()
    last_reply = (getattr(retrieval, "last_assistant_answer", "") or "").strip()
    last_status = getattr(retrieval, "last_turn_status", None)
    last_resolved_user_query = (getattr(retrieval, "last_resolved_user_query", "") or "").strip()

    # --- log preserved state ---
    print(f"[rag_control] last_user_message = {last_user!r}")
    print()
    print(f"[rag_control] last_assistant_answer = {last_reply!r}")
    print()
    print(f"[rag_control] last_turn_status = {last_status!r}")
    print()
    print(f"[rag_control] last_resolved_user_query = {getattr(retrieval, 'last_resolved_user_query', '')!r}")
    print()

    has_previous_turn = not (last_user == "" and last_reply == "")
    use_history = _conversation_history_is_usable()

    print(f"[rag_control] has_previous_turn = {has_previous_turn}")
    print(f"[rag_control] use_history = {use_history}")

    rewrite_attempted = False
    generation_query = user_query

    # --- decide retrieval query ---
    if has_previous_turn:
        print("[rag_control] Follow-up detected; rewriting before retrieval.")
        rewrite_attempted = True
        success, rewrite_output = _perform_rewrite(user_query, llm_client, use_history)
        if not success:
            return rewrite_output

        retrieval_query = rewrite_output
        generation_query = rewrite_output
    else:
        print("[rag_control] First turn; using raw query.")
        retrieval_query = user_query
        generation_query = user_query

    print(f"[rag_control] retrieval_query = {retrieval_query!r}")
    print(f"[rag_control] generation_query = {generation_query!r}")

    # --- first retrieval attempt ---
    retrieval_status, chunks = _retrieve_chunks_safe(
        retrieval_query,
        qdrant_client,
        embedding_model,
        top_k=20,
    )
    if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
        return _stop_with_status(UNKNOWN_RETRIEVAL_ERROR)

    # --- fallback rewrite for first-turn zero chunks ---
    if not chunks:
        if not has_previous_turn and not rewrite_attempted:
            print("[rag_control] First-turn raw retrieval returned 0 chunks; attempting rewrite.")
            rewrite_attempted = True
            success, rewrite_output = _perform_rewrite(user_query, llm_client, use_history=False)
            if not success:
                return rewrite_output

            retrieval_query = rewrite_output
            generation_query = rewrite_output

            print(f"[rag_control] rewritten retrieval_query = {retrieval_query!r}")
            print(f"[rag_control] rewritten generation_query = {generation_query!r}")

            retrieval_status, chunks = _retrieve_chunks_safe(
                retrieval_query,
                qdrant_client,
                embedding_model,
                top_k=20,
            )
            if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
                return _stop_with_status(UNKNOWN_RETRIEVAL_ERROR)
            if not chunks:
                return _return_semantic_failure(
                    user_query,
                    NO_CONTEXT_CHUNKS,
                    resolved_user_query=generation_query,
                )
        else:
            return _return_semantic_failure(
                user_query,
                NO_CONTEXT_CHUNKS,
                resolved_user_query=generation_query,
            )

    # --- generation attempt ---
    response = generate_response(generation_query, chunks, llm_client)
    response_str = str(response).strip()
    returned_status = MESSAGE_TO_STATUS.get(response_str)

    if returned_status is None:
        retrieval.update_conversation(
            user_query,
            response_str,
            SUCCESS,
            resolved_user_query=generation_query,
        )
        return response_str

    if returned_status in ERROR_STATUSES:
        return _stop_with_status(returned_status)

    # --- first-turn NOT_IN_CONTEXT gets one rewrite rescue ---
    if returned_status == NOT_IN_CONTEXT_TYPE and not has_previous_turn and not rewrite_attempted:
        print("[rag_control] First-turn generation returned NOT_IN_CONTEXT; attempting rewrite.")
        rewrite_attempted = True
        success, rewrite_output = _perform_rewrite(user_query, llm_client, use_history=False)
        if not success:
            return rewrite_output

        retrieval_query = rewrite_output
        generation_query = rewrite_output

        print(f"[rag_control] rewritten retrieval_query = {retrieval_query!r}")
        print(f"[rag_control] rewritten generation_query = {generation_query!r}")

        retrieval_status, chunks = _retrieve_chunks_safe(
            retrieval_query,
            qdrant_client,
            embedding_model,
            top_k=20,
        )
        if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
            return _stop_with_status(UNKNOWN_RETRIEVAL_ERROR)
        if not chunks:
            return _return_semantic_failure(
                user_query,
                NO_CONTEXT_CHUNKS,
                resolved_user_query=generation_query,
            )

        response = generate_response(generation_query, chunks, llm_client)
        response_str = str(response).strip()
        returned_status = MESSAGE_TO_STATUS.get(response_str)

        if returned_status is None:
            retrieval.update_conversation(
                user_query,
                response_str,
                SUCCESS,
                resolved_user_query=generation_query,
            )
            return response_str

        if returned_status in ERROR_STATUSES:
            return _stop_with_status(returned_status)

        if returned_status == NOT_IN_CONTEXT_TYPE:
            return _return_semantic_failure(
                user_query,
                NOT_IN_CONTEXT_TYPE,
                resolved_user_query=generation_query,
            )

        return _return_semantic_failure(
            user_query,
            NOT_IN_CONTEXT_TYPE,
            resolved_user_query=generation_query,
        )

    return _return_semantic_failure(
        user_query,
        NOT_IN_CONTEXT_TYPE,
        resolved_user_query=generation_query,
    )