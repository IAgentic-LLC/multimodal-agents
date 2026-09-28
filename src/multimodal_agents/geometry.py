"""Coordinate transforms that keep visual evidence attached to pixels."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import Region


@dataclass(frozen=True)
class ImageSize:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("image dimensions must be positive")


@dataclass(frozen=True)
class FitTransform:
    source: ImageSize
    target: ImageSize
    scale: float
    offset_x: float
    offset_y: float

    def forward(self, region: Region) -> Region:
        left = (
            region.left * self.source.width * self.scale + self.offset_x
        ) / self.target.width
        top = (
            region.top * self.source.height * self.scale + self.offset_y
        ) / self.target.height
        right = (
            region.right * self.source.width * self.scale + self.offset_x
        ) / self.target.width
        bottom = (
            region.bottom * self.source.height * self.scale + self.offset_y
        ) / self.target.height
        return visible_region(left, top, right, bottom)

    def inverse(self, region: Region) -> Region:
        left = (
            region.left * self.target.width - self.offset_x
        ) / self.scale / self.source.width
        top = (
            region.top * self.target.height - self.offset_y
        ) / self.scale / self.source.height
        right = (
            region.right * self.target.width - self.offset_x
        ) / self.scale / self.source.width
        bottom = (
            region.bottom * self.target.height - self.offset_y
        ) / self.scale / self.source.height
        return visible_region(left, top, right, bottom)


def visible_region(
    left: float,
    top: float,
    right: float,
    bottom: float,
) -> Region:
    clipped = (
        max(0.0, left),
        max(0.0, top),
        min(1.0, right),
        min(1.0, bottom),
    )
    if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
        raise ValueError("region is outside the visible image")
    return Region(*clipped)


def fit_transform(
    source: ImageSize,
    target: ImageSize,
    mode: str = "contain",
) -> FitTransform:
    width_scale = target.width / source.width
    height_scale = target.height / source.height
    if mode == "contain":
        scale = min(width_scale, height_scale)
    elif mode == "cover":
        scale = max(width_scale, height_scale)
    else:
        raise ValueError("mode must be contain or cover")
    rendered_width = source.width * scale
    rendered_height = source.height * scale
    return FitTransform(
        source=source,
        target=target,
        scale=scale,
        offset_x=(target.width - rendered_width) / 2,
        offset_y=(target.height - rendered_height) / 2,
    )


def region_in_crop(region: Region, crop: Region) -> Region:
    left = max(region.left, crop.left)
    top = max(region.top, crop.top)
    right = min(region.right, crop.right)
    bottom = min(region.bottom, crop.bottom)
    if left >= right or top >= bottom:
        raise ValueError("region does not intersect crop")
    crop_width = crop.right - crop.left
    crop_height = crop.bottom - crop.top
    return Region(
        (left - crop.left) / crop_width,
        (top - crop.top) / crop_height,
        (right - crop.left) / crop_width,
        (bottom - crop.top) / crop_height,
    )
