from multimodal_agents.run_qdrant_search import point_id, tenant_filter


def test_point_id_is_stable_and_distinguishes_objects():
    first = point_id("report:p1:table:1")
    assert first == point_id("report:p1:table:1")
    assert first != point_id("report:p1:figure:1")


def test_tenant_filter_requires_exact_tenant():
    result = tenant_filter("tenant-blue")
    assert result == {
        "must": [
            {
                "key": "tenant_id",
                "match": {"value": "tenant-blue"},
            }
        ]
    }
