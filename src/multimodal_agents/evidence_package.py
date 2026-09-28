from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    modality: str
    locator: str
    content: str
    supports: tuple[str, ...]


def remove_modality(
    items: list[EvidenceItem],
    modality: str,
) -> list[EvidenceItem]:
    return [item for item in items if item.modality != modality]


def verify_citations(
    items: list[EvidenceItem],
    citations: list[dict[str, str]],
) -> list[str]:
    by_id = {item.evidence_id: item for item in items}
    errors = []
    for citation in citations:
        evidence_id = citation["evidence_id"]
        quote = citation["quote"]
        if evidence_id not in by_id:
            errors.append(f"unknown evidence: {evidence_id}")
        elif quote not in by_id[evidence_id].content:
            errors.append(f"quote not found: {evidence_id}")
    return errors


def answer_is_supported(
    answer: str,
    items: list[EvidenceItem],
    citations: list[dict[str, str]],
) -> bool:
    if verify_citations(items, citations):
        return False
    cited = {citation["evidence_id"] for citation in citations}
    normalized = answer.lower()
    return bool(cited) and all(
        any(term.lower() in normalized for term in item.supports)
        for item in items
        if item.evidence_id in cited
    )
