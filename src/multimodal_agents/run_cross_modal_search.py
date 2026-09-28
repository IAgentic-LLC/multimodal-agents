import json
import os
import sys
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from multimodal_agents.run_qdrant_search import point_id, request

COLLECTION = "cross_modal_evidence"
TENANT = "tenant-blue"


def exact_filter(**values: str) -> dict:
    return {
        "must": [
            {"key": key, "match": {"value": value}}
            for key, value in values.items()
        ]
    }


def embed(client: genai.Client, content: object) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=content,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values or [])


def image_part(path: str) -> types.Part:
    return types.Part.from_bytes(
        data=Path(path).read_bytes(),
        mime_type="image/png",
    )


def search(vector: list[float], object_type: str) -> tuple[float, list[dict]]:
    started = perf_counter()
    response = request(
        "POST",
        f"/collections/{COLLECTION}/points/query",
        {
            "query": vector,
            "using": "evidence",
            "filter": exact_filter(
                tenant_id=TENANT,
                object_type=object_type,
            ),
            "limit": 3,
            "with_payload": True,
        },
    )
    latency = round((perf_counter() - started) * 1000, 2)
    return latency, response["result"]["points"]


def main() -> None:
    output = Path(sys.argv[1])
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    images = [
        {
            "object_id": "image:checkout-latency",
            "path": "runs/gate-5/scene-dashboard.png",
            "label": "checkout latency dashboard",
        },
        {
            "object_id": "image:search-error-rate",
            "path": "fixtures/document-error-rates.png",
            "label": "search error-rate chart",
        },
        {
            "object_id": "image:shape-grounding",
            "path": "runs/gate-4/shapes.png",
            "label": "shape grounding fixture",
        },
    ]
    incidents = [
        {
            "object_id": "incident:checkout-latency",
            "text": (
                "Checkout p95 latency reached 410 ms, above the 300 ms "
                "threshold. Catalog remained at 180 ms."
            ),
        },
        {
            "object_id": "incident:search-error-rate",
            "text": (
                "Search API error rate reached 3.4 percent and requires "
                "investigation. Vision API remained at 0.8 percent."
            ),
        },
        {
            "object_id": "incident:shape-grounding",
            "text": (
                "Visual grounding fixture containing a red circle, blue "
                "square, green triangle, and yellow rectangle."
            ),
        },
    ]
    image_vectors = [embed(client, image_part(item["path"])) for item in images]
    incident_vectors = [
        embed(client, "task: document | " + item["text"])
        for item in incidents
    ]

    request(
        "PUT",
        f"/collections/{COLLECTION}",
        {"vectors": {"evidence": {"size": 768, "distance": "Cosine"}}},
    )
    for field in ("tenant_id", "object_type", "pair_id"):
        request(
            "PUT",
            f"/collections/{COLLECTION}/index?wait=true",
            {"field_name": field, "field_schema": "keyword"},
        )
    points = []
    for index, (item, vector) in enumerate(
        zip(images, image_vectors, strict=True)
    ):
        points.append(
            {
                "id": point_id(item["object_id"]),
                "vector": {"evidence": vector},
                "payload": {
                    **item,
                    "object_type": "image",
                    "tenant_id": TENANT,
                    "pair_id": incidents[index]["object_id"],
                },
            }
        )
    for index, (item, vector) in enumerate(
        zip(incidents, incident_vectors, strict=True)
    ):
        points.append(
            {
                "id": point_id(item["object_id"]),
                "vector": {"evidence": vector},
                "payload": {
                    **item,
                    "object_type": "incident",
                    "tenant_id": TENANT,
                    "pair_id": images[index]["object_id"],
                },
            }
        )
    request(
        "PUT",
        f"/collections/{COLLECTION}/points?wait=true",
        {"points": points},
    )

    text_query = (
        "task: retrieval | query: dashboard where checkout latency is "
        "above threshold"
    )
    text_latency, text_hits = search(embed(client, text_query), "image")
    screenshot_latency, screenshot_hits = search(
        image_vectors[0],
        "incident",
    )
    image_latency, image_hits = search(image_vectors[0], "image")

    directions = [
        {
            "direction": "text_to_image",
            "expected": "image:checkout-latency",
            "latency_ms": text_latency,
            "hits": text_hits,
        },
        {
            "direction": "screenshot_to_incident",
            "expected": "incident:checkout-latency",
            "latency_ms": screenshot_latency,
            "hits": screenshot_hits,
        },
        {
            "direction": "image_to_image",
            "expected": "image:checkout-latency",
            "latency_ms": image_latency,
            "hits": image_hits,
        },
    ]
    for result in directions:
        result["top1_correct"] = (
            result["hits"][0]["payload"]["object_id"]
            == result["expected"]
        )
        result["hits"] = [
            {
                "rank": rank,
                "score": round(hit["score"], 6),
                "object_id": hit["payload"]["object_id"],
                "object_type": hit["payload"]["object_type"],
                "tenant_id": hit["payload"]["tenant_id"],
            }
            for rank, hit in enumerate(result["hits"], start=1)
        ]
    artifact = {
        "provider": "google",
        "model": "gemini-embedding-2",
        "engine": "qdrant-1.19.1",
        "collection": COLLECTION,
        "corpus": {"images": len(images), "incidents": len(incidents)},
        "directions": directions,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
