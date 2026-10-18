"""A real terminal CLI over the same functions studio_mcp_server.py
exposes to an agent, for scripting or reproducing a chapter's exact
sequence without an MCP client. Every subcommand calls the project's
own real analysis functions directly (offline subcommands) or the
coordinator's real live-session REST endpoints (live-* subcommands) -
no logic is duplicated here, only argument parsing and JSON printing.

Examples:
    uv run studio-cli describe-tiff sample.tiff
    uv run studio-cli filter-tiff sample.tiff --steps \
        '[{"filter": "gaussian_blur", "params": {"sigma": 2.0}}]' \
        --out filtered.png
    uv run studio-cli analyze-video-tracking clip.mp4
    uv run studio-cli live-list --coordinator-url http://127.0.0.1:8080
    uv run studio-cli live-send <session_id> set_timepoint \
        '{"timepoint": 1}' --coordinator-url http://127.0.0.1:8080
    uv run studio-cli live-screenshot <session_id> --out shot.png \
        --coordinator-url http://127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path

from multimodal_agents.studio_mcp_server import (
    _live_session_request,
    _resolve_local_file,
    _select_channel,
    _send_live_command,
)
from multimodal_agents.tenant_filters import (
    UnsupportedFilterError,
    apply_filter_pipeline,
    volume_intensity_stats,
)
from multimodal_agents.tenant_tiff import (
    UnsupportedTiffError,
    describe_tiff,
    fetch_tiff_channel_volume,
    render_volume_max_projection_png,
    segment_tiff,
)
from multimodal_agents.tenant_video_tracking import (
    UnsupportedVideoError,
    describe_tracks,
    extract_frames,
    track_frames,
    tracked_frames_to_dicts,
)


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _cmd_describe_tiff(args: argparse.Namespace) -> int:
    try:
        _print_json(describe_tiff(_resolve_local_file(args.file_path)))
    except UnsupportedTiffError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def _cmd_segment_tiff(args: argparse.Namespace) -> int:
    try:
        result = segment_tiff(
            _resolve_local_file(args.file_path), args.channel_index
        )
    except UnsupportedTiffError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    _print_json(result)
    return 0


def _cmd_filter_tiff(args: argparse.Namespace) -> int:
    path = _resolve_local_file(args.file_path)
    try:
        steps = json.loads(args.steps)
        volume, _spacing = fetch_tiff_channel_volume(path, args.timepoint)
        channel_volume = _select_channel(volume, args.channel_index)
        filtered = apply_filter_pipeline(channel_volume, steps)
    except (UnsupportedTiffError, UnsupportedFilterError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    metadata = {
        "channel_index": args.channel_index,
        "timepoint": args.timepoint,
        "steps": steps,
        "before": volume_intensity_stats(channel_volume),
        "after": volume_intensity_stats(filtered),
    }
    if args.out:
        Path(args.out).write_bytes(render_volume_max_projection_png(filtered))
        metadata["saved_to"] = args.out
    _print_json(metadata)
    return 0


def _cmd_analyze_video_tracking(args: argparse.Namespace) -> int:
    path = _resolve_local_file(args.file_path)
    try:
        frames = extract_frames(
            path.read_bytes(), max_frames=args.max_frames
        )
        tracked = track_frames(frames)
    except UnsupportedVideoError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    _print_json(
        {
            "claim": describe_tracks(tracked),
            "frame_count": len(frames),
            "tracks": tracked_frames_to_dicts(tracked),
        }
    )
    return 0


def _cmd_live_list(args: argparse.Namespace) -> int:
    _print_json(
        _live_session_request(
            args.coordinator_url,
            args.access_token,
            "GET",
            "/api/studio/live-sessions",
        )
    )
    return 0


def _cmd_live_state(args: argparse.Namespace) -> int:
    _print_json(
        _live_session_request(
            args.coordinator_url,
            args.access_token,
            "GET",
            f"/api/studio/live-sessions/{args.session_id}/state",
        )
    )
    return 0


def _cmd_live_send(args: argparse.Namespace) -> int:
    params = json.loads(args.params) if args.params else {}
    _print_json(
        _send_live_command(
            args.coordinator_url,
            args.access_token,
            args.session_id,
            args.action,
            params,
        )
    )
    return 0


def _cmd_live_screenshot(args: argparse.Namespace) -> int:
    path = f"/api/studio/live-sessions/{args.session_id}/screenshot"
    before = _live_session_request(
        args.coordinator_url, args.access_token, "GET", path
    ).get("reported_at")
    _send_live_command(
        args.coordinator_url,
        args.access_token,
        args.session_id,
        "capture_screenshot",
        {},
    )
    deadline = time.monotonic() + args.timeout_seconds
    while time.monotonic() < deadline:
        result = _live_session_request(
            args.coordinator_url, args.access_token, "GET", path
        )
        reported_at = result.get("reported_at")
        if reported_at is not None and reported_at != before:
            header, _, encoded = result["image_base64"].partition(",")
            Path(args.out).write_bytes(
                base64.b64decode(encoded or header)
            )
            _print_json({"saved_to": args.out, "reported_at": reported_at})
            return 0
        time.sleep(0.3)
    print(
        f"error: no new screenshot reported within "
        f"{args.timeout_seconds}s",
        file=sys.stderr,
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="studio-cli",
        description=__doc__.split("\n\n")[0],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    describe_tiff_p = sub.add_parser(
        "describe-tiff", help="describe a local TIFF/OME-TIFF file"
    )
    describe_tiff_p.add_argument("file_path")
    describe_tiff_p.set_defaults(func=_cmd_describe_tiff)

    segment_tiff_p = sub.add_parser(
        "segment-tiff", help="segment a local TIFF/OME-TIFF channel"
    )
    segment_tiff_p.add_argument("file_path")
    segment_tiff_p.add_argument("--channel-index", type=int, default=0)
    segment_tiff_p.set_defaults(func=_cmd_segment_tiff)

    filter_tiff_p = sub.add_parser(
        "filter-tiff", help="apply a filter pipeline to a local TIFF file"
    )
    filter_tiff_p.add_argument("file_path")
    filter_tiff_p.add_argument(
        "--steps", required=True, help="JSON list of filter steps"
    )
    filter_tiff_p.add_argument("--channel-index", type=int, default=0)
    filter_tiff_p.add_argument("--timepoint", type=int, default=0)
    filter_tiff_p.add_argument("--out", help="save the filtered PNG here")
    filter_tiff_p.set_defaults(func=_cmd_filter_tiff)

    track_p = sub.add_parser(
        "analyze-video-tracking", help="track objects in a local video"
    )
    track_p.add_argument("file_path")
    track_p.add_argument("--max-frames", type=int, default=30)
    track_p.set_defaults(func=_cmd_analyze_video_tracking)

    for name, builder, extra in (
        ("live-list", _cmd_live_list, None),
        ("live-state", _cmd_live_state, "session_id"),
        ("live-send", _cmd_live_send, "session_id action params"),
        ("live-screenshot", _cmd_live_screenshot, "session_id"),
    ):
        live_p = sub.add_parser(
            name, help=f"{name.replace('-', ' ')} on a live coordinator"
        )
        live_p.add_argument("--coordinator-url", required=True)
        live_p.add_argument("--access-token")
        if extra and "session_id" in extra:
            live_p.add_argument("session_id")
        if extra and "action" in extra:
            live_p.add_argument("action")
        if extra and "params" in extra:
            live_p.add_argument(
                "params", nargs="?", help="JSON object of params"
            )
        if name == "live-screenshot":
            live_p.add_argument("--out", required=True)
            live_p.add_argument(
                "--timeout-seconds", type=float, default=8.0
            )
        live_p.set_defaults(func=builder)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
