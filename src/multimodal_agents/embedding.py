"""Shared async text-embedding helper, gemini-embedding-2, reused by the
capstone specialists and the tenant studio API rather than duplicated.
"""

from __future__ import annotations

import asyncio
import os

from google import genai
from google.genai import types

EMBEDDING_DIMENSIONS = 768


async def embed_text(text: str) -> list[float]:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call() -> list[float]:
        result = client.models.embed_content(
            model="gemini-embedding-2",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        )
        return list(result.embeddings[0].values or [])

    return await asyncio.to_thread(call)


async def embed_image_bytes(data: bytes, media_type: str = "image/png") -> list[float]:
    """Embed already-validated image bytes. Distinct from
    run_opensearch_index.py's embed_image, which Chapter 37 quotes
    verbatim and must not drift from the book's own printed source.
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    def call() -> list[float]:
        part = types.Part.from_bytes(data=data, mime_type=media_type)
        result = client.models.embed_content(
            model="gemini-embedding-2",
            contents=part,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        )
        return list(result.embeddings[0].values or [])

    return await asyncio.to_thread(call)
