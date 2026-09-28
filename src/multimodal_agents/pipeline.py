"""Bind retained browser media to perception and inspectable events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .evidence import EvidenceEvent, EvidenceRef, Region, TimeRange, utc_now
from .perception import PerceptionAdapter


@dataclass(frozen=True)
class GroundTruth:
    expected_transcript: str
    expected_object: str
    expected_region: Region


@dataclass(frozen=True)
class CaptureRecord:
    session_id: str
    capture_id: str
    frame_asset: str
    audio_asset: str
    frame_captured_at: str
    frame_offset_ms: int
    voice_start_ms: int
    voice_end_ms: int
    ground_truth: GroundTruth | None = None

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> CaptureRecord:
        fields = {
            name: value[name]
            for name in cls.__dataclass_fields__
            if name != "ground_truth"
        }
        truth = value.get("ground_truth")
        if isinstance(truth, dict):
            region = truth["expected_region"]
            fields["ground_truth"] = GroundTruth(
                expected_transcript=str(truth["expected_transcript"]),
                expected_object=str(truth["expected_object"]),
                expected_region=Region(
                    float(region["left"]),
                    float(region["top"]),
                    float(region["right"]),
                    float(region["bottom"]),
                ),
            )
        return cls(**fields)  # type: ignore[arg-type]


def load_capture(manifest: Path, capture_id: str) -> CaptureRecord:
    for line in manifest.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if value.get("capture_id") == capture_id:
            return CaptureRecord.from_dict(value)
    raise LookupError(f"capture not found: {capture_id}")


def perceive_capture(
    root: Path,
    capture: CaptureRecord,
    adapter: PerceptionAdapter,
) -> tuple[EvidenceEvent, EvidenceEvent]:
    frame = root / capture.frame_asset
    audio = root / capture.audio_asset
    observation = adapter.observe(frame, audio)
    speech_id = f"evt-{uuid4()}"
    visual_id = f"evt-{uuid4()}"

    speech = EvidenceEvent(
        event_id=speech_id,
        session_id=capture.session_id,
        modality="speech",
        event_type="spoken_reference_captured",
        observation={"capture_id": capture.capture_id},
        evidence=EvidenceRef(
            asset=capture.audio_asset,
            captured_at=capture.frame_captured_at,
        ),
        confidence=1.0,
        created_at=utc_now(),
        session_offset_ms=capture.voice_start_ms,
        time_range=TimeRange(
            capture.voice_start_ms,
            capture.voice_end_ms,
        ),
    )
    visual = EvidenceEvent(
        event_id=visual_id,
        session_id=capture.session_id,
        modality="image",
        event_type="reference_grounded",
        observation={
            "spoken_text": observation.spoken_text,
            "object": observation.object_name,
            "description": observation.description,
            "provider": observation.provider,
            "model": observation.model,
            "latency_ms": observation.latency_ms,
            "input_tokens": observation.input_tokens,
            "output_tokens": observation.output_tokens,
            "capture_id": capture.capture_id,
        },
        evidence=EvidenceRef(
            asset=capture.frame_asset,
            captured_at=capture.frame_captured_at,
            region=observation.region,
        ),
        confidence=observation.confidence,
        created_at=utc_now(),
        session_offset_ms=capture.frame_offset_ms,
        related_event_ids=(speech_id,),
    )
    return speech, visual
