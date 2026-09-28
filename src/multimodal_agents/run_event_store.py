import json
import sqlite3
import sys
from pathlib import Path

from multimodal_agents.event_store import EventStore, MemoryEvent


def main() -> None:
    output = Path(sys.argv[1])
    store = EventStore(sqlite3.connect(":memory:"))
    events = [
        MemoryEvent(
            event_id="evt-keys-voice",
            event_type="speech.observed",
            entity_id="keys",
            valid_at="2026-09-28T19:41:58+03:00",
            recorded_at="2026-09-28T19:41:59+03:00",
            modality="voice",
            locator="session-17#audio&t=1.2,2.8",
            payload={"utterance": "I will put these here."},
        ),
        MemoryEvent(
            event_id="evt-keys-video",
            event_type="object.observed",
            entity_id="keys",
            valid_at="2026-09-28T19:42:00+03:00",
            recorded_at="2026-09-28T19:42:03+03:00",
            modality="video",
            locator="kitchen.mp4#t=4,6&xywh=410,220,90,55",
            payload={"location": "kitchen counter", "confidence": 0.88},
            derived_from=("evt-keys-voice",),
        ),
        MemoryEvent(
            event_id="evt-keys-correction",
            event_type="observation.corrected",
            entity_id="keys",
            valid_at="2026-09-28T19:42:00+03:00",
            recorded_at="2026-09-28T19:44:00+03:00",
            modality="human",
            locator="review://session-17/correction-1",
            payload={"location": "kitchen drawer", "confidence": 1.0},
            derived_from=("evt-keys-video",),
            corrects="evt-keys-video",
        ),
    ]
    sequences = [store.append(event) for event in events]
    artifact = {
        "store": "sqlite-in-memory",
        "append_sequences": sequences,
        "history": store.history("keys"),
        "projection_before_correction": store.projection(
            "keys", "2026-09-28T19:43:00+03:00"
        ),
        "projection_after_correction": store.projection(
            "keys", "2026-09-28T19:45:00+03:00"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
