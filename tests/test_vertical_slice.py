from __future__ import annotations

import tempfile
import unittest
import base64
from pathlib import Path

from multimodal_agents.capture import persist_capture
from multimodal_agents.evaluate import (
    TokenRates,
    intersection_over_union,
    score_case,
    score_grounded_capture,
)
from multimodal_agents.evidence import EvidenceEvent, EvidenceRef, Region
from multimodal_agents.memory import EvidenceMemory
from multimodal_agents.perception import ScriptedPerception, VisualObservation
from multimodal_agents.pipeline import (
    CaptureRecord,
    load_capture,
    perceive_capture,
)
from multimodal_agents.world_state import what_changed, where_is


class VerticalSliceTests(unittest.TestCase):
    def event(self) -> EvidenceEvent:
        return EvidenceEvent(
            event_id="evt-001",
            session_id="session-001",
            modality="image",
            event_type="object_observed",
            observation={"object": "red mug"},
            evidence=EvidenceRef(
                asset="frames/frame-0042.jpg",
                captured_at="2026-09-28T00:00:01Z",
                region=Region(0.3, 0.2, 0.7, 0.8),
            ),
            confidence=0.9,
            created_at="2026-09-28T00:00:02Z",
        )

    def test_identical_regions_have_full_overlap(self) -> None:
        region = Region(0.1, 0.2, 0.8, 0.9)
        self.assertEqual(intersection_over_union(region, region), 1.0)

    def test_memory_retains_inspectable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = EvidenceMemory(Path(directory) / "events.jsonl")
            memory.append(self.event())
            matches = memory.search_object("red mug")
            self.assertEqual(len(matches), 1)
            self.assertEqual(
                matches[0]["evidence"]["asset"],
                "frames/frame-0042.jpg",
            )

    def test_wrong_frame_is_a_protected_violation(self) -> None:
        result = score_case(
            self.event(),
            expected_object="red mug",
            expected_asset="frames/frame-0043.jpg",
            expected_region=Region(0.3, 0.2, 0.7, 0.8),
            memory_recalled=True,
        )
        self.assertEqual(result.protected_violations, 1)

    def test_capture_persists_bound_frame_audio_and_manifest(self) -> None:
        jpeg = base64.b64encode(b"\xff\xd8test-jpeg").decode("ascii")
        metadata = {
            "session_id": "session-001",
            "capture_id": "capture-001",
            "frame_captured_at": "2026-09-28T00:00:01Z",
            "frame_offset_ms": 20,
            "voice_start_ms": 24,
            "voice_end_ms": 900,
            "ground_truth": {
                "expected_transcript": "remember where I put this",
                "expected_object": "red mug",
                "expected_region": {
                    "left": 0.1,
                    "top": 0.2,
                    "right": 0.8,
                    "bottom": 0.9,
                },
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = persist_capture(
                root,
                metadata,
                f"data:image/jpeg;base64,{jpeg}",
                b"webm-audio",
            )
            self.assertEqual(paths.frame.read_bytes(), b"\xff\xd8test-jpeg")
            self.assertEqual(paths.audio.read_bytes(), b"webm-audio")
            manifest = paths.manifest.read_text(encoding="utf-8")
            self.assertIn("session-001/frames/capture-001.jpg", manifest)
            self.assertIn('"expected_object": "red mug"', manifest)
            record = load_capture(paths.manifest, "capture-001")
            self.assertEqual(record.ground_truth.expected_object, "red mug")
            self.assertEqual(record.ground_truth.expected_region.left, 0.1)

    def test_scripted_perception_binds_voice_frame_and_region(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frame = root / "session-001/frames/capture-001.jpg"
            audio = root / "session-001/audio/capture-001.webm"
            frame.parent.mkdir(parents=True)
            audio.parent.mkdir(parents=True)
            frame.write_bytes(b"frame")
            audio.write_bytes(b"audio")
            capture = CaptureRecord(
                session_id="session-001",
                capture_id="capture-001",
                frame_asset="session-001/frames/capture-001.jpg",
                audio_asset="session-001/audio/capture-001.webm",
                frame_captured_at="2026-09-28T00:00:01Z",
                frame_offset_ms=100,
                voice_start_ms=120,
                voice_end_ms=900,
            )
            adapter = ScriptedPerception(
                VisualObservation(
                    spoken_text="remember where I put this",
                    object_name="red mug",
                    description="a red mug on the counter",
                    region=Region(0.2, 0.3, 0.6, 0.9),
                    confidence=0.95,
                    provider="scripted",
                    model="fixed-fixture",
                )
            )
            speech, visual = perceive_capture(root, capture, adapter)
            self.assertEqual(visual.observation["object"], "red mug")
            self.assertEqual(visual.evidence.asset, capture.frame_asset)
            self.assertEqual(visual.related_event_ids, (speech.event_id,))
            self.assertEqual(speech.time_range.start_ms, 120)

    def test_latest_object_uses_session_time(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = EvidenceMemory(Path(directory) / "events.jsonl")
            first = self.event()
            second = EvidenceEvent(
                **{
                    **first.__dict__,
                    "event_id": "evt-002",
                    "session_offset_ms": 500,
                }
            )
            memory.append(first)
            memory.append(second)
            latest = memory.latest_object("red mug")
            self.assertEqual(latest["event_id"], "evt-002")

    def test_grounded_score_recomputes_cost_and_iou(self) -> None:
        capture = CaptureRecord.from_dict({
            "session_id": "session-001",
            "capture_id": "capture-001",
            "frame_asset": "frames/frame-0042.jpg",
            "audio_asset": "audio/capture-001.webm",
            "frame_captured_at": "2026-09-28T00:00:01Z",
            "frame_offset_ms": 100,
            "voice_start_ms": 120,
            "voice_end_ms": 900,
            "ground_truth": {
                "expected_transcript": "Remember where I put this.",
                "expected_object": "red mug",
                "expected_region": {
                    "left": 0.3,
                    "top": 0.2,
                    "right": 0.7,
                    "bottom": 0.8,
                },
            },
        })
        event = EvidenceEvent(
            **{
                **self.event().__dict__,
                "observation": {
                    "spoken_text": "remember where I put this",
                    "object": "red mug",
                    "latency_ms": 1250,
                    "input_tokens": 1000,
                    "output_tokens": 100,
                },
            }
        )
        result = score_grounded_capture(
            capture,
            event,
            memory_recalled=True,
            rates=TokenRates(0.75, 3.75),
        )
        self.assertTrue(result.transcript_correct)
        self.assertTrue(result.localized_at_50)
        self.assertAlmostEqual(result.estimated_cost_usd, 0.001125)

    def test_temporal_answer_cites_latest_observation(self) -> None:
        first = self.event().as_dict()
        first["observation"]["location"] = "on the desk"
        second = self.event().as_dict()
        second["event_id"] = "evt-002"
        second["session_offset_ms"] = 500
        second["observation"]["location"] = "on the shelf"
        answer = where_is([second, first], "red mug")
        self.assertEqual(
            answer.answer,
            "red mug was last observed on the shelf.",
        )
        self.assertEqual(answer.citations[0].event_id, "evt-002")

    def test_change_answer_requires_two_observations(self) -> None:
        first = self.event().as_dict()
        first["observation"]["location"] = "on the desk"
        unresolved = what_changed([first], "red mug")
        self.assertEqual(unresolved.status, "insufficient_history")
        self.assertIsNone(unresolved.answer)

        second = self.event().as_dict()
        second["event_id"] = "evt-002"
        second["session_offset_ms"] = 500
        second["observation"]["location"] = "on the shelf"
        resolved = what_changed([first, second], "red mug")
        self.assertEqual(
            resolved.answer,
            "red mug moved from on the desk to on the shelf.",
        )
        self.assertEqual(len(resolved.citations), 2)

    def test_unknown_object_does_not_invent_location(self) -> None:
        answer = where_is([self.event().as_dict()], "blue notebook")
        self.assertEqual(answer.status, "insufficient_evidence")
        self.assertIsNone(answer.answer)


if __name__ == "__main__":
    unittest.main()
