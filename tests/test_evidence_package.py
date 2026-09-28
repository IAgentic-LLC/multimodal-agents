from multimodal_agents.evidence_package import (
    EvidenceItem,
    answer_is_supported,
    remove_modality,
    verify_citations,
)


def fixture() -> list[EvidenceItem]:
    return [
        EvidenceItem("p1", "text", "page:1", "Search API is 3.4%.", ("Search API",)),
        EvidenceItem("t1", "table", "table:1", "Search API | 3.4%", ("Search API",)),
    ]


def test_remove_modality_keeps_other_evidence():
    assert [item.evidence_id for item in remove_modality(fixture(), "text")] == ["t1"]


def test_verify_citations_rejects_unknown_id_and_invented_quote():
    assert verify_citations(fixture(), [{"evidence_id": "bad", "quote": "x"}])
    assert verify_citations(fixture(), [{"evidence_id": "p1", "quote": "4.3%"}])


def test_supported_answer_requires_valid_cited_evidence():
    citations = [{"evidence_id": "t1", "quote": "Search API | 3.4%"}]
    assert answer_is_supported("Search API needs investigation.", fixture(), citations)
    assert not answer_is_supported("Vision API needs investigation.", fixture(), citations)
