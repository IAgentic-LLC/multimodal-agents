"""Follow-along script: embed the book's own real multimodal evidence
(claim text and committed figures) with gemini-embedding-2 and load it into
the capstone's real OpenSearch hybrid index. Requires GEMINI_API_KEY and a
local OpenSearch at OPENSEARCH_URL (default http://127.0.0.1:9200).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from multimodal_agents.opensearch_corpus import iter_image_documents, iter_text_documents
from multimodal_agents.opensearch_index import ensure_index, index_document, refresh

EMBEDDING_DIMENSIONS = 768


def embed_text(client: genai.Client, text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    return list(result.embeddings[0].values or [])


def embed_image(client: genai.Client, path: Path) -> list[float]:
    part = types.Part.from_bytes(data=path.read_bytes(), mime_type="image/png")
    result = client.models.embed_content(
        model="gemini-embedding-2",
        contents=part,
        config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
    )
    return list(result.embeddings[0].values or [])


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY is required", file=sys.stderr)
        raise SystemExit(1)
    client = genai.Client(api_key=api_key)

    reset = "--reset" in sys.argv
    ensure_index(reset=reset)

    started = perf_counter()
    text_count = 0
    for doc in iter_text_documents():
        vector = embed_text(client, doc.text)
        index_document(
            doc.doc_id,
            {
                "doc_id": doc.doc_id,
                "chapter": doc.chapter,
                "chapter_title": doc.chapter_title,
                "modality": "text",
                "text": doc.text,
                "evidence_ids": list(doc.evidence_ids),
                "source_file": doc.source_file,
                "embedding": vector,
            },
        )
        text_count += 1

    image_count = 0
    for doc in iter_image_documents():
        vector = embed_image(client, doc.image_path)
        index_document(
            doc.doc_id,
            {
                "doc_id": doc.doc_id,
                "chapter": doc.chapter,
                "chapter_title": doc.chapter_title,
                "modality": "image",
                "text": f"Figure for chapter {doc.chapter}: {doc.chapter_title}",
                "evidence_ids": [],
                "source_file": doc.source_file,
                "embedding": vector,
            },
        )
        image_count += 1

    refresh()
    elapsed_ms = round((perf_counter() - started) * 1000)
    print(
        f"indexed {text_count} text documents and {image_count} image "
        f"documents in {elapsed_ms} ms"
    )


if __name__ == "__main__":
    main()
