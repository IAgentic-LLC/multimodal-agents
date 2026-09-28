"""Run the deterministic first vertical slice and temporal follow-up."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .evaluate import score_case
from .evidence import EvidenceEvent, EvidenceRef, Region, utc_now
from .memory import EvidenceMemory
from .world_state import what_changed, where_is


def observed(
    event_id: str,
    offset_ms: int,
    location: str,
    asset: str,
) -> EvidenceEvent:
    return EvidenceEvent(
        event_id=event_id,
        session_id="slice-001",
        modality="image",
        event_type="object_observed",
        observation={"object": "red mug", "location": location},
        evidence=EvidenceRef(
            asset=asset,
            captured_at="fixture-session-time",
            region=Region(0.31, 0.12, 0.74, 0.91),
        ),
        confidence=0.94,
        created_at=utc_now(),
        session_offset_ms=offset_ms,
    )


def main() -> None:
    first = observed(
        "evt-001",
        100,
        "on the desk",
        "frames/frame-0042.jpg",
    )
    second = observed(
        "evt-002",
        500,
        "on the shelf",
        "frames/frame-0087.jpg",
    )
    with tempfile.TemporaryDirectory() as directory:
        memory = EvidenceMemory(Path(directory) / "events.jsonl")
        memory.append(first)
        memory.append(second)
        recalled = bool(memory.search_object("red mug"))
        result = score_case(
            second,
            expected_object="red mug",
            expected_asset="frames/frame-0087.jpg",
            expected_region=second.evidence.region,
            memory_recalled=recalled,
        )
        latest = where_is(memory.events(), "red mug")
        changed = what_changed(memory.events(), "red mug")
        print("object correct:", result.correct_object)
        print("frame correct: ", result.correct_frame)
        print("region IoU:   ", f"{result.region_iou:.2f}")
        print("memory found: ", result.memory_recalled)
        print("violations:   ", result.protected_violations)
        print("where:        ", latest.answer)
        print("where cites:  ", latest.citations[0].event_id)
        print("changed:      ", changed.answer)
        print(
            "change cites: ",
            ", ".join(item.event_id for item in changed.citations),
        )


if __name__ == "__main__":
    main()
