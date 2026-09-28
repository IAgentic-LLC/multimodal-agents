"""Generate and score reproducible visual-corruption cases."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

from .image_grounding import GroundingScore


@dataclass(frozen=True)
class RobustnessSummary:
    present_resolution_rate: float
    absent_rejection_rate: float
    mean_present_iou: float
    protected_violations: int


def create_variants(source: Path, destination: Path) -> dict[str, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGB")
    paths: dict[str, Path] = {}

    def save(name: str, value: Image.Image, **options: object) -> None:
        path = destination / f"{name}.png"
        value.save(path, **options)
        paths[name] = path

    save("clean", image)
    save("blur", image.filter(ImageFilter.GaussianBlur(radius=6)))
    small = image.resize((80, 60), Image.Resampling.BILINEAR)
    save(
        "low-resolution",
        small.resize(image.size, Image.Resampling.NEAREST),
    )
    save("dark", ImageEnhance.Brightness(image).enhance(0.18))
    jpeg_path = destination / "jpeg.jpg"
    image.save(jpeg_path, format="JPEG", quality=8)
    paths["jpeg"] = jpeg_path
    return paths


def summarize_scores(
    present_scores: list[GroundingScore],
    absent_scores: list[GroundingScore],
) -> RobustnessSummary:
    present_iou = [
        score.region_iou
        for score in present_scores
        if score.region_iou is not None
    ]
    all_scores = present_scores + absent_scores
    return RobustnessSummary(
        present_resolution_rate=(
            sum(score.correct_resolution for score in present_scores)
            / len(present_scores)
        ),
        absent_rejection_rate=(
            sum(score.correct_resolution for score in absent_scores)
            / len(absent_scores)
        ),
        mean_present_iou=(
            sum(present_iou) / len(present_iou) if present_iou else 0.0
        ),
        protected_violations=sum(
            score.protected_violations for score in all_scores
        ),
    )
