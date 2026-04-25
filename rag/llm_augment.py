from typing import List, Dict, Any, Optional
import hashlib
import logging
import json

# For quick debugging only.
logging.basicConfig(level=logging.INFO)

NOT_IN_CONTEXT = "Not in context"

NO_CONTEXT_CHUNKS = "no_context_chunks"
NOT_IN_CONTEXT_TYPE = "not_in_context"
UNKNOWN_RETRIEVAL_ERROR = "unknown_retrieval_error"
LLM_AUTH_ERROR = "llm_auth_error"
LLM_QUOTA_ERROR = "llm_quota_error"
LLM_RATE_LIMIT = "llm_rate_limit"
LLM_PARSE_ERROR = "llm_parse_error"
LLM_UNKNOWN_ERROR = "llm_unknown_error"
SUCCESS = "success"

OP_ERROR_SUFFIX = " Conversational history state was not persisted for the current user question."

FAILURE_MESSAGE_MAP = {
    NO_CONTEXT_CHUNKS: "No relevant information was retrieved from the selected YouTube-playlists knowledge base for that query.",
    NOT_IN_CONTEXT_TYPE: "The retrieved context does not contain enough information to answer that question.",
    UNKNOWN_RETRIEVAL_ERROR: "The knowledge retrieval step failed unexpectedly. Please try again." + OP_ERROR_SUFFIX,
    LLM_AUTH_ERROR: "Service configuration error." + OP_ERROR_SUFFIX,
    LLM_QUOTA_ERROR: "Service unavailable: usage limit reached. Try again later." + OP_ERROR_SUFFIX,
    LLM_RATE_LIMIT: "Too many requests. Please slow down and retry." + OP_ERROR_SUFFIX,
    LLM_PARSE_ERROR: "The language model returned an unreadable response. Please try again." + OP_ERROR_SUFFIX,
    LLM_UNKNOWN_ERROR: "The language model is temporarily unavailable. Please try again." + OP_ERROR_SUFFIX,
}

SEED = 42

logger = logging.getLogger(__name__)


def stable_context_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _log_event(status: str, detail: str = "") -> None:
    print(f"[llm_augment] status={status}")
    if detail:
        print(f"[llm_augment] detail={detail}")


def _map_failure_to_user_message(status: str) -> str:
    return FAILURE_MESSAGE_MAP.get(status, FAILURE_MESSAGE_MAP[LLM_UNKNOWN_ERROR])


def _classify_llm_exception(exc: Exception) -> str:
    err_str = str(exc).lower()

    if (
        "incorrect api key" in err_str
        or "invalid_api_key" in err_str
        or "authenticationerror" in err_str
        or "authentication" in err_str
        or "unauthorized" in err_str
        or "401" in err_str
    ):
        return LLM_AUTH_ERROR

    if (
        "insufficient_quota" in err_str
        or "quota" in err_str
        or "billing" in err_str
    ):
        return LLM_QUOTA_ERROR

    if (
        "rate limit" in err_str
        or "ratelimit" in err_str
        or "429" in err_str
        or "too many requests" in err_str
    ):
        return LLM_RATE_LIMIT

    return LLM_UNKNOWN_ERROR


def _extract_response_text(resp: Any) -> Optional[str]:
    try:
        if hasattr(resp, "choices"):
            raw = resp.choices[0].message.content
        elif isinstance(resp, dict) and "choices" in resp:
            raw = resp["choices"][0]["message"]["content"]
        else:
            return None
    except Exception:
        return None

    if raw is None:
        return None

    if isinstance(raw, str):
        text = raw.strip()
        return text or None

    # Minimal support for content-part arrays from Chat Completions
    if isinstance(raw, list):
        parts = []

        for part in raw:
            # SDK object style
            if hasattr(part, "type"):
                part_type = getattr(part, "type", None)
                if part_type == "text":
                    text_value = getattr(part, "text", None)
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())
                elif part_type == "refusal":
                    refusal_value = getattr(part, "refusal", None)
                    if isinstance(refusal_value, str) and refusal_value.strip():
                        parts.append(refusal_value.strip())

            # dict style
            elif isinstance(part, dict):
                part_type = part.get("type")
                if part_type == "text":
                    text_value = part.get("text")
                    if isinstance(text_value, str) and text_value.strip():
                        parts.append(text_value.strip())
                elif part_type == "refusal":
                    refusal_value = part.get("refusal")
                    if isinstance(refusal_value, str) and refusal_value.strip():
                        parts.append(refusal_value.strip())

        if parts:
            return "\n".join(parts)

    return None


def _extract_structured_payload(resp: Any) -> Optional[Dict[str, Any]]:
    raw = _extract_response_text(resp)
    if raw is None:
        return None

    try:
        parsed = json.loads(raw)
    except Exception:
        return None

    return parsed if isinstance(parsed, dict) else None


async def generate_response(
    user_query: str,
    context_chunks: List[Dict],
    llm_client,
    model: str = "gpt-5.4",
    context_char_limit: int = 100000,
    temperature: float = 0.0,
    seed=SEED
):
    try:
        chunks = list(context_chunks or [])
    except Exception as e:
        status = UNKNOWN_RETRIEVAL_ERROR
        _log_event(status, f"{type(e).__name__}: {e}")
        return _map_failure_to_user_message(status)

    assembled: List[str] = []
    length = 0
    chunk_ids: List[str] = []

    try:
        for i, c in enumerate(chunks):
            cid = c.get("id", f"chunk_{i}")
            text = c.get("text", "") or ""
            block = f"[SOURCE: {cid}]\n{text}\n\n"

            if length + len(block) > context_char_limit:
                break

            assembled.append(block)
            chunk_ids.append(str(cid))
            length += len(block)
    except Exception as e:
        status = UNKNOWN_RETRIEVAL_ERROR
        _log_event(status, f"{type(e).__name__}: {e}")
        return _map_failure_to_user_message(status)

    context = "".join(assembled).strip()

    if not context:
        status = NO_CONTEXT_CHUNKS
        _log_event(status, "No usable chunks were assembled from retrieval output.")
        return _map_failure_to_user_message(status)

    context_hash = stable_context_hash(context)

    system_prompt = (
        "You are a Survival Guidance assistant that intelligently extracts the factual information\n"
        "and procedural knowledge from the supplied Context.\n"
        "Use ONLY the text in Context. Do NOT use external knowledge or assumptions to answer the user query.\n"
        "The answer should be detailed and comprehensive unless explicitly asked by the user query not to be.\n"
        "In generating the answer, please check all parts of the Context for answering this question; do not leave any out. "
        "You must return a JSON object matching the provided schema.\n"
        f"If the answer cannot be derived from the Context, return status='not_in_context' and message='{NOT_IN_CONTEXT}'."
    )

    user_prompt = (
        f"Question:\n{user_query}\n\n"
        f"Context (each block has provenance):\n\n{context}\n\n"
        "Task:\n"
        "Answer the Question using only the Context above.\n"
        "Rules:\n"
        "1. Read the entire Context before answering.\n"
        "2. Use only information explicitly present in the Context.\n"
        "3. Do not use external knowledge, assumptions, or guesswork.\n"
        "4. First identify the exact task requested by the Question, including but not limited to category, scope, exclusions, and formatting constraints.\n"
        "5. If the Question asks for a list, names, items, records, types, or examples, include all items explicitly supported by the Context that satisfy the Question's constraints, including relevant incidental mentions that also satisfy those constraints.\n"
        "6. Do not include related, broader, narrower, or partially matching items unless the Question explicitly asks for them.\n"
        "7. If the Question asks for steps, guidance, explanation, or comparison, give a direct answer based only on the Context.\n"
        "8. When the Question asks for a list, return the list clearly in the message using the format requested by the user.\n"
        "9. For list answers, deduplicate only clearly repeated items unless the Question asks for exact repeated mentions.\n"
        "10. If the Question includes exclusions or negative qualifiers, only include information that the Context explicitly indicates is not excluded by those terms.\n"
        "11. If the Question asks for a table or tabular output, include the table directly in the message using markdown table formatting.\n"
        "12. If the Question asks for paragraphs, lists, tables, or a combination of formats, include those formats directly in the message as requested.\n"
        "13. If the Context does not support an answer, return status='not_in_context' and message='Not in context'.\n"
        "14. Otherwise return status='success' and place the full answer only in the message field.\n"
    )
    logger.info("SYSTEM PROMPT:\n%s", system_prompt)
    logger.info("USER PROMPT:\n%s", user_prompt)
    logger.info("------------------ CALLING LLM ------------------")

    logger.info(
        "RAG request | model=%s | temperature=%s | seed=%s | query=%r | chunk_ids=%s | context_hash=%s",
        model,
        temperature,
        seed,
        user_query,
        chunk_ids,
        context_hash,
    )

    try:
        resp = await llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            seed=seed,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "rag_answer",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["success", "not_in_context"],
                            },
                            "message": {
                                "type": "string",
                            },
                        },
                        "required": ["status", "message"],
                    },
                },
            },
        )

        logger.info(
            "LLM response | system_fingerprint=%s | response_id=%s | model=%s",
            getattr(resp, "system_fingerprint", None),
            getattr(resp, "id", None),
            getattr(resp, "model", model),
        )

    except Exception as e:
        status = _classify_llm_exception(e)
        _log_event(status, f"{type(e).__name__}: {e}")
        return _map_failure_to_user_message(status)

    payload = _extract_structured_payload(resp)

    if payload is None:
        status = LLM_PARSE_ERROR
        _log_event(status, "Structured response could not be parsed as JSON.")
        return _map_failure_to_user_message(status)

    logger.info(
        "LLM STRUCTURED RESPONSE:\n%s",
        json.dumps(payload, ensure_ascii=False, indent=2),
    )

    status_value = str(payload.get("status", "")).strip().lower()
    message = str(payload.get("message", "")).strip()

    if status_value == "not_in_context":
        status = NOT_IN_CONTEXT_TYPE
        _log_event(status, "LLM explicitly returned structured not_in_context.")
        return _map_failure_to_user_message(status)

    if status_value != "success":
        status = LLM_PARSE_ERROR
        _log_event(status, f"Unexpected structured status: {status_value!r}")
        return _map_failure_to_user_message(status)

    if not message:
        status = LLM_PARSE_ERROR
        _log_event(status, "Structured success response had empty message.")
        return _map_failure_to_user_message(status)

    _log_event(SUCCESS, "LLM returned a successful structured text answer.")
    return message


async def rewrite_query_for_qdrant(
    latest_user_message: str,
    last_llm_reply: str,
    current_user_question: str,
    llm_client,
    model: str = "gpt-4o-mini",
    seed=SEED,
):
    """
    Returns:
    - rewritten standalone query string on success
    - mapped LLM error string on LLM failure / parse failure
    """

    system = (
        "You are a query rewriter for the retrieval step of a RAG system. "
        "The previous resolved user query and previous assistant reply may be empty if this is the first question in the conversation. "
        "First decide whether CURRENT_USER_QUESTION continues the same topic as the immediately previous turn. "
        "If the topic continues, use previous-turn context only to resolve pronouns, ellipsis, omitted nouns, shorthand, or likely typos. "
        "If the topic changes, ignore the previous-turn context completely and rewrite only from CURRENT_USER_QUESTION. "
        "Do not carry over entities, hazards, objects, diseases, eruptions, events, or facts from the previous topic into a new topic. "
        "A topic change must still be detected even if the question begins with words like 'and', 'what type', 'what kind', 'here', 'there', 'what about', or similar follow-up wording. "
        "If CURRENT_USER_QUESTION contains vague references such as 'it', 'them', 'that', 'these', 'those', or similar incomplete expressions, and the topic continues, resolve them using the concrete topic from the previous turn. "
        "Never replace a missing topic with vague placeholder words such as 'information', 'details', 'facts', 'content', 'things', or similar generic filler words. "
        "Always produce exactly one standalone retrieval query sentence with explicit keyword nouns. "
        "Preserve all semantic constraints from the original question, including inclusion criteria, exclusion criteria, category restrictions, and scope. "
        #"Do not carry over presentation-only instructions such as table format, bullet format, or desired answer length unless they are necessary to preserve the meaning of the query. "
        "Preserve any explicit output-format or answer-structure instruction stated in the CURRENT_USER_QUESTION, such as table, tabular format, bullet list, JSON, CSV, or requested answer length, when it affects the final answer. Do not invent or carry over such instructions from prior turns unless the CURRENT_USER_QUESTION clearly refers back to them. Remove only wording that is purely stylistic. "
        "If PREVIOUS_ASSISTANT_REPLY is empty or is only a generic failure/control message and does not contain topic-specific content, ignore it completely. "
        "If no rewrite is needed, restate the current question as a standalone retrieval query anyway. "
        "Return a JSON object matching the schema. "
        "Always set status='success'."
    )

    user_prompt = (
        f"PREVIOUS_RESOLVED_USER_QUERY:\n{(latest_user_message or '').strip()}\n\n"
        f"PREVIOUS_ASSISTANT_REPLY:\n{(last_llm_reply or '').strip()}\n\n"
        f"CURRENT_USER_QUESTION:\n{(current_user_question or '').strip()}\n\n"
        "Return only the JSON object."
    )

    try:
        resp = await llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            seed=seed,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "rewritten_query",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "status": {
                                "type": "string",
                                "enum": ["success"],
                            },
                            "rewritten_query": {
                                "type": "string",
                            },
                        },
                        "required": ["status", "rewritten_query"],
                    },
                },
            },
        )

    except Exception as e:
        status = _classify_llm_exception(e)
        _log_event(status, f"rewrite_query_for_qdrant failed: {type(e).__name__}: {e}")
        return _map_failure_to_user_message(status)

    payload = _extract_structured_payload(resp)

    if payload is None:
        status = LLM_PARSE_ERROR
        _log_event(status, "rewrite_query_for_qdrant structured response could not be parsed as JSON.")
        return _map_failure_to_user_message(status)

    status_value = str(payload.get("status", "")).strip().lower()
    rewritten_query = str(payload.get("rewritten_query", "")).strip()

    if status_value != "success":
        status = LLM_PARSE_ERROR
        _log_event(status, f"rewrite_query_for_qdrant returned unexpected status: {status_value!r}")
        return _map_failure_to_user_message(status)

    if not rewritten_query:
        status = LLM_PARSE_ERROR
        _log_event(status, "rewrite_query_for_qdrant returned empty rewritten_query.")
        return _map_failure_to_user_message(status)

    logger.info("Rewritten query: %s", rewritten_query)
    return rewritten_query