import json
import os
import sys
import urllib.request
import uuid
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

BASE_URL = "http://127.0.0.1:6333"
COLLECTION = "multimodal_evidence"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def point_id(object_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, object_id))


def tenant_filter(tenant_id: str) -> dict:
    return {
        "must": [
            {
                "key": "tenant_id",
                "match": {"value": tenant_id},
            }
        ]
    }


def embed(client: genai.Client, content: object) -> list[float]:
    response = client.models.embed_content(
        model="gemini-embedding-2",
        contents=content,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(response.embeddings[0].values or [])


def main() -> None:
    output = Path(sys.argv[1])
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    items = [
        {
            "object_id": "report:p1:paragraph:1",
            "object_type": "paragraph",
            "content": "The release decision depends on service metrics.",
            "contains_answer": False,
        },
        {
            "object_id": "report:p1:table:1",
            "object_type": "table",
            "content": (
                "Service error rates: Vision API 0.8 percent pass; "
                "Search API 3.4 percent investigate."
            ),
            "contains_answer": True,
        },
        {
            "object_id": "report:p1:figure:1",
            "object_type": "image",
            "path": "fixtures/document-error-rates.png",
            "contains_answer": True,
        },
    ]
    vectors = []
    for item in items:
        if item["object_type"] == "image":
            content = types.Part.from_bytes(
                data=Path(str(item["path"])).read_bytes(),
                mime_type="image/png",
            )
        else:
            content = "task: document | " + str(item["content"])
        vectors.append(embed(client, content))

    query_text = "Which service exceeds the threshold?"
    query = embed(client, "task: retrieval | query: " + query_text)
    request(
        "PUT",
        f"/collections/{COLLECTION}",
        {"vectors": {"evidence": {"size": 768, "distance": "Cosine"}}},
    )
    for field in ("tenant_id", "object_type", "source_id"):
        request(
            "PUT",
            f"/collections/{COLLECTION}/index?wait=true",
            {"field_name": field, "field_schema": "keyword"},
        )

    points = []
    for item, vector in zip(items, vectors, strict=True):
        payload = {
            "object_id": item["object_id"],
            "object_type": item["object_type"],
            "tenant_id": "tenant-blue",
            "source_id": "release-report-v1",
            "contains_answer": item["contains_answer"],
            "embedding_model": "gemini-embedding-2",
            "dimensions": 768,
        }
        points.append(
            {
                "id": point_id(str(item["object_id"])),
                "vector": {"evidence": vector},
                "payload": payload,
            }
        )
    decoy = dict(points[1])
    decoy["id"] = point_id("other-tenant:report:p1:table:1")
    decoy["payload"] = dict(points[1]["payload"])
    decoy["payload"]["tenant_id"] = "tenant-red"
    decoy["payload"]["object_id"] = "other-tenant:report:p1:table:1"
    points.append(decoy)
    request(
        "PUT",
        f"/collections/{COLLECTION}/points?wait=true",
        {"points": points},
    )

    started = perf_counter()
    response = request(
        "POST",
        f"/collections/{COLLECTION}/points/query",
        {
            "query": query,
            "using": "evidence",
            "filter": tenant_filter("tenant-blue"),
            "limit": 3,
            "with_payload": True,
        },
    )
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    results = response["result"]["points"]
    assert all(
        hit["payload"]["tenant_id"] == "tenant-blue" for hit in results
    )
    assert not any(
        hit["payload"]["object_id"].startswith("other-tenant")
        for hit in results
    )
    service = request("GET", "/")
    artifact = {
        "engine": "qdrant",
        "engine_version": service["version"],
        "collection": COLLECTION,
        "dimensions": 768,
        "distance": "Cosine",
        "query": query_text,
        "required_tenant": "tenant-blue",
        "excluded_decoy_tenant": "tenant-red",
        "latency_ms": elapsed_ms,
        "payload_indexes": ["tenant_id", "object_type", "source_id"],
        "results": [
            {
                "rank": rank,
                "score": round(hit["score"], 6),
                **hit["payload"],
            }
            for rank, hit in enumerate(results, start=1)
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
