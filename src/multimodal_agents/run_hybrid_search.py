import json
import os
import sys
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from multimodal_agents.hybrid_search import (
    bm25_sparse,
    inverse_document_frequency,
    tokenize,
)
from multimodal_agents.run_qdrant_search import point_id, request

COLLECTION = "hybrid_incidents"
TENANT = "tenant-blue"

RERANK_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "best_object_id": {"type": ["string", "null"]},
        "evidence_quote": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
    "required": [
        "supported",
        "best_object_id",
        "evidence_quote",
        "reason",
    ],
    "additionalProperties": False,
}


def embed(client: genai.Client, text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values or [])


def filter_payload() -> dict:
    return {
        "must": [
            {"key": "tenant_id", "match": {"value": TENANT}},
        ]
    }


def points(response: dict) -> list[dict]:
    return response["result"]["points"]


def query_leg(vector: object, using: str, limit: int = 4) -> list[dict]:
    response = request(
        "POST",
        f"/collections/{COLLECTION}/points/query",
        {
            "query": vector,
            "using": using,
            "filter": filter_payload(),
            "limit": limit,
            "with_payload": True,
        },
    )
    return points(response)


def query_rrf(
    dense: list[float],
    sparse: dict[str, list[int] | list[float]],
    limit: int = 4,
) -> tuple[float, list[dict]]:
    started = perf_counter()
    prefetch = [
        {"query": dense, "using": "dense", "limit": limit},
    ]
    if sparse["indices"]:
        prefetch.append(
            {"query": sparse, "using": "sparse", "limit": limit}
        )
    response = request(
        "POST",
        f"/collections/{COLLECTION}/points/query",
        {
            "prefetch": prefetch,
            "query": {"fusion": "rrf"},
            "filter": filter_payload(),
            "limit": limit,
            "with_payload": True,
        },
    )
    return round((perf_counter() - started) * 1000, 2), points(response)


def simplify(hits: list[dict]) -> list[dict]:
    return [
        {
            "rank": rank,
            "object_id": hit["payload"]["object_id"],
            "score": round(hit["score"], 6),
        }
        for rank, hit in enumerate(hits, start=1)
    ]


def rerank(
    client: genai.Client,
    query: str,
    hits: list[dict],
) -> tuple[float, dict]:
    candidates = [
        {
            "object_id": hit["payload"]["object_id"],
            "text": hit["payload"]["text"],
        }
        for hit in hits
    ]
    prompt = (
        "Decide whether any candidate directly supports the query. "
        "Do not infer facts absent from candidate text. If supported, choose "
        "one object and copy a short exact evidence quote. Otherwise set "
        "supported false and both nullable fields null.\n"
        f"Query: {query}\nCandidates: {json.dumps(candidates)}"
    )
    started = perf_counter()
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=RERANK_SCHEMA,
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(disable=True)
            ),
        ),
    )
    return (
        round((perf_counter() - started) * 1000),
        json.loads(response.text),
    )


def main() -> None:
    output = Path(sys.argv[1])
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    documents = [
        {
            "object_id": "incident:inc-4827",
            "text": (
                "Reference INC-4827. Checkout receipts arrive late after a "
                "completed payment."
            ),
        },
        {
            "object_id": "incident:checkout-authorization",
            "text": (
                "Customers wait for an order confirmation after card "
                "authorization."
            ),
        },
        {
            "object_id": "incident:search-errors",
            "text": "Search API errors exceeded the release threshold.",
        },
        {
            "object_id": "runbook:receipt-worker",
            "text": (
                "Restart the checkout worker when receipt generation is "
                "delayed."
            ),
        },
        {
            "object_id": "release:inc-4828",
            "text": "INC-4828 fixed catalog caching during deployment.",
        },
        {
            "object_id": "note:vision",
            "text": "Vision API remained within its error budget.",
        },
    ]
    texts = [document["text"] for document in documents]
    idf = inverse_document_frequency(texts)
    average_length = sum(len(tokenize(text)) for text in texts) / len(texts)
    dense_vectors = [
        embed(client, "task: document | " + text) for text in texts
    ]
    sparse_vectors = [
        bm25_sparse(
            text,
            idf,
            document_length=len(tokenize(text)),
            average_length=average_length,
        )
        for text in texts
    ]
    request(
        "PUT",
        f"/collections/{COLLECTION}",
        {
            "vectors": {"dense": {"size": 768, "distance": "Cosine"}},
            "sparse_vectors": {"sparse": {}},
        },
    )
    request(
        "PUT",
        f"/collections/{COLLECTION}/index?wait=true",
        {"field_name": "tenant_id", "field_schema": "keyword"},
    )
    request(
        "PUT",
        f"/collections/{COLLECTION}/points?wait=true",
        {
            "points": [
                {
                    "id": point_id(document["object_id"]),
                    "vector": {
                        "dense": dense,
                        "sparse": sparse,
                    },
                    "payload": {
                        **document,
                        "tenant_id": TENANT,
                    },
                }
                for document, dense, sparse in zip(
                    documents,
                    dense_vectors,
                    sparse_vectors,
                    strict=True,
                )
            ]
        },
    )

    queries = [
        {
            "name": "exact_identifier",
            "text": "INC-4827",
            "expected": "incident:inc-4827",
        },
        {
            "name": "semantic_paraphrase",
            "text": "proof of purchase appears too slowly after paying",
            "expected": "incident:inc-4827",
        },
        {
            "name": "unsupported_secret",
            "text": "Which database password was leaked?",
            "expected": None,
        },
    ]
    results = []
    for query in queries:
        dense = embed(client, "task: retrieval | query: " + query["text"])
        sparse = bm25_sparse(query["text"], idf)
        dense_hits = query_leg(dense, "dense")
        sparse_hits = (
            query_leg(sparse, "sparse") if sparse["indices"] else []
        )
        fusion_ms, fused_hits = query_rrf(dense, sparse)
        rerank_ms, decision = rerank(client, query["text"], fused_hits)
        results.append(
            {
                **query,
                "dense": simplify(dense_hits),
                "sparse": simplify(sparse_hits),
                "rrf": simplify(fused_hits),
                "fusion_latency_ms": fusion_ms,
                "rerank_latency_ms": rerank_ms,
                "reranker": decision,
            }
        )
    artifact = {
        "engine": "qdrant-1.19.1",
        "dense_model": "gemini-embedding-2",
        "sparse_method": "client-bm25",
        "reranker": "gemini-3.8-flash",
        "corpus_size": len(documents),
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
