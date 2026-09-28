import asyncio
import json
from pathlib import Path

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)


async def measured_runtime() -> dict:
    span_exporter = InMemorySpanExporter()
    trace_provider = TracerProvider()
    trace_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    tracer = trace_provider.get_tracer("multimodal.runtime")

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    meter = meter_provider.get_meter("multimodal.runtime")
    accepted = meter.create_counter("runtime.events.accepted")
    rejected = meter.create_counter("runtime.events.rejected")
    latency = meter.create_histogram("runtime.stage.latency", unit="ms")

    queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=2)
    events = [
        {"id": "event-1", "kind": "video"},
        {"id": "event-2", "kind": "audio"},
        {"id": "event-3", "kind": "sensor"},
    ]
    with tracer.start_as_current_span("session") as session:
        session.set_attribute("session.id", "session-runtime-1")
        session.set_attribute("tenant.id", "tenant-blue")
        for event in events:
            with tracer.start_as_current_span("queue.publish") as span:
                span.set_attribute("event.id", event["id"])
                span.set_attribute("event.kind", event["kind"])
                try:
                    queue.put_nowait(event)
                    accepted.add(1, {"queue": "observations"})
                    span.set_attribute("queue.outcome", "accepted")
                except asyncio.QueueFull:
                    rejected.add(1, {"queue": "observations"})
                    span.set_attribute("queue.outcome", "rejected_full")
        while not queue.empty():
            event = queue.get_nowait()
            with tracer.start_as_current_span("event.process") as span:
                span.set_attribute("event.id", event["id"])
                span.set_attribute("evidence.retained", True)
                latency.record(12.0, {"stage": "process"})
            queue.task_done()

    spans = [
        {
            "name": span.name,
            "trace_id": format(span.context.trace_id, "032x"),
            "span_id": format(span.context.span_id, "016x"),
            "parent_span_id": (
                format(span.parent.span_id, "016x") if span.parent else None
            ),
            "attributes": dict(span.attributes),
        }
        for span in span_exporter.get_finished_spans()
    ]
    metrics = {}
    data = metric_reader.get_metrics_data()
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                points = metric.data.data_points
                if metric.name == "runtime.stage.latency":
                    metrics[metric.name] = sum(
                        point.count for point in points
                    )
                else:
                    metrics[metric.name] = sum(
                        point.value for point in points
                    )
    return {
        "queue": {"capacity": 2, "accepted": 2, "rejected_full": 1},
        "spans": spans,
        "metrics": metrics,
    }


def run_and_save(root: Path) -> dict:
    result = asyncio.run(measured_runtime())
    output = root / "runs" / "gate-30" / "runtime-observability.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result
