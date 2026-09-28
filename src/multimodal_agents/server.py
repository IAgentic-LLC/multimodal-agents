"""Local capture server for the first browser-based vertical slice."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .capture import persist_capture


PACKAGE_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PACKAGE_ROOT / "web"


class CaptureHandler(SimpleHTTPRequestHandler):
    server_version = "MultimodalCapture/0.1"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    @property
    def capture_root(self) -> Path:
        return self.server.capture_root  # type: ignore[attr-defined]

    def send_json(self, status: HTTPStatus, value: object) -> None:
        payload = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:
        if self.path != "/api/captures":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 40_000_000:
                raise ValueError("request has an invalid size")
            request = json.loads(self.rfile.read(length))
            metadata = request["metadata"]
            frame = request["frame"]
            audio = base64.b64decode(request["audio_base64"], validate=True)
            paths = persist_capture(
                self.capture_root,
                metadata,
                frame,
                audio,
            )
        except (
            binascii.Error,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        self.send_json(
            HTTPStatus.CREATED,
            {
                "frame": str(paths.frame),
                "audio": str(paths.audio),
                "manifest": str(paths.manifest),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    parser.add_argument("--capture-root", default="runs/local-captures")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), CaptureHandler)
    server.capture_root = Path(args.capture_root).resolve()  # type: ignore[attr-defined]
    print(f"Capture UI: http://{args.host}:{args.port}")
    print(f"Artifacts: {server.capture_root}")  # type: ignore[attr-defined]
    server.serve_forever()


if __name__ == "__main__":
    main()
