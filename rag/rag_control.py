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


def _stop_with_status(session_state, status: str) -> str:
    """
    Return mapped user message.
    For operational errors, only record the status.
    Do NOT wipe the previous semantic turn.
    """
    try:
        retrieval.update_turn_status(session_state, status)
    except Exception:
        session_state.last_turn_status = status

    return FAILURE_MESSAGE_MAP[status]


def _return_semantic_failure(session_state, user_query: str, status: str, resolved_user_query: str = None) -> str:
    """
    Record the current user turn as the latest semantic turn,
    while preserving the resolved semantic query for future rewrites.
    """
    try:
        retrieval.update_conversation(
            session_state,
            user_query,
            "",
            status,
            resolved_user_query=resolved_user_query if resolved_user_query is not None else user_query,
        )
    except Exception:
        session_state.last_user_message = user_query
        session_state.last_assistant_answer = ""
        session_state.last_turn_status = status
        session_state.last_resolved_user_query = resolved_user_query if resolved_user_query is not None else user_query

    return FAILURE_MESSAGE_MAP[status]


async def _retrieve_chunks_safe(query, qdrant_client, top_k=20):
    """
    Returns:
        (None, chunks)                 on success (chunks may be empty)
        (UNKNOWN_RETRIEVAL_ERROR, [])  on error
    """
    try:
        chunks = await retrieval.retrieve_chunks(query, qdrant_client, top_k=top_k)
    except Exception as e:
        print(f"[rag_control] retrieval_status={UNKNOWN_RETRIEVAL_ERROR}")
        print(f"[rag_control] retrieval_detail={type(e).__name__}: {e}")
        return UNKNOWN_RETRIEVAL_ERROR, []

    if chunks is None:
        print(f"[rag_control] retrieval_status={UNKNOWN_RETRIEVAL_ERROR}")
        print("[rag_control] retrieval_detail=retrieve_chunks returned None")
        return UNKNOWN_RETRIEVAL_ERROR, []

    return None, list(chunks)


def _conversation_history_is_usable(session_state) -> bool:
    """
    History is usable if we have any preserved semantic conversation state.
    """
    last_user = (getattr(session_state, "last_user_message", "") or "").strip()
    last_reply = (getattr(session_state, "last_assistant_answer", "") or "").strip()

    return bool(last_user or last_reply)


async def _perform_rewrite(session_state, user_query: str, llm_client, use_history: bool):
    """
    Perform query rewrite.
    Returns:
        (True, rewritten_query)   on success
        (False, error_message)    on failure
    """
    if use_history:
        previous_user = (
            getattr(session_state, "last_resolved_user_query", "") or
            getattr(session_state, "last_user_message", "")
        )
        previous_reply = getattr(session_state, "last_assistant_answer", "") or ""
    else:
        previous_user = ""
        previous_reply = ""

    print(f"[rag_control] rewrite_previous_user = {previous_user!r}")
    print(f"[rag_control] rewrite_previous_reply = {previous_reply!r}")

    rewrite_result = await rewrite_query_for_qdrant(
        previous_user,
        previous_reply,
        user_query,
        llm_client,
    )

    rewrite_result_str = str(rewrite_result).strip()
    rewrite_status = MESSAGE_TO_STATUS.get(rewrite_result_str)

    if rewrite_status in ERROR_STATUSES:
        return False, _stop_with_status(session_state, rewrite_status)

    if not rewrite_result_str:
        return False, _stop_with_status(session_state, LLM_PARSE_ERROR)

    return True, rewrite_result_str


async def rag_pipeline(user_query, qdrant_client, llm_client, session_state):
    """
    Corrected flow with:
    - original input query logging
    - single-rewrite guard
    - generation aligned to retrieval query
    - semantic failures updating the latest turn state
    - operational failures updating status only, without wiping semantic history
    - resolved rewritten query preserved for future rewrites
    """

    print()
    print(f"[rag_control] user_query = {user_query!r}")
    print()

    last_user = (getattr(session_state, "last_user_message", "") or "").strip()
    last_reply = (getattr(session_state, "last_assistant_answer", "") or "").strip()
    last_status = getattr(session_state, "last_turn_status", None)
    last_resolved_user_query = (getattr(session_state, "last_resolved_user_query", "") or "").strip()

    print()
    print(f"[rag_control] last_user_message = {last_user!r}")
    print()
    print(f"[rag_control] last_assistant_answer = {last_reply!r}")
    print()
    print(f"[rag_control] last_turn_status = {last_status!r}")
    print()
    print(f"[rag_control] last_resolved_user_query = {last_resolved_user_query!r}")
    print()

    has_previous_turn = not (last_user == "" and last_reply == "")
    use_history = _conversation_history_is_usable(session_state)

    print()
    print(f"[rag_control] has_previous_turn = {has_previous_turn}")
    print(f"[rag_control] use_history = {use_history}")
    print()

    rewrite_attempted = False
    generation_query = user_query

    if has_previous_turn:
        print()
        print("[rag_control] Follow-up detected; rewriting before retrieval.")
        print()

        rewrite_attempted = True
        success, rewrite_output = await _perform_rewrite(session_state, user_query, llm_client, use_history)
        if not success:
            return rewrite_output

        retrieval_query = rewrite_output
        generation_query = rewrite_output
    else:
        print()
        print("[rag_control] First turn; using raw query.")
        print()
        retrieval_query = user_query
        generation_query = user_query

    print()
    print(f"[rag_control] retrieval_query = {retrieval_query!r}")
    print(f"[rag_control] generation_query = {generation_query!r}")
    print()

    retrieval_status, chunks = await _retrieve_chunks_safe(
        retrieval_query,
        qdrant_client,
        top_k=20,
    )
    if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
        return _stop_with_status(session_state, UNKNOWN_RETRIEVAL_ERROR)

    if not chunks:
        if not has_previous_turn and not rewrite_attempted:
            print()
            print("[rag_control] First-turn raw retrieval returned 0 chunks; attempting rewrite.")
            print()
            rewrite_attempted = True
            success, rewrite_output = await _perform_rewrite(session_state, user_query, llm_client, use_history=False)
            if not success:
                return rewrite_output

            retrieval_query = rewrite_output
            generation_query = rewrite_output

            print()
            print(f"[rag_control] rewritten retrieval_query = {retrieval_query!r}")
            print(f"[rag_control] rewritten generation_query = {generation_query!r}")
            print()

            retrieval_status, chunks = await _retrieve_chunks_safe(
                retrieval_query,
                qdrant_client,
                top_k=20,
            )
            if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
                return _stop_with_status(session_state, UNKNOWN_RETRIEVAL_ERROR)
            if not chunks:
                return _return_semantic_failure(
                    session_state,
                    user_query,
                    NO_CONTEXT_CHUNKS,
                    resolved_user_query=generation_query,
                )
        else:
            return _return_semantic_failure(
                session_state,
                user_query,
                NO_CONTEXT_CHUNKS,
                resolved_user_query=generation_query,
            )

    response = await generate_response(generation_query, chunks, llm_client)
    response_str = str(response).strip()
    returned_status = MESSAGE_TO_STATUS.get(response_str)

    if returned_status is None:
        retrieval.update_conversation(
            session_state,
            user_query,
            response_str,
            SUCCESS,
            resolved_user_query=generation_query,
        )
        return response_str

    if returned_status in ERROR_STATUSES:
        return _stop_with_status(session_state, returned_status)

    if returned_status == NOT_IN_CONTEXT_TYPE and not has_previous_turn and not rewrite_attempted:
        print()
        print("[rag_control] First-turn generation returned NOT_IN_CONTEXT; attempting rewrite.")
        print()

        rewrite_attempted = True
        success, rewrite_output = await _perform_rewrite(session_state, user_query, llm_client, use_history=False)
        if not success:
            return rewrite_output

        retrieval_query = rewrite_output
        generation_query = rewrite_output

        print()
        print(f"[rag_control] rewritten retrieval_query = {retrieval_query!r}")
        print(f"[rag_control] rewritten generation_query = {generation_query!r}")
        print()

        retrieval_status, chunks = await _retrieve_chunks_safe(
            retrieval_query,
            qdrant_client,
            top_k=20,
        )
        if retrieval_status == UNKNOWN_RETRIEVAL_ERROR:
            return _stop_with_status(session_state, UNKNOWN_RETRIEVAL_ERROR)
        if not chunks:
            return _return_semantic_failure(
                session_state,
                user_query,
                NO_CONTEXT_CHUNKS,
                resolved_user_query=generation_query,
            )

        response = await generate_response(generation_query, chunks, llm_client)
        response_str = str(response).strip()
        returned_status = MESSAGE_TO_STATUS.get(response_str)

        if returned_status is None:
            retrieval.update_conversation(
                session_state,
                user_query,
                response_str,
                SUCCESS,
                resolved_user_query=generation_query,
            )
            return response_str

        if returned_status in ERROR_STATUSES:
            return _stop_with_status(session_state, returned_status)

        if returned_status == NOT_IN_CONTEXT_TYPE:
            return _return_semantic_failure(
                session_state,
                user_query,
                NOT_IN_CONTEXT_TYPE,
                resolved_user_query=generation_query,
            )

        return _return_semantic_failure(
            session_state,
            user_query,
            NOT_IN_CONTEXT_TYPE,
            resolved_user_query=generation_query,
        )

    return _return_semantic_failure(
        session_state,
        user_query,
        NOT_IN_CONTEXT_TYPE,
        resolved_user_query=generation_query,
    )