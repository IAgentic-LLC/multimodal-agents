"""Real behaviors for the capstone's three new specialists: analysis,
visualization, and edit-proposal. Each grounds its answer in a real
hybrid-search hit from the OpenSearch evidence index; none invents a claim
when the index returns nothing above the confidence floor, and none of
them, including edit-proposal, ever mutates anything.
"""

from __future__ import annotations

import asyncio

from multimodal_agents.embedding import embed_text
from multimodal_agents.opensearch_index import (
    hybrid_query,
    lexical_confidence,
    visual_confidence,
)

MIN_LEXICAL_CONFIDENCE = 8.0
MIN_VISUAL_CONFIDENCE = 0.72
FULL_CORPUS_POOL = 100


async def _embed(question: str) -> list[float]:
    return await embed_text(question)


async def _search(question: str, vector: list[float], size: int = 5) -> list[dict]:
    response = await asyncio.to_thread(hybrid_query, question, vector, size)
    return response.get("hits", {}).get("hits", [])


async def _best_supported_hit(question: str, modality: str) -> dict | None:
    """The top hybrid hit of one modality, gated by a real raw score
    against that specific document rather than the hybrid pipeline's
    min-max-normalized score, which is always stretched toward 1.0 for
    whichever hit ranks first regardless of true relevance. Text is gated
    on lexical overlap; images carry no literal caption worth matching, so
    they are gated on raw embedding similarity instead.
    """
    vector = await _embed(question)
    hits = await _search(question, vector, size=FULL_CORPUS_POOL)
    candidates = [h for h in hits if h["_source"]["modality"] == modality]
    if not candidates:
        return None
    top = candidates[0]
    source = top["_source"]
    if modality == "image":
        confidence = await asyncio.to_thread(
            visual_confidence, vector, source["source_file"]
        )
        if confidence < MIN_VISUAL_CONFIDENCE:
            return None
        return top
    confidence = await asyncio.to_thread(
        lexical_confidence, question, source["source_file"]
    )
    if confidence < MIN_LEXICAL_CONFIDENCE:
        return None
    return top


async def analyze(question: str) -> dict:
    """Answer a question by citing the strongest real evidence hit."""
    top = await _best_supported_hit(question, "text")
    if top is None:
        return {
            "specialist": "analysis",
            "claim": "no supported evidence above the confidence floor",
            "evidence_ids": [],
        }
    source = top["_source"]
    return {
        "specialist": "analysis",
        "claim": source["text"],
        "evidence_ids": [source["source_file"]],
        "chapter": source["chapter"],
    }


async def visualize(question: str) -> dict:
    """Name the real retained figure that best answers a question."""
    top = await _best_supported_hit(question, "image")
    if top is None:
        return {
            "specialist": "visualization",
            "claim": "no retained figure matches this question",
            "evidence_ids": [],
        }
    source = top["_source"]
    return {
        "specialist": "visualization",
        "claim": f"chapter {source['chapter']} figure best answers this: {source['source_file']}",
        "evidence_ids": [source["source_file"]],
        "chapter": source["chapter"],
    }


async def propose_edit(question: str) -> dict:
    """Propose a bounded edit grounded in real evidence. Never mutates
    anything: the result is always a pending proposal, never applied.
    """
    top = await _best_supported_hit(question, "text")
    if top is None:
        return {
            "specialist": "edit-proposal",
            "claim": "no supported evidence to ground an edit proposal",
            "evidence_ids": [],
            "status": "refused",
        }
    source = top["_source"]
    return {
        "specialist": "edit-proposal",
        "claim": f"proposed edit grounded in {source['source_file']}: {question.strip()}",
        "evidence_ids": [source["source_file"]],
        "chapter": source["chapter"],
        "status": "proposed_pending_approval",
    }
