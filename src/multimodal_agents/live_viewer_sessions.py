"""A real in-memory relay that lets an MCP tool call push a command to
one specific, already-open browser tab's VolumeViewer or
ChannelVolumeViewer, and have that tab apply it live. This is the
bridge the backend-only MCP tool surface deliberately did not have: an
agent calling set_live_window_level now genuinely changes what a human
is looking at, not just what a REST call returns.

Single-process, in-memory by design: a real constraint, not a
deferred-and-forgotten shortcut. A coordinator scaled to multiple
replicas would need a shared backing store (e.g. Redis pub/sub) instead
of this in-process dict, since a command pushed on one replica would
never reach a browser tab's SSE connection held open on another. The
same real constraint applies to the audit log and rate limiter below:
per-process state, not a durable, cluster-wide guarantee.

Three real gaps this module closes beyond the bare relay:
- Validation: every command is checked against a real schema (known
  actions, required/optional params, real value constraints like which
  axis labels or colormap names actually exist) before it is ever
  queued, so a malformed or unknown command fails loudly here instead
  of being silently ignored by the browser's own dispatch switch.
- Self-correction: the browser reports its own real last-applied state
  back after every change, so an agent can read it back and confirm a
  command actually took effect rather than trusting that "sent" meant
  "applied" (a command could time out in flight, target a tab that
  never actually responds, etc).
- Governance: every command is appended to a real, append-only audit
  log (who, what, when, to which session), and a real per-session rate
  limit rejects a runaway or malicious burst of commands before it ever
  reaches a person's screen.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from asyncio import Queue
from collections import deque
from pathlib import Path
from typing import Literal

ViewerType = Literal["volume", "channel_volume", "detection", "tracking"]

AUDIT_LOG_PATH = Path(
    os.getenv("LIVE_COMMAND_AUDIT_LOG", "runs/live-command-audit.jsonl")
)
RATE_LIMIT_MAX_COMMANDS = 20
RATE_LIMIT_WINDOW_SECONDS = 10.0

# The real axis labels VolumeViewer.tsx/ChannelVolumeViewer.tsx's own
# AXIS_VIEWS expose, and the real colormap names VolumeViewer.tsx's own
# COLORMAP_NAMES expose. Duplicated here (Python backend, TypeScript
# frontend) rather than shared at runtime; if either frontend list ever
# changes, this one must be updated to match or validation will reject
# a real, now-valid value.
VALID_AXES = frozenset({"+X", "-X", "+Y", "-Y", "+Z", "-Z"})
VALID_COLORMAPS = frozenset(
    {
        "Grayscale",
        "X Ray",
        "Black-Body Radiation",
        "Cool to Warm",
        "Cold and Hot",
        "rainbow",
    }
)

# Required and optional real parameter names per real action, plus a
# real per-parameter type/value check. A command missing a required
# parameter, carrying an unknown parameter, carrying a wrongly-typed
# parameter, or carrying a parameter whose value is not one of a real
# fixed set (axis, colormap name) is rejected before it is ever queued.
_REQUIRED_PARAMS: dict[str, frozenset[str]] = {
    "set_window_level": frozenset({"window", "level"}),
    "set_colormap": frozenset({"name"}),
    "set_timepoint": frozenset({"timepoint"}),
    "snap_axis": frozenset({"axis"}),
    "set_segmentation_visible": frozenset({"visible"}),
    "set_grid_visible": frozenset({"visible"}),
    "set_auto_rotate": frozenset({"enabled"}),
    "set_channel_state": frozenset({"channel_index"}),
    "apply_filter_pipeline": frozenset({"steps"}),
    "set_detection_display": frozenset(),
    "set_segmentation_mask_visible": frozenset({"visible"}),
    "set_track_display": frozenset(),
}
_OPTIONAL_PARAMS: dict[str, frozenset[str]] = {
    "set_auto_rotate": frozenset({"direction"}),
    "set_channel_state": frozenset(
        {"visible", "color_hex", "window", "level"}
    ),
    "apply_filter_pipeline": frozenset({"channel_index", "timepoint"}),
    "set_detection_display": frozenset(
        {"confidence_threshold", "boxes_visible", "highlighted_index"}
    ),
    "set_segmentation_mask_visible": frozenset({"nuclear_channel_index"}),
    "set_track_display": frozenset(
        {
            "confidence_threshold",
            "boxes_visible",
            "highlighted_track_id",
            "frame_index",
        }
    ),
}


def _check_type(
    action: str,
    name: str,
    value: object,
    expected: type | tuple[type, ...],
) -> None:
    # bool is a subclass of int in Python; a real "window": True must
    # not silently pass a (int, float) check meant for real numbers.
    if (
        expected in ((int, float), (int,), (float,))
        and isinstance(value, bool)
    ):
        raise InvalidLiveCommandError(
            f"{action}: {name!r} must be a real number, got a bool"
        )
    if not isinstance(value, expected):
        raise InvalidLiveCommandError(
            f"{action}: {name!r} must be {expected}, got "
            f"{type(value).__name__}"
        )


_PARAM_TYPES: dict[str, type | tuple[type, ...]] = {
    "window": (int, float),
    "level": (int, float),
    "name": str,
    "timepoint": int,
    "axis": str,
    "visible": bool,
    "enabled": bool,
    "direction": int,
    "channel_index": int,
    "color_hex": str,
    "steps": list,
    "confidence_threshold": (int, float),
    "boxes_visible": bool,
    "highlighted_index": int,
    "nuclear_channel_index": int,
    "highlighted_track_id": int,
    "frame_index": int,
}


class InvalidLiveCommandError(ValueError):
    pass


class RateLimitExceededError(ValueError):
    pass


class UnknownLiveSessionError(ValueError):
    pass


def validate_command(action: str, params: dict) -> None:
    """Raises InvalidLiveCommandError on the first real problem found:
    an unknown action, a missing required parameter, an unrecognized
    parameter, a wrongly-typed parameter, or a parameter whose value is
    not one of a real fixed set.
    """
    required = _REQUIRED_PARAMS.get(action)
    if required is None:
        raise InvalidLiveCommandError(
            f"unknown live command action {action!r}"
        )
    optional = _OPTIONAL_PARAMS.get(action, frozenset())
    allowed = required | optional

    missing = required - params.keys()
    if missing:
        raise InvalidLiveCommandError(
            f"{action}: missing required parameter(s) {sorted(missing)}"
        )
    unknown = params.keys() - allowed
    if unknown:
        raise InvalidLiveCommandError(
            f"{action}: unknown parameter(s) {sorted(unknown)}"
        )

    for name, value in params.items():
        expected = _PARAM_TYPES[name]
        _check_type(action, name, value, expected)

    if action == "snap_axis" and params["axis"] not in VALID_AXES:
        raise InvalidLiveCommandError(
            f"snap_axis: {params['axis']!r} is not a real axis "
            f"{sorted(VALID_AXES)}"
        )
    if action == "set_colormap" and params["name"] not in VALID_COLORMAPS:
        raise InvalidLiveCommandError(
            f"set_colormap: {params['name']!r} is not a real colormap "
            f"{sorted(VALID_COLORMAPS)}"
        )
    if (
        action == "set_auto_rotate"
        and "direction" in params
        and params["direction"] not in (1, -1)
    ):
        raise InvalidLiveCommandError(
            "set_auto_rotate: direction must be 1 or -1"
        )
    if (
        action in ("set_detection_display", "set_track_display")
        and "confidence_threshold" in params
        and not 0.0 <= params["confidence_threshold"] <= 1.0
    ):
        raise InvalidLiveCommandError(
            f"{action}: confidence_threshold must be between 0.0 and 1.0"
        )
    if action == "apply_filter_pipeline":
        steps = params["steps"]
        if not steps:
            raise InvalidLiveCommandError(
                "apply_filter_pipeline: steps must not be empty"
            )
        for step in steps:
            if not isinstance(step, dict) or not isinstance(
                step.get("filter"), str
            ):
                raise InvalidLiveCommandError(
                    "apply_filter_pipeline: each step must be a real "
                    "dict with a real string 'filter' key - the real "
                    "filter catalog lives in tenant_filters.py"
                )


class LiveSession:
    def __init__(self, tenant_id: str, viewer_type: ViewerType) -> None:
        self.session_id = str(uuid.uuid4())
        self.tenant_id = tenant_id
        self.viewer_type: ViewerType = viewer_type
        self.registered_at = time.time()
        self.queue: Queue[dict] = Queue()
        self.last_known_state: dict = {}
        self.state_reported_at: float | None = None
        self._recent_command_times: deque[float] = deque()


_sessions: dict[str, LiveSession] = {}


def register_session(tenant_id: str, viewer_type: ViewerType) -> LiveSession:
    session = LiveSession(tenant_id, viewer_type)
    _sessions[session.session_id] = session
    return session


def unregister_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _get_owned_session(session_id: str, tenant_id: str) -> LiveSession:
    """Looks up a session and checks tenant ownership in one place, so
    a caller from a different tenant gets the exact same "no such
    session" error a truly nonexistent session_id would: this never
    confirms or denies that a session_id exists for another tenant.
    """
    session = _sessions.get(session_id)
    if session is None or session.tenant_id != tenant_id:
        raise UnknownLiveSessionError(
            f"no live session {session_id!r} for this tenant"
        )
    return session


def list_sessions(tenant_id: str) -> list[dict]:
    return [
        {
            "session_id": session.session_id,
            "viewer_type": session.viewer_type,
            "registered_at": session.registered_at,
        }
        for session in _sessions.values()
        if session.tenant_id == tenant_id
    ]


def session_queue(session_id: str, tenant_id: str) -> Queue[dict]:
    return _get_owned_session(session_id, tenant_id).queue


def _append_audit_entry(entry: dict) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")


def _enforce_rate_limit(session: LiveSession) -> None:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    recent = session._recent_command_times
    while recent and recent[0] < window_start:
        recent.popleft()
    if len(recent) >= RATE_LIMIT_MAX_COMMANDS:
        raise RateLimitExceededError(
            f"more than {RATE_LIMIT_MAX_COMMANDS} live commands in the last "
            f"{RATE_LIMIT_WINDOW_SECONDS:.0f}s for this session"
        )
    recent.append(now)


async def push_command(
    session_id: str,
    tenant_id: str,
    action: str,
    params: dict,
    subject: str | None = None,
) -> None:
    """Validates, rate-limits, audit-logs, then queues a real command
    for delivery, in that order: a rejected or throttled command is
    never queued, and is never logged as having been sent, only
    rejected entries ever claim that outcome.
    """
    session = _get_owned_session(session_id, tenant_id)
    validate_command(action, params)
    _enforce_rate_limit(session)
    _append_audit_entry(
        {
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tenant_id": tenant_id,
            "subject": subject,
            "session_id": session_id,
            "viewer_type": session.viewer_type,
            "action": action,
            "params": params,
        }
    )
    await session.queue.put({"action": action, "params": params})


def report_state(session_id: str, tenant_id: str, state: dict) -> None:
    """The browser's own real current state, reported after applying
    any change (agent-driven or a person's own direct interaction),
    so get_state always reflects what is genuinely on screen right now.
    """
    session = _get_owned_session(session_id, tenant_id)
    session.last_known_state = state
    session.state_reported_at = time.time()


def get_state(session_id: str, tenant_id: str) -> dict:
    session = _get_owned_session(session_id, tenant_id)
    return {
        "state": session.last_known_state,
        "reported_at": session.state_reported_at,
    }
