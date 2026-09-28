import pytest

from multimodal_agents.hybrid_search import (
    bm25_sparse,
    inverse_document_frequency,
    reciprocal_rank_fusion,
    tokenize,
)


def test_tokenize_preserves_exact_hyphenated_identifier():
    assert tokenize("Investigate INC-4827 now") == [
        "investigate",
        "inc-4827",
        "now",
    ]


def test_bm25_sparse_gives_rare_identifier_a_positive_weight():
    documents = ["incident INC-4827", "ordinary release note"]
    idf = inverse_document_frequency(documents)
    vector = bm25_sparse("INC-4827", idf)
    assert len(vector["indices"]) == 1
    assert vector["values"][0] == pytest.approx(idf["inc-4827"])


def test_rrf_rewards_candidate_found_by_both_legs():
    fused = reciprocal_rank_fusion(
        [["semantic", "shared"], ["exact", "shared"]],
    )
    assert fused[0][0] == "shared"
