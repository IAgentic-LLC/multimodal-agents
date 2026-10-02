"""Privacy-conscious Langfuse tracing for the production coordinator."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager, nullcontext
from functools import lru_cache
from typing import Any

from langfuse import Langfuse


def _redact(data: Any, **_: Any) -> Any:
    """Defence in depth if future code accidentally adds sensitive fields."""
    sensitive = {"authorization", "token", "secret", "password", "image"}
    if isinstance(data, dict):
        return {
            key: "[REDACTED]"
            if any(word in key.lower() for word in sensitive)
            else _redact(value)
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_redact(value) for value in data]
    return data


class Telemetry:
    """Small adapter that keeps Langfuse optional and easy to test."""

    def __init__(self) -> None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        self.enabled = bool(public_key and secret_key)
        self.client = (
            Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                base_url=os.getenv("LANGFUSE_BASE_URL", "http://localhost:3001"),
                environment=os.getenv("LANGFUSE_ENVIRONMENT", "development"),
                release=os.getenv("APP_RELEASE", "local"),
                mask=_redact,
            )
            if self.enabled
            else None
        )

    def orchestration(
        self, trace_id: str, question_length: int
    ) -> AbstractContextManager[Any]:
        if not self.client:
            return nullcontext()
        return self.client.start_as_current_observation(
            name="multimodal-orchestration",
            as_type="agent",
            trace_context={
                "trace_id": self.client.create_trace_id(seed=trace_id)
            },
            input={"question_length": question_length},
            metadata={
                "external_trace_id": trace_id,
                "authority": "observe_only",
                "transport": "a2a-jsonrpc-1.0",
            },
        )

    def specialist(self, role: str) -> AbstractContextManager[Any]:
        if not self.client:
            return nullcontext()
        return self.client.start_as_current_observation(
            name=f"delegate-{role}",
            as_type="agent",
            input={"role": role},
            metadata={"protocol": "A2A", "a2a_version": "1.0"},
        )

    def flush(self) -> None:
        if self.client:
            self.client.flush()


@lru_cache(maxsize=1)
def telemetry() -> Telemetry:
    return Telemetry()
