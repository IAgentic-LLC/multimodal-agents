from multimodal_agents.opensearch_corpus import (
    REPO_ROOT,
    iter_image_documents,
    iter_text_documents,
    normalize_gate_file,
)
from multimodal_agents.opensearch_index import HYBRID_SEARCH_PIPELINE, INDEX_MAPPING


def test_text_documents_trace_to_real_files_with_nonempty_text():
    documents = list(iter_text_documents())
    assert len(documents) > 0
    for doc in documents:
        assert doc.text != ""
        assert (REPO_ROOT / doc.source_file).exists()


def test_claim_field_is_preferred_verbatim_when_present(tmp_path):
    gate_file = tmp_path / "claim-shaped.json"
    gate_file.write_text(
        '{"claim": "98 regions found", "evidence_ids": ["a", "b", "a"]}',
        encoding="utf-8",
    )
    text, evidence_ids = normalize_gate_file(gate_file)
    assert text == "98 regions found"
    assert evidence_ids == ("a", "b")


def test_heterogeneous_shape_falls_back_to_flattened_text(tmp_path):
    gate_file = tmp_path / "no-claim.json"
    gate_file.write_text('{"scenario": "refusal", "status": "blocked"}', encoding="utf-8")
    text, evidence_ids = normalize_gate_file(gate_file)
    assert "scenario: refusal" in text
    assert "status: blocked" in text
    assert evidence_ids == ()


def test_image_documents_resolve_to_real_committed_figures():
    documents = list(iter_image_documents())
    assert len(documents) > 0
    for doc in documents:
        assert doc.image_path.exists()
        assert doc.image_path.suffix == ".png"


def test_index_mapping_enables_knn_and_the_hybrid_search_pipeline():
    assert INDEX_MAPPING["settings"]["index"]["knn"] is True
    assert "search.default_pipeline" in INDEX_MAPPING["settings"]["index"]
    embedding_field = INDEX_MAPPING["mappings"]["properties"]["embedding"]
    assert embedding_field["type"] == "knn_vector"
    assert embedding_field["method"]["space_type"] == "cosinesimil"


def test_hybrid_pipeline_combines_normalized_bm25_and_knn_scores():
    processor = HYBRID_SEARCH_PIPELINE["phase_results_processors"][0]
    normalization = processor["normalization-processor"]
    assert normalization["normalization"]["technique"] == "min_max"
    assert normalization["combination"]["technique"] == "arithmetic_mean"
