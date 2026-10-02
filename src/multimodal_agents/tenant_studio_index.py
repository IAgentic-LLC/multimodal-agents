"""Real per-tenant OpenSearch isolation for the bring-your-own-data studio.

Deliberately separate from opensearch_index.py, which backs Chapter 37's
own shipped, tested claims about the book's fixed reference corpus. This
module is product-direction work beyond the book: real researchers
uploading their own data, isolated from each other and from the book's
own reference corpus.

Isolation is enforced by OpenSearch itself via a filtered alias per
tenant, not by trusting every caller to always filter correctly: a query
against a tenant's own alias can only ever see that tenant's own
documents, confirmed in tests/test_tenant_studio_index.py by writing two
tenants' overlapping content and proving neither alias ever returns the
other's documents, even for queries that would otherwise match.
"""

from __future__ import annotations

import urllib.parse

from multimodal_agents.opensearch_index import HYBRID_PIPELINE, HYBRID_SEARCH_PIPELINE, request

TENANT_INDEX = "tenant_evidence"
RESERVED_TENANT_IDS = frozenset({"book-reference"})
EMBEDDING_DIMENSIONS = 768

TENANT_INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "search.default_pipeline": HYBRID_PIPELINE,
        },
    },
    "mappings": {
        "properties": {
            "doc_id": {"type": "keyword"},
            "tenant_id": {"type": "keyword"},
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


def tenant_alias(tenant_id: str) -> str:
    return f"{TENANT_INDEX}__{tenant_id}"


def validate_tenant_id(tenant_id: str) -> None:
    if not tenant_id or tenant_id in RESERVED_TENANT_IDS:
        raise ValueError(f"invalid tenant_id: {tenant_id!r}")
    if not tenant_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"tenant_id must be alphanumeric with - or _: {tenant_id!r}")


def ensure_tenant_index(reset: bool = False) -> None:
    exists = True
    try:
        request("GET", f"/{TENANT_INDEX}")
    except RuntimeError:
        exists = False
    if exists and not reset:
        return
    if exists and reset:
        request("DELETE", f"/{TENANT_INDEX}")
    request("PUT", f"/_search/pipeline/{HYBRID_PIPELINE}", HYBRID_SEARCH_PIPELINE)
    request("PUT", f"/{TENANT_INDEX}", TENANT_INDEX_MAPPING)


def ensure_tenant_alias(tenant_id: str) -> None:
    """Create or replace this tenant's filtered alias. OpenSearch enforces
    the filter at query time: a search against this alias can only ever
    match documents whose tenant_id equals this tenant's own id, regardless
    of what the query itself asks for.
    """
    validate_tenant_id(tenant_id)
    alias = tenant_alias(tenant_id)
    request(
        "POST",
        "/_aliases",
        {
            "actions": [
                {
                    "add": {
                        "index": TENANT_INDEX,
                        "alias": alias,
                        "filter": {"term": {"tenant_id": tenant_id}},
                    }
                }
            ]
        },
    )


def index_tenant_document(tenant_id: str, doc_id: str, document: dict) -> None:
    """Write one document, stamped with its real tenant_id. Isolation at
    read time comes from the alias filter, not from this write being
    correct, but the field must still be set correctly for the document
    to be visible to its own tenant at all.
    """
    validate_tenant_id(tenant_id)
    ensure_tenant_alias(tenant_id)
    stamped = {**document, "tenant_id": tenant_id}
    safe_id = urllib.parse.quote(f"{tenant_id}::{doc_id}", safe="")
    request("PUT", f"/{TENANT_INDEX}/_doc/{safe_id}", stamped)


def get_tenant_document(tenant_id: str, doc_id: str) -> dict | None:
    """Look up one document through the tenant's own alias, the same
    real enforced boundary every tenant query already goes through: a
    doc_id that exists but belongs to a different tenant resolves to
    None here, not to that other tenant's document.
    """
    validate_tenant_id(tenant_id)
    alias = tenant_alias(tenant_id)
    safe_id = urllib.parse.quote(f"{tenant_id}::{doc_id}", safe="")
    try:
        result = request("GET", f"/{alias}/_doc/{safe_id}")
    except RuntimeError:
        return None
    if not result.get("found"):
        return None
    return result.get("_source")


def refresh_tenant_index() -> None:
    request("POST", f"/{TENANT_INDEX}/_refresh")


def tenant_hybrid_query(tenant_id: str, text_query: str, vector: list[float], size: int = 5) -> dict:
    """Query strictly through this tenant's own alias. Even a caller that
    forgot to filter, or a bug elsewhere in this module, cannot surface
    another tenant's documents this way: the alias itself is the boundary.
    """
    validate_tenant_id(tenant_id)
    alias = tenant_alias(tenant_id)
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
        "_source": ["doc_id", "tenant_id", "modality", "text", "evidence_ids", "source_file"],
    }
    return request("POST", f"/{alias}/_search?search_pipeline={HYBRID_PIPELINE}", body)
