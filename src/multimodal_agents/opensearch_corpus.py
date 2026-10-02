"""Build the capstone's multimodal evidence corpus from the book's own
retained gate artifacts and committed figures. Every document traces to a
real file on disk; nothing here is invented.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "course_manifest.json"
FIGURES_DIR = REPO_ROOT.parent / "multimodal-agents-book" / "figures"
MAX_TEXT_LENGTH = 2000


@dataclass(frozen=True)
class TextDocument:
    doc_id: str
    chapter: int
    chapter_title: str
    text: str
    evidence_ids: tuple[str, ...]
    source_file: str


@dataclass(frozen=True)
class ImageDocument:
    doc_id: str
    chapter: int
    chapter_title: str
    image_path: Path
    source_file: str


def _collect_evidence_ids(value: object, found: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_ids" and isinstance(item, list):
                found.extend(str(v) for v in item if isinstance(v, str))
            else:
                _collect_evidence_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_evidence_ids(item, found)


def _flatten_text(value: object, path: str, parts: list[str]) -> None:
    if sum(len(p) for p in parts) > MAX_TEXT_LENGTH:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else key
            _flatten_text(item, next_path, parts)
    elif isinstance(value, list):
        for item in value[:8]:
            _flatten_text(item, path, parts)
    elif isinstance(value, (str, int, float, bool)) and value != "":
        parts.append(f"{path}: {value}")


def normalize_gate_file(path: Path) -> tuple[str, tuple[str, ...]]:
    """Return (searchable text, evidence ids) read directly from one real
    retained JSON file. The claim field is preferred verbatim when present;
    otherwise a flattened, honest serialization of the real record is used.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    evidence_ids: list[str] = []
    _collect_evidence_ids(raw, evidence_ids)
    if isinstance(raw, dict) and isinstance(raw.get("claim"), str):
        text = raw["claim"]
    else:
        parts: list[str] = []
        _flatten_text(raw, "", parts)
        text = "; ".join(parts)[:MAX_TEXT_LENGTH]
    return text, tuple(dict.fromkeys(evidence_ids))


def iter_text_documents() -> Iterator[TextDocument]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for episode in manifest["episodes"]:
        chapter = episode["chapter"]
        title = episode["title"]
        gate_dir = REPO_ROOT / episode["artifact"]
        if not gate_dir.exists():
            continue
        for json_path in sorted(gate_dir.glob("*.json")):
            if json_path.name == "manifest.json":
                continue
            text, evidence_ids = normalize_gate_file(json_path)
            if not text:
                continue
            rel = json_path.relative_to(REPO_ROOT).as_posix()
            yield TextDocument(
                doc_id=f"text::{rel}",
                chapter=chapter,
                chapter_title=title,
                text=text,
                evidence_ids=evidence_ids,
                source_file=rel,
            )


def iter_image_documents() -> Iterator[ImageDocument]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    titles = {episode["chapter"]: episode["title"] for episode in manifest["episodes"]}
    if not FIGURES_DIR.exists():
        return
    for image_path in sorted(FIGURES_DIR.glob("ch*.png")):
        chapter_token = image_path.name.split("-", 1)[0]
        try:
            chapter = int(chapter_token.removeprefix("ch"))
        except ValueError:
            continue
        title = titles.get(chapter, f"Chapter {chapter}")
        rel = image_path.relative_to(REPO_ROOT.parent).as_posix()
        yield ImageDocument(
            doc_id=f"image::{rel}",
            chapter=chapter,
            chapter_title=title,
            image_path=image_path,
            source_file=rel,
        )
