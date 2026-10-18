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
    lessons = data["lessons"]
    chapters = sorted((BOOK / "chapters").glob("[0-9][0-9]-*.md"))

    if [item["chapter"] for item in lessons] != list(range(1, 39)):
        fail("course_manifest.json must contain chapters 1 through 38 in order")
    if len(chapters) != 38:
        fail(f"expected 38 numbered chapter files, found {len(chapters)}")

    for lesson, chapter_path in zip(lessons, chapters, strict=True):
        number = lesson["chapter"]
        if int(chapter_path.name[:2]) != number:
            fail(f"chapter order mismatch at {chapter_path.name}")
        body = chapter_path.read_text(encoding="utf-8")
        if body.count("## Follow along") != 1:
            fail(f"{chapter_path.name} must contain exactly one Follow along section")
        for source in lesson["files"]:
            if not (ROOT / source).is_file():
                fail(f"chapter {number} references missing source file: {source}")
            if source not in body:
                fail(f"chapter {number} does not name source file: {source}")
        for required in (lesson["run"], lesson["test"], lesson["artifact"]):
            if required not in body:
                fail(f"chapter {number} omits its manifest value: {required}")
        match = re.fullmatch(
            r"uv run python scripts/verify_chapter\.py (\d+)", lesson["test"]
        )
        if not match or int(match.group(1)) != number:
            fail(f"chapter {number} has a noncanonical verifier command")

    subprocess.run(
        [sys.executable, "scripts/verify_chapter.py", "1"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "scripts/verify_chapter.py", "38"],
        cwd=ROOT,
        check=True,
    )
    print(
        "course contract passed: 38 chapters, all source paths and lesson "
        "instructions validated; boundary chapter tests passed"
    )


if __name__ == "__main__":
    main()
