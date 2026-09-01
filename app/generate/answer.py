"""Grounded generation with mandatory citation and a hard refusal path.

Generation is provider-agnostic via the OpenAI-compatible client: it points at
whatever ``DEEPSEEK_BASE_URL``/``GEN_MODEL`` say. In this project that's a local
**Ollama** server (``http://localhost:11434/v1``, model ``qwen2.5:7b-instruct``);
set a real DeepSeek key + URL to switch. The grounding contract is unchanged —
answer only from CONTEXT, cite every claim, refuse rather than guess.
"""
from openai import OpenAI

from app.config import SETTINGS
from app.retrieval.metadata import resolve_manual
from app.retrieval.hybrid import retrieve
from app.retrieval.rerank import rerank
from app.retrieval.citations import lookup, source_label

_client = OpenAI(api_key=SETTINGS.deepseek_api_key,
                 base_url=SETTINGS.deepseek_base_url)

SYSTEM = (
    "You are an automotive maintenance assistant. Answer the user's question "
    "using ONLY the manual excerpts provided in CONTEXT.\n"
    "Rules:\n"
    "  1. Ground every statement in the CONTEXT. Do not use outside knowledge.\n"
    "  2. After each factual claim, cite the source as "
    "[<make> <model> <year> - <section>].\n"
    "  3. If the CONTEXT does not contain the answer, reply exactly with the "
    "refusal message.\n"
    "  4. Never guess safety-critical values (pressures, torques, capacities, "
    "fluid types)."
)

REFUSAL = ("The provided manual does not specify this. Please consult the full "
           "manual or a qualified technician.")

# Questions whose answers must never be guessed — surfaced to the UI as a
# trust indicator, and a reminder that refusal is preferable to a wrong value.
_SAFETY_TERMS = (
    "pressure", "psi", "kpa", "torque", "capacity", "fluid", "coolant",
    "oil grade", "brake", "tyre", "tire", "tightening",
)


def _is_safety_critical(question: str) -> bool:
    q = question.lower()
    return any(t in q for t in _SAFETY_TERMS)


def answer(question: str, make: str | None = None, model: str | None = None,
           year: int | None = None, reasoning: bool = False) -> dict:
    manual_id = resolve_manual(make, model, year)
    fused = retrieve(question, manual_id)
    passages, top_score = rerank(question, fused)

    safety = _is_safety_critical(question)
    base = {
        "manual_id": manual_id,
        "scoped": manual_id is not None,
        "top_score": round(float(top_score), 4),
        "safety_critical": safety,
    }

    # Hard refusal: no passages, or nothing cleared the reranker threshold.
    if not passages or top_score < SETTINGS.refusal_score:
        return {**base, "text": REFUSAL, "citations": [], "sources": [],
                "refused": True}

    # Label each context passage with its real source so the model can cite
    # [Make Model - Section] as instructed (opaque chunk ids can't be cited).
    cids = [cid for cid, _ in passages]
    passage_text = {cid: txt for cid, txt in passages}
    details = lookup(cids)
    context = "\n\n".join(
        f"[{source_label(details.get(cid, {})) or cid}] {txt}"
        for cid, txt in passages
    )
    top_cid = cids[0]
    top_passage = passage_text[top_cid].strip().replace("\n", " ")
    if len(top_passage) > 500:
        top_passage = top_passage[:500].rsplit(" ", 1)[0] + "…"

    model_id = SETTINGS.reason_model if reasoning else SETTINGS.gen_model
    resp = _client.chat.completions.create(
        model=model_id,
        temperature=0.0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}\n\n"
                        f"(If CONTEXT lacks the answer, reply exactly: {REFUSAL})"},
        ],
    )
    text = resp.choices[0].message.content

    # Structured, de-duplicated sources for the UI citation chip.
    sources, seen = [], set()
    for cid in cids:
        info = details.get(cid)
        if not info:
            continue
        key = (info.get("manual_id"), info.get("section"))
        if key in seen:
            continue
        seen.add(key)
        sources.append({
            "label": source_label(info),
            "make": info.get("make"), "model": info.get("model"),
            "variant": info.get("variant"), "section": info.get("section"),
            "source_url": info.get("source_url"),
        })

    refused = text.strip() == REFUSAL.strip()
    return {**base, "text": text, "citations": cids, "sources": sources,
            "top_passage": top_passage, "refused": refused}
