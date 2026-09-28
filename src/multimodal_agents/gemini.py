"""Gemini implementation of the retained-media perception boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from google import genai
from google.genai import types

from .evidence import Region
from .image_grounding import GroundingResult
from .perception import VisualObservation
from .scene_reading import SceneElement, SceneExtraction, SceneRelation


MODEL = "gemini-3.8-flash"
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resolved": {"type": "boolean"},
        "spoken_text": {"type": "string"},
        "object_name": {"type": "string"},
        "description": {"type": "string"},
        "left": {"type": "number", "minimum": 0, "maximum": 1},
        "top": {"type": "number", "minimum": 0, "maximum": 1},
        "right": {"type": "number", "minimum": 0, "maximum": 1},
        "bottom": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "resolved",
        "spoken_text",
        "object_name",
        "description",
        "left",
        "top",
        "right",
        "bottom",
        "confidence",
    ],
}

AUDIO_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "has_intelligible_speech": {"type": "boolean"},
        "transcript": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["has_intelligible_speech", "transcript", "confidence"],
}

GROUNDING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resolved": {"type": "boolean"},
        "object_name": {"type": "string"},
        "description": {"type": "string"},
        "left": {"type": "number", "minimum": 0, "maximum": 1},
        "top": {"type": "number", "minimum": 0, "maximum": 1},
        "right": {"type": "number", "minimum": 0, "maximum": 1},
        "bottom": {"type": "number", "minimum": 0, "maximum": 1},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "resolved",
        "object_name",
        "description",
        "left",
        "top",
        "right",
        "bottom",
        "confidence",
    ],
}

SCENE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "elements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": ["title", "text", "table", "chart"],
                    },
                    "text": {"type": "string"},
                    "left": {"type": "number"},
                    "top": {"type": "number"},
                    "right": {"type": "number"},
                    "bottom": {"type": "number"},
                },
                "required": [
                    "element_id",
                    "kind",
                    "text",
                    "left",
                    "top",
                    "right",
                    "bottom",
                ],
            },
        },
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "relation": {"type": "string"},
                    "target_id": {"type": "string"},
                },
                "required": ["source_id", "relation", "target_id"],
            },
        },
    },
    "required": ["elements", "relations"],
}

TEMPORAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["supported", "insufficient_history", "ambiguous"],
        },
        "direction": {"type": "string"},
        "evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "explanation": {"type": "string"},
    },
    "required": ["status", "direction", "evidence_ids", "explanation"],
}

IMAGE_PROMPT = """Find the exact object named in QUERY in the supplied image.
Set resolved to false if that object is absent or ambiguous. When resolved,
return the smallest defensible bounding box in normalized left, top, right,
bottom coordinates. Do not include shadows or unrelated objects. QUERY: """

PROMPT = """Transcribe the short spoken reference, then resolve it against
the accompanying image. The speaker may use a deictic phrase such as 'this'.
Return the smallest defensible bounding box around the referenced object using
normalized coordinates. Set resolved to false rather than guessing when the
audio or image does not support one object. Do not infer hidden details."""


def usage_counts(usage: object) -> dict[str, int | None]:
    candidate = getattr(usage, "candidates_token_count", None)
    thought = getattr(usage, "thoughts_token_count", None)
    billed_output = sum(value or 0 for value in (candidate, thought))
    return {
        "input": getattr(usage, "prompt_token_count", None),
        "candidate": candidate,
        "thought": thought,
        "billed_output": billed_output,
        "total": getattr(usage, "total_token_count", None),
    }


class ReferenceNotGrounded(RuntimeError):
    pass


class GeminiImageGrounder:
    def __init__(
        self,
        model: str = MODEL,
        client: genai.Client | None = None,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = client or genai.Client(api_key=api_key)
        self.model = model
        self.last_trace: dict[str, Any] | None = None

    def ground(self, image: Path, query: str) -> GroundingResult:
        started = perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                f"{IMAGE_PROMPT}{json.dumps(query)}",
                types.Part.from_bytes(
                    data=image.read_bytes(),
                    mime_type="image/png",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=GROUNDING_SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        latency_ms = round((perf_counter() - started) * 1000)
        value = json.loads(response.text)
        usage = response.usage_metadata
        counts = usage_counts(usage)
        region = None
        if value["resolved"]:
            region = Region(
                value["left"],
                value["top"],
                value["right"],
                value["bottom"],
            )
        self.last_trace = {
            "provider": "google",
            "model": self.model,
            "latency_ms": latency_ms,
            "response_id": getattr(response, "response_id", None),
            "input_tokens": counts["input"],
            "candidate_tokens": counts["candidate"],
            "thought_tokens": counts["thought"],
            "billed_output_tokens": counts["billed_output"],
            "total_tokens": counts["total"],
            "response": value,
        }
        return GroundingResult(
            resolved=value["resolved"],
            object_name=value["object_name"],
            description=value["description"],
            region=region,
            confidence=value["confidence"],
            latency_ms=latency_ms,
            input_tokens=counts["input"],
            output_tokens=counts["billed_output"],
        )


class GeminiSceneReader:
    def __init__(
        self,
        model: str = MODEL,
        client: genai.Client | None = None,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = client or genai.Client(api_key=api_key)
        self.model = model
        self.last_trace: dict[str, Any] | None = None

    def read(self, image: Path) -> SceneExtraction:
        prompt = (
            "Read this dashboard without flattening its layout. Return three "
            "elements with these exact IDs: page-title, latency-table, and "
            "latency-chart. Classify their types, transcribe their meaningful "
            "content, and return the tight normalized region of each. Add "
            "visualizes_same_measurements_as from latency-chart to "
            "latency-table only if the visible values support it."
        )
        started = perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=image.read_bytes(),
                    mime_type="image/png",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=SCENE_SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        latency_ms = round((perf_counter() - started) * 1000)
        value = json.loads(response.text)
        counts = usage_counts(response.usage_metadata)
        elements = tuple(
            SceneElement(
                element["element_id"],
                element["kind"],
                element["text"],
                Region(
                    element["left"],
                    element["top"],
                    element["right"],
                    element["bottom"],
                ),
            )
            for element in value["elements"]
        )
        relations = tuple(
            SceneRelation(
                relation["source_id"],
                relation["relation"],
                relation["target_id"],
            )
            for relation in value["relations"]
        )
        self.last_trace = {
            "provider": "google",
            "model": self.model,
            "latency_ms": latency_ms,
            "response_id": getattr(response, "response_id", None),
            "input_tokens": counts["input"],
            "candidate_tokens": counts["candidate"],
            "thought_tokens": counts["thought"],
            "billed_output_tokens": counts["billed_output"],
            "total_tokens": counts["total"],
            "response": value,
        }
        return SceneExtraction(
            elements=elements,
            relations=relations,
            latency_ms=latency_ms,
            input_tokens=counts["input"],
            output_tokens=counts["billed_output"],
        )


class GeminiTemporalReader:
    def __init__(
        self,
        model: str = MODEL,
        client: genai.Client | None = None,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = client or genai.Client(api_key=api_key)
        self.model = model

    def read(self, frames: tuple[tuple[str, Path], ...]) -> dict[str, Any]:
        contents: list[object] = [
            "Determine whether the same red block moved horizontally. The "
            "images are chronological and each preceding label is its exact "
            "evidence ID. A single image cannot prove motion. If motion is "
            "supported, return its direction and cite both endpoint IDs."
        ]
        for frame_id, path in frames:
            contents.extend(
                [
                    f"Evidence ID: {frame_id}",
                    types.Part.from_bytes(
                        data=path.read_bytes(),
                        mime_type="image/png",
                    ),
                ]
            )
        started = perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=TEMPORAL_SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        latency_ms = round((perf_counter() - started) * 1000)
        counts = usage_counts(response.usage_metadata)
        return {
            "provider": "google",
            "model": self.model,
            "latency_ms": latency_ms,
            "input_tokens": counts["input"],
            "candidate_tokens": counts["candidate"],
            "thought_tokens": counts["thought"],
            "billed_output_tokens": counts["billed_output"],
            "total_tokens": counts["total"],
            "response": json.loads(response.text),
        }


class GeminiPerception:
    def __init__(
        self,
        model: str = MODEL,
        client: genai.Client | None = None,
    ) -> None:
        api_key = os.environ.get("GEMINI_API_KEY")
        self.client = client or genai.Client(api_key=api_key)
        self.model = model
        self.last_trace: dict[str, Any] | None = None

    def observe(self, frame: Path, spoken_reference: Path) -> VisualObservation:
        started = perf_counter()
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                PROMPT,
                types.Part.from_bytes(
                    data=spoken_reference.read_bytes(),
                    mime_type="audio/webm",
                ),
                types.Part.from_bytes(
                    data=frame.read_bytes(),
                    mime_type="image/jpeg",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        latency_ms = round((perf_counter() - started) * 1000)
        value = json.loads(response.text)
        usage = response.usage_metadata
        counts = usage_counts(usage)
        self.last_trace = {
            "provider": "google",
            "model": self.model,
            "latency_ms": latency_ms,
            "response_id": getattr(response, "response_id", None),
            "input_tokens": counts["input"],
            "candidate_tokens": counts["candidate"],
            "thought_tokens": counts["thought"],
            "billed_output_tokens": counts["billed_output"],
            "total_tokens": counts["total"],
            "response": value,
        }
        if not value["resolved"]:
            raise ReferenceNotGrounded(value.get("description", "unresolved"))
        return VisualObservation(
            spoken_text=value["spoken_text"],
            object_name=value["object_name"],
            description=value["description"],
            region=Region(
                value["left"],
                value["top"],
                value["right"],
                value["bottom"],
            ),
            confidence=value["confidence"],
            provider="google",
            model=self.model,
            latency_ms=latency_ms,
            input_tokens=counts["input"],
            output_tokens=counts["billed_output"],
        )


class SplitGeminiPerception(GeminiPerception):
    """Keep audio transcription isolated from visual grounding."""

    def observe(self, frame: Path, spoken_reference: Path) -> VisualObservation:
        audio_started = perf_counter()
        audio_response = self.client.models.generate_content(
            model=self.model,
            contents=[
                "Transcribe only intelligible speech in this audio. If there "
                "is none, set has_intelligible_speech to false and return an "
                "empty transcript. Do not guess.",
                types.Part.from_bytes(
                    data=spoken_reference.read_bytes(),
                    mime_type="audio/webm",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=AUDIO_SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        audio_ms = round((perf_counter() - audio_started) * 1000)
        transcript = json.loads(audio_response.text)
        if not transcript["has_intelligible_speech"]:
            self.last_trace = {
                "provider": "google",
                "model": self.model,
                "audio_latency_ms": audio_ms,
                "transcription": transcript,
            }
            raise ReferenceNotGrounded("no intelligible spoken reference")

        grounding_started = perf_counter()
        visual_response = self.client.models.generate_content(
            model=self.model,
            contents=[
                "Ground this exact spoken transcript against the image: "
                f"{json.dumps(transcript['transcript'])}. Return the smallest "
                "defensible normalized box. Set resolved to false instead of "
                "matching unrelated visible text or guessing.",
                types.Part.from_bytes(
                    data=frame.read_bytes(),
                    mime_type="image/jpeg",
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=GROUNDING_SCHEMA,
                automatic_function_calling=(
                    types.AutomaticFunctionCallingConfig(disable=True)
                ),
            ),
        )
        grounding_ms = round((perf_counter() - grounding_started) * 1000)
        grounding = json.loads(visual_response.text)
        audio_usage = audio_response.usage_metadata
        visual_usage = visual_response.usage_metadata
        audio_counts = usage_counts(audio_usage)
        visual_counts = usage_counts(visual_usage)
        input_tokens = sum(
            value or 0
            for value in (
                audio_counts["input"],
                visual_counts["input"],
            )
        )
        output_tokens = sum(
            value or 0
            for value in (
                audio_counts["billed_output"],
                visual_counts["billed_output"],
            )
        )
        self.last_trace = {
            "provider": "google",
            "model": self.model,
            "audio_latency_ms": audio_ms,
            "grounding_latency_ms": grounding_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "audio_usage": audio_counts,
            "grounding_usage": visual_counts,
            "transcription": transcript,
            "grounding": grounding,
        }
        if not grounding["resolved"]:
            raise ReferenceNotGrounded(grounding["description"])
        return VisualObservation(
            spoken_text=transcript["transcript"],
            object_name=grounding["object_name"],
            description=grounding["description"],
            region=Region(
                grounding["left"],
                grounding["top"],
                grounding["right"],
                grounding["bottom"],
            ),
            confidence=min(transcript["confidence"], grounding["confidence"]),
            provider="google",
            model=self.model,
            latency_ms=audio_ms + grounding_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
