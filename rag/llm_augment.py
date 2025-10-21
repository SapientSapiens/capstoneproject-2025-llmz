from typing import List, Dict

NOT_IN_CONTEXT = "Not in context"
INFORMATION_NOT_FOUND_MSG = "I don't have information on that survival topic in my knowledge base."

def generate_response(
        user_query: str,
        context_chunks: List[Dict],  
        llm_client,
        model: str = "gpt-4o-mini",
        context_char_limit: int = 80000,
        temperature: float = 0.2,
   ):

    # 1) Sort/prepare chunks (simple ordering by provided score — not a neural re-ranker)
    chunks = list(context_chunks or [])
    #if chunks and isinstance(chunks[0], dict) and "score" in chunks[0]:
        # This is just ordering by the retrieval score (descending). True re-ranking is a separate model step.
        #chunks = sorted(chunks, key=lambda c: c.get("score", 0), reverse=True)

    # 2) Assemble context with provenance markers until char limit
    assembled = []
    length = 0
    for i, c in enumerate(chunks):
        cid = c.get("id", f"chunk_{i}")
        text = c.get("text", "") or ""
        block = f"[SOURCE: {cid}]\n{text}\n\n"
        if length + len(block) > context_char_limit:
            break
        assembled.append(block)
        length += len(block)

    context = "".join(assembled).strip()
    if not context:
        return INFORMATION_NOT_FOUND_MSG

    # 3) Strict system prompt (grounding)
    system_prompt = (
        "You are a Survival Guidance assistant that intelligently extracts the factual information and procedural knowledge "
        "from the supplied Context. Use ONLY the text in Context. Do NOT use external knowledge or assumptions. "
        f"If the answer cannot be derived from the Context, respond EXACTLY with: {NOT_IN_CONTEXT}\n"
        "Be concise and factual with the required information for the user."
    )

    # 4) Compose user prompt (question + context)
    user_prompt = (
        f"Question:\n{user_query}\n\n"
        f"Context (each block has provenance):\n\n{context}\n\n"
        "Task:\nUsing ONLY the Context above, answer the question. "
        f"If the required information is missing or not at all present, reply EXACTLY:{NOT_IN_CONTEXT}\n"
        "Be concise and factual with all the required information for the user from the supplied context"
    )

    # Debug prints (single set)
    print("SYSTEM PROMPT:\n", system_prompt)
    print("\nUSER PROMPT:\n", user_prompt)
    print("\n------------------ CALLING LLM ------------------\n")
    

    # 5) Call LLM (note: no max_tokens/timeout args)
    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
    except Exception:
        # If LLM call fails, prefer safe failure
        return INFORMATION_NOT_FOUND_MSG

    # FOR FASTAPI IMPLEMENTATION: If the client returned a coroutine (async client), run it from sync code
    import inspect, asyncio
    if inspect.isawaitable(resp):
        # run in new event loop (safe from sync thread)
        resp = asyncio.run(resp)
    
    # 6) Extract model output (handle common shapes)
    raw = None
    if hasattr(resp, "choices"):
        try:
            raw = resp.choices[0].message.content
        except Exception:
            raw = None
    elif isinstance(resp, dict) and "choices" in resp:
        raw = resp["choices"][0]["message"]["content"]
    else:
        raw = str(resp)

    if raw is None:
        return INFORMATION_NOT_FOUND_MSG

    text = raw.strip()
    # print(f"\n----- PROMPT SENT TO LLM -----\n{user_prompt}\n------------------------------\n")
    print(f"LLM RAW RESPONSE: {text}\n")

    # 7) Enforce exact failure token
    if text.strip().lower() == NOT_IN_CONTEXT.lower():
        return INFORMATION_NOT_FOUND_MSG

    #print(f"\n----- PROMPT SENT TO LLM -----\n{user_prompt}\n------------------------------\n")
    #print(f"LLM RAW RESPONSE: {text}\n")
    return text

def rewrite_query_for_qdrant(
        latest_user_message: str,
        last_llm_reply: str,
        current_user_question: str,
        llm_client,
        model: str = "gpt-4o-mini",
    ):

    system = (
        "You are a concise query rewriter for vector search in a RAG systm "
        "Given the assistant's last reply, the user's latest message, and the current user question "
        "(which previously returned no useful search results from the Knowledge Base), produce ONE single-sentence, standalone, "
        "human-language search query suitable for retrieving relevant chunks. "
        "Do NOT invent facts. If you cannot produce a safe rewrite without adding facts, return the current user question unchanged. "
    )

    user_prompt = (
        f"ASSISTANT_REPLY:\n{(last_llm_reply or '').strip()}\n\n"
        f"LATEST_USER_MESSAGE:\n{(latest_user_message or '').strip()}\n\n"
        f"CURRENT_USER_QUESTION (no/low-quality chunks):\n{(current_user_question or '').strip()}\n\n"
        "Return the question in only one sentence."
    )

    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
    except Exception:
        return " ".join(current_user_question.split())

    # FOR FASTAPI IMPLEMENTATION:  handle async client returning coroutine
    import inspect, asyncio
    if inspect.isawaitable(resp):
        resp = asyncio.run(resp)

    # extract text (handle common response shapes)
    raw = None
    if hasattr(resp, "choices"):
        try:
            raw = resp.choices[0].message.content
        except Exception:
            raw = None
    elif isinstance(resp, dict) and "choices" in resp:
        raw = resp["choices"][0]["message"]["content"]
    else:
        raw = str(resp)

    if not raw:
        return " ".join(current_user_question.split())

    # keep first non-empty line, strip wrapping quotes, collapse whitespace
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if (line.startswith('"') and line.endswith('"')) or (line.startswith("'") and line.endswith("'")):
            line = line[1:-1].strip()
        final_rewritten_query = " ".join(line.split())
        print(f"📝 Rewritten query: {final_rewritten_query}")
        return final_rewritten_query

    final_rewritten_query = " ".join(current_user_question.split())
    print(f"Rewritten query:: {final_rewritten_query}")
    return final_rewritten_query