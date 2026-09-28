import json
import sqlite3
import sys
from pathlib import Path

from multimodal_agents.event_store import EventStore, MemoryEvent
from multimodal_agents.memory_queries import changes, event_order, where_was


def main() -> None:
    output = Path(sys.argv[1])
    store = EventStore(sqlite3.connect(":memory:"))
    for event in (
        MemoryEvent(
            "voice", "speech.observed", "keys",
            "2026-09-28T19:41:58+03:00", "2026-09-28T19:41:59+03:00",
            "voice", "session#audio&t=1.2,2.8", {"utterance": "here"},
        ),
        MemoryEvent(
            "video", "object.observed", "keys",
            "2026-09-28T19:42:00+03:00", "2026-09-28T19:42:03+03:00",
            "video", "kitchen.mp4#t=4,6", {"location": "kitchen counter"},
            derived_from=("voice",),
        ),
        MemoryEvent(
            "correction", "observation.corrected", "keys",
            "2026-09-28T19:42:00+03:00", "2026-09-28T19:44:00+03:00",
            "human", "review:1", {"location": "kitchen drawer"},
            derived_from=("video",), corrects="video",
        ),
    ):
        store.append(event)
    artifact = {
        "where_known_at_19_43": where_was(
            store, "keys", "2026-09-28T19:43:00+03:00"
        ),
        "where_known_at_19_45": where_was(
            store, "keys", "2026-09-28T19:45:00+03:00"
        ),
        "changes": changes(store, "keys"),
        "event_order": event_order(store, "keys"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
