import sqlite3

import pytest

from multimodal_agents.event_store import EventStore, MemoryEvent


def event(event_id: str, recorded_at: str, **changes) -> MemoryEvent:
    values = {
        "event_id": event_id,
        "event_type": "object.observed",
        "entity_id": "keys",
        "valid_at": "2026-09-28T19:42:00+03:00",
        "recorded_at": recorded_at,
        "modality": "video",
        "locator": "kitchen.mp4#t=4,6",
        "payload": {"location": "kitchen counter"},
    }
    values.update(changes)
    return MemoryEvent(**values)


def test_event_store_is_append_only_and_rejects_duplicate_id():
    store = EventStore(sqlite3.connect(":memory:"))
    store.append(event("evt-1", "2026-09-28T19:42:03+03:00"))
    with pytest.raises(sqlite3.IntegrityError):
        store.append(event("evt-1", "2026-09-28T19:42:04+03:00"))
    assert len(store.history("keys")) == 1


def test_correction_preserves_original_and_changes_projection():
    store = EventStore(sqlite3.connect(":memory:"))
    store.append(event("evt-1", "2026-09-28T19:42:03+03:00"))
    store.append(event(
        "evt-2",
        "2026-09-28T19:44:00+03:00",
        event_type="observation.corrected",
        payload={"location": "kitchen drawer"},
        corrects="evt-1",
    ))
    assert len(store.history("keys")) == 2
    assert store.projection(
        "keys", "2026-09-28T19:43:00+03:00"
    )["payload"]["location"] == "kitchen counter"
    assert store.projection(
        "keys", "2026-09-28T19:45:00+03:00"
    )["payload"]["location"] == "kitchen drawer"
