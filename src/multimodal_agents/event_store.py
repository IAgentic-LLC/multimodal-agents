import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    event_type: str
    entity_id: str
    valid_at: str
    recorded_at: str
    modality: str
    locator: str
    payload: dict
    derived_from: tuple[str, ...] = ()
    corrects: str | None = None

    @property
    def digest(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()


class EventStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              sequence INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT UNIQUE NOT NULL,
              event_type TEXT NOT NULL,
              entity_id TEXT NOT NULL,
              valid_at TEXT NOT NULL,
              recorded_at TEXT NOT NULL,
              modality TEXT NOT NULL,
              locator TEXT NOT NULL,
              payload TEXT NOT NULL,
              derived_from TEXT NOT NULL,
              corrects TEXT,
              digest TEXT NOT NULL
            )
            """
        )

    def append(self, event: MemoryEvent) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO events (
              event_id, event_type, entity_id, valid_at, recorded_at,
              modality, locator, payload, derived_from, corrects, digest
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.event_type,
                event.entity_id,
                event.valid_at,
                event.recorded_at,
                event.modality,
                event.locator,
                json.dumps(event.payload, sort_keys=True),
                json.dumps(event.derived_from),
                event.corrects,
                event.digest,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def history(self, entity_id: str) -> list[dict]:
        rows = self.connection.execute(
            """
            SELECT sequence, event_id, event_type, valid_at, recorded_at,
                   modality, locator, payload, derived_from, corrects, digest
            FROM events WHERE entity_id = ? ORDER BY sequence
            """,
            (entity_id,),
        ).fetchall()
        keys = (
            "sequence", "event_id", "event_type", "valid_at", "recorded_at",
            "modality", "locator", "payload", "derived_from", "corrects",
            "digest",
        )
        result = []
        for row in rows:
            item = dict(zip(keys, row, strict=True))
            item["payload"] = json.loads(item["payload"])
            item["derived_from"] = json.loads(item["derived_from"])
            result.append(item)
        return result

    def projection(self, entity_id: str, recorded_by: str) -> dict | None:
        history = [
            event
            for event in self.history(entity_id)
            if event["recorded_at"] <= recorded_by
        ]
        if not history:
            return None
        corrected = {
            event["corrects"] for event in history if event["corrects"]
        }
        candidates = [
            event for event in history if event["event_id"] not in corrected
        ]
        return max(
            candidates,
            key=lambda event: (event["valid_at"], event["sequence"]),
        )
