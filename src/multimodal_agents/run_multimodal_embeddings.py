import json
import math
import os
import sys
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types


def cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm)


def embed(client: genai.Client, content: object) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=content,
        config=types.EmbedContentConfig(output_dimensionality=768),
    )
    return list(result.embeddings[0].values or [])


def main() -> None:
    output = Path(sys.argv[1])
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    items = [
        {
            "object_id": "report:p1:paragraph:1",
            "modality": "text",
            "section": "release-readiness",
            "content": "The release decision depends on service metrics.",
        },
        {
            "object_id": "report:p1:table:1",
            "modality": "table",
            "section": "release-readiness",
            "content": (
                "Service error rates: Vision API 0.8 percent pass; "
                "Search API 3.4 percent investigate."
            ),
        },
        {
            "object_id": "report:p1:figure:1",
            "modality": "image",
            "section": "release-readiness",
            "path": "fixtures/document-error-rates.png",
        },
    ]
    started = perf_counter()
    vectors: list[list[float]] = []
    for item in items:
        if item["modality"] == "image":
            content = types.Part.from_bytes(
                data=Path(str(item["path"])).read_bytes(),
                mime_type="image/png",
            )
        else:
            content = "task: document | " + str(item["content"])
        vectors.append(embed(client, content))
    query = "task: retrieval | query: Which service exceeds the threshold?"
    query_vector = embed(client, query)
    ranked = sorted(
        [
            {
                "rank": 0,
                "object_id": item["object_id"],
                "modality": item["modality"],
                "section": item["section"],
                "score": round(cosine(query_vector, vector), 6),
            }
            for item, vector in zip(items, vectors, strict=True)
        ],
        key=lambda item: item["score"],
        reverse=True,
    )
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    payload = {
        "provider": "google",
        "model": "gemini-embedding-2",
        "dimensions": len(query_vector),
        "query": query,
        "index": {
            "index_id": "release-report-v1",
            "source_asset": "fixtures/document-layout.docx",
            "parser": "apache-tika-4.0.0",
            "embedding_model": "gemini-embedding-2",
        },
        "results": ranked,
        "latency_ms": round((perf_counter() - started) * 1000),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
