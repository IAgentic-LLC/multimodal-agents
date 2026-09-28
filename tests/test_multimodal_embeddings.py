import pytest

from multimodal_agents.run_multimodal_embeddings import cosine


def test_cosine_ranks_same_direction_above_orthogonal():
    query = [1.0, 0.0]
    assert cosine(query, [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine(query, [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_supports_normalized_negative_similarity():
    assert cosine([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
