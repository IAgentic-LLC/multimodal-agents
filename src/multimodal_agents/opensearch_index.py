"""Thin raw-HTTP OpenSearch client and index/pipeline definitions for the
capstone's multimodal evidence index. No SDK dependency, matching the
book's existing Qdrant client convention in ``run_qdrant_search.py``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.getenv("OPENSEARCH_URL", "http://127.0.0.1:9200")
INDEX = "multimodal_evidence"
HYBRID_PIPELINE = "multimodal-hybrid-pipeline"
EMBEDDING_DIMENSIONS = 768


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"OpenSearch {method} {path} failed: {detail}") from error


INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "search.default_pipeline": HYBRID_PIPELINE,
        },
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "chapter": {"type": "integer"},
            "chapter_title": {"type": "text"},
            "modality": {"type": "keyword"},
            "text": {"type": "text", "analyzer": "english"},
            "evidence_ids": {"type": "keyword"},
            "source_file": {"type": "keyword"},
            "embedding": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIMENSIONS,
                "method": {
                    "name": "hnsw",
                    "engine": "lucene",
                    "space_type": "cosinesimil",
                },
            },
        }
    },
}

HYBRID_SEARCH_PIPELINE = {
    "description": "Normalize and combine BM25 and k-NN scores for the capstone's hybrid query.",
    "phase_results_processors": [
        {
            "normalization-processor": {
                "normalization": {"technique": "min_max"},
                "combination": {
                    "technique": "arithmetic_mean",
                    "parameters": {"weights": [0.4, 0.6]},
                },
            }
        }
    ],
}


def ensure_index(reset: bool = False) -> None:
    exists = True
    try:
        request("GET", f"/{INDEX}")
    except RuntimeError:
        exists = False
    if exists and not reset:
        return
    if exists and reset:
        request("DELETE", f"/{INDEX}")
    request("PUT", f"/_search/pipeline/{HYBRID_PIPELINE}", HYBRID_SEARCH_PIPELINE)
    request("PUT", f"/{INDEX}", INDEX_MAPPING)


def index_document(doc_id: str, document: dict) -> None:
    safe_id = urllib.parse.quote(doc_id, safe="")
    request("PUT", f"/{INDEX}/_doc/{safe_id}", document)


def refresh() -> None:
    request("POST", f"/{INDEX}/_refresh")


def lexical_confidence(text_query: str, source_file: str) -> float:
    """Raw BM25 score for one specific document, used as a fails-closed
    gate. The hybrid pipeline's min-max normalization always stretches the
    top hit toward 1.0 regardless of true relevance, so it cannot answer
    "is this actually a good match" on its own; a raw score can.
    """
    body = {
        "size": 1,
        "query": {
            "bool": {
                "must": [{"match": {"text": {"query": text_query}}}],
                "filter": [{"term": {"source_file": source_file}}],
            }
        },
    }
    result = request("POST", f"/{INDEX}/_search", body)
    hits = result.get("hits", {}).get("hits", [])
    return hits[0]["_score"] if hits else 0.0


def visual_confidence(vector: list[float], source_file: str) -> float:
    """Raw cosine k-NN score for one specific image document. Images carry
    no literal caption worth a BM25 match, so their fails-closed gate is
    the embedding similarity itself, filtered to that one document.
    """
    body = {
        "size": 1,
        "query": {
            "knn": {
                "embedding": {
                    "vector": vector,
                    "k": 1,
                    "filter": {"term": {"source_file": source_file}},
                }
            }
        },
    }
    result = request("POST", f"/{INDEX}/_search", body)
    hits = result.get("hits", {}).get("hits", [])
    return hits[0]["_score"] if hits else 0.0


def hybrid_query(text_query: str, vector: list[float], size: int = 5) -> dict:
    body = {
        "size": size,
        "query": {
            "hybrid": {
                "queries": [
                    {"match": {"text": {"query": text_query}}},
                    {"knn": {"embedding": {"vector": vector, "k": size}}},
                ]
            }
        },
        "_source": ["doc_id", "chapter", "chapter_title", "modality", "text", "evidence_ids", "source_file"],
    }
    return request(
        "POST",
        f"/{INDEX}/_search?search_pipeline={HYBRID_PIPELINE}",
        body,
    )
