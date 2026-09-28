"""Small inspectable memory used by the first vertical slice."""

from __future__ import annotations

import json
from pathlib import Path

from .evidence import EvidenceEvent


class EvidenceMemory:
    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, event: EvidenceEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event.as_dict(), sort_keys=True) + "\n")

    def events(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return [
            json.loads(line)
            for line in self.path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def search_object(self, object_name: str) -> list[dict[str, object]]:
        matches = []
        for event in self.events():
            observed = event.get("observation", {}).get("object")
            if observed == object_name:
                matches.append(event)
        return matches

    def latest_object(self, object_name: str) -> dict[str, object] | None:
        matches = self.search_object(object_name)
        if not matches:
            return None
        return max(
            matches,
            key=lambda item: int(item.get("session_offset_ms", 0)),
        )
