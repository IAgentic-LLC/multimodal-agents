import json
import os
import sys
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from multimodal_agents.evidence_package import (
    EvidenceItem,
    answer_is_supported,
    remove_modality,
    verify_citations,
)

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "evidence_id": {"type": "string"},
                    "quote": {"type": "string"},
                },
                "required": ["evidence_id", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer", "citations"],
    "additionalProperties": False,
}


def package() -> list[EvidenceItem]:
    return [
        EvidenceItem(
            "report:p1:paragraph:1",
            "text",
            "document-layout.docx#paragraph=2",
            (
                "The investigation threshold is 2.0 percent. Search API "
                "measured 3.4 percent; Vision API measured 0.8 percent."
            ),
            ("Search API",),
        ),
        EvidenceItem(
            "report:p1:table:1:row:search-api",
            "table",
            "document-layout.docx#table=1&row=search-api",
            "Service | Error rate | Decision\nSearch API | 3.4% | Investigate",
            ("Search API",),
        ),
        EvidenceItem(
            "report:p1:figure:1:region:search-api",
            "image",
            "document-error-rates.png#xywh=pixel:400,122,91,179",
            "Search API 3.4%",
            ("Search API",),
        ),
    ]


def ask(
    client: genai.Client,
    items: list[EvidenceItem],
) -> tuple[int, dict]:
    manifest = []
    contents: list[object] = []
    for item in items:
        record = {
            "evidence_id": item.evidence_id,
            "modality": item.modality,
            "locator": item.locator,
            "content": (
                "[attached image; quote only text visible in the region]"
                if item.modality == "image"
                else item.content
            ),
        }
        manifest.append(record)
    prompt = (
        "Answer only from this evidence package. Question: Which service "
        "requires investigation? Cite one or more evidence IDs. Every quote "
        "must be copied exactly from that evidence.\nEvidence:\n"
        + json.dumps(manifest)
    )
    contents.append(prompt)
    if any(item.modality == "image" for item in items):
        contents.append(
            types.Part.from_bytes(
                data=Path("fixtures/document-error-rates.png").read_bytes(),
                mime_type="image/png",
            )
        )
    started = perf_counter()
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(disable=True)
            ),
        ),
    )
    return round((perf_counter() - started) * 1000), json.loads(response.text)


def main() -> None:
    output = Path(sys.argv[1])
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    complete = package()
    variants = [("complete", complete)] + [
        (f"without_{modality}", remove_modality(complete, modality))
        for modality in ("text", "table", "image")
    ]
    results = []
    for name, items in variants:
        latency, response = ask(client, items)
        errors = verify_citations(items, response["citations"])
        supported = answer_is_supported(
            response["answer"],
            items,
            response["citations"],
        )
        results.append(
            {
                "variant": name,
                "modalities": [item.modality for item in items],
                "answer": response["answer"],
                "citations": response["citations"],
                "citation_errors": errors,
                "supported": supported,
                "latency_ms": latency,
            }
        )
    assert all(result["supported"] for result in results)
    artifact = {
        "model": "gemini-3.8-flash",
        "question": "Which service requires investigation?",
        "evidence_items": [item.__dict__ for item in complete],
        "results": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
