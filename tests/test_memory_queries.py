import sqlite3

from multimodal_agents.event_store import EventStore, MemoryEvent
from multimodal_agents.memory_queries import changes, event_order, where_was


def populated() -> EventStore:
    store = EventStore(sqlite3.connect(":memory:"))
    store.append(MemoryEvent(
        "seen", "object.observed", "keys", "2026-09-28T19:42:00+03:00",
        "2026-09-28T19:42:03+03:00", "video", "video#t=4,6",
        {"location": "counter"},
    ))
    store.append(MemoryEvent(
        "fixed", "observation.corrected", "keys",
        "2026-09-28T19:42:00+03:00", "2026-09-28T19:44:00+03:00",
        "human", "review:1", {"location": "drawer"},
        corrects="seen",
    ))
    return store


def test_where_was_respects_record_time():
    store = populated()
    assert where_was(store, "keys", "2026-09-28T19:43:00+03:00")["answer"] == "counter"
    assert where_was(store, "keys", "2026-09-28T19:45:00+03:00")["answer"] == "drawer"


def test_changes_explains_before_after_and_evidence():
    assert changes(populated(), "keys") == [{
        "changed_at": "2026-09-28T19:44:00+03:00",
        "from": "counter",
        "to": "drawer",
        "evidence": ["seen", "fixed"],
    }]


def test_event_order_is_stable_for_equal_valid_time():
    assert event_order(populated(), "keys") == ["seen", "fixed"]
