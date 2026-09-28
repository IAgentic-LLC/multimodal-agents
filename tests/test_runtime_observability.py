import asyncio

from multimodal_agents.runtime_observability import measured_runtime


def result():
    return asyncio.run(measured_runtime())


def test_bounded_queue_rejects_excess_work():
    assert result()["queue"] == {
        "capacity": 2,
        "accepted": 2,
        "rejected_full": 1,
    }


def test_spans_share_trace_and_keep_parent_relationships():
    spans = result()["spans"]
    assert len(spans) == 6
    assert len({span["trace_id"] for span in spans}) == 1
    session = next(span for span in spans if span["name"] == "session")
    children = [span for span in spans if span["name"] != "session"]
    assert all(
        span["parent_span_id"] == session["span_id"]
        for span in children
    )


def test_metrics_record_accept_reject_and_processing_count():
    metrics = result()["metrics"]
    assert metrics == {
        "runtime.events.accepted": 2,
        "runtime.events.rejected": 1,
        "runtime.stage.latency": 2,
    }


def test_trace_attributes_use_ids_not_raw_media():
    spans = result()["spans"]
    serialized = str(spans)
    assert "event-1" in serialized
    assert "raw_audio" not in serialized
    assert "image_bytes" not in serialized
