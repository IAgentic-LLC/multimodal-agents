from multimodal_agents.run_cross_modal_search import exact_filter


def test_exact_filter_requires_every_payload_value():
    result = exact_filter(tenant_id="tenant-blue", object_type="image")
    assert result["must"] == [
        {
            "key": "tenant_id",
            "match": {"value": "tenant-blue"},
        },
        {
            "key": "object_type",
            "match": {"value": "image"},
        },
    ]
