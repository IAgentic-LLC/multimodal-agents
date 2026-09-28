"""Validate the book's build-along contract against the companion repository."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT.parent / "multimodal-agents-book"
MANIFEST = ROOT / "course_manifest.json"


def fail(message: str) -> None:
    raise SystemExit(f"course contract failed: {message}")


def main() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    episodes = data["episodes"]
    chapters = sorted((BOOK / "chapters").glob("[0-9][0-9]-*.md"))

    if [item["chapter"] for item in episodes] != list(range(1, 35)):
        fail("course_manifest.json must contain chapters 1 through 34 in order")
    if len(chapters) != 34:
        fail(f"expected 34 numbered chapter files, found {len(chapters)}")

    for episode, chapter_path in zip(episodes, chapters, strict=True):
        number = episode["chapter"]
        if int(chapter_path.name[:2]) != number:
            fail(f"chapter order mismatch at {chapter_path.name}")
        body = chapter_path.read_text(encoding="utf-8")
        if body.count("## Follow along") != 1:
            fail(f"{chapter_path.name} must contain exactly one Follow along section")
        for source in episode["files"]:
            if not (ROOT / source).is_file():
                fail(f"chapter {number} references missing source file: {source}")
            if source not in body:
                fail(f"chapter {number} does not name source file: {source}")
        for required in (episode["run"], episode["test"], episode["artifact"]):
            if required not in body:
                fail(f"chapter {number} omits its manifest value: {required}")
        match = re.fullmatch(
            r"uv run python scripts/verify_chapter\.py (\d+)", episode["test"]
        )
        if not match or int(match.group(1)) != number:
            fail(f"chapter {number} has a noncanonical verifier command")

    subprocess.run(
        [sys.executable, "scripts/verify_chapter.py", "1"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/verify_chapter.py", "34"],
        cwd=ROOT,
        check=True,
    )
    print(
        "course contract passed: 34 chapters, all source paths and lesson "
        "instructions validated; boundary chapter tests passed"
    )


if __name__ == "__main__":
    main()
