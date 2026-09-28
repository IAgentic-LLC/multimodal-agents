import hashlib
import math
import re
from collections import Counter

TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def token_index(token: str) -> int:
    digest = hashlib.sha256(token.encode()).digest()
    return int.from_bytes(digest[:4], "big")


def inverse_document_frequency(
    documents: list[str],
) -> dict[str, float]:
    document_count = len(documents)
    frequencies = Counter(
        token
        for document in documents
        for token in set(tokenize(document))
    )
    return {
        token: math.log(1 + (document_count - count + 0.5) / (count + 0.5))
        for token, count in frequencies.items()
    }


def bm25_sparse(
    text: str,
    idf: dict[str, float],
    *,
    document_length: int | None = None,
    average_length: float | None = None,
    k1: float = 1.2,
    b: float = 0.75,
) -> dict[str, list[int] | list[float]]:
    tokens = tokenize(text)
    counts = Counter(tokens)
    values: list[tuple[int, float]] = []
    for token, frequency in counts.items():
        weight = idf.get(token, 0.0)
        if document_length is not None and average_length is not None:
            denominator = frequency + k1 * (
                1 - b + b * document_length / average_length
            )
            weight *= frequency * (k1 + 1) / denominator
        values.append((token_index(token), weight))
    values.sort()
    return {
        "indices": [index for index, _ in values],
        "values": [value for _, value in values],
    }


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    scores: Counter[str] = Counter()
    for ranking in rankings:
        for rank, object_id in enumerate(ranking, start=1):
            scores[object_id] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
