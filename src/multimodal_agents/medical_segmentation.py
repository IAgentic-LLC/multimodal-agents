"""Evidence-first segmentation of a real 4D (volume plus time) MRI series.

Production volumetric segmentation runs a pretrained network such as
TotalSegmentator across a full 3D NIfTI series on a GPU. This module
demonstrates the same evidence contract on a real retained 4D volume,
loaded through nibabel, using an intensity-threshold and connected-component
baseline that runs on CPU in well under a second per slice. See the chapter
text for why the full pretrained pipeline is described but not executed
here.

The retained volume is nibabel's own bundled `example4d.nii.gz`: 128 x 96
in-plane, 24 real z-slices, 2 real timepoints. It ships with the `nibabel`
package itself, so no network download is required to reproduce this
chapter.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage


@dataclass(frozen=True)
class SegmentedRegion:
    region_id: str
    label: str
    voxel_count: int
    mean_intensity: float
    slice_index: int
    timepoint: int
    bbox: tuple[int, int, int, int]


@dataclass(frozen=True)
class SegmentationEvidence:
    capability: str
    status: str
    claim: str
    evidence_ids: tuple[str, ...]
    source: str
    model: str
    volume_shape: tuple[int, int, int, int]
    regions: tuple[SegmentedRegion, ...]


def load_volume(nifti_path: Path) -> np.ndarray:
    """Load the real 4D volume as (X, Y, Z, T)."""
    img = nib.load(nifti_path)
    return np.asarray(img.get_fdata())


def segment_high_intensity_regions(
    volume: np.ndarray,
    threshold: float,
    min_voxels: int = 40,
) -> list[SegmentedRegion]:
    """Label connected high-intensity regions, per z-slice, per timepoint.

    The volume carries no Hounsfield calibration, so the threshold is a real
    percentile of this specific retained volume's own intensity distribution
    rather than a borrowed CT constant. Each region is a bounded observation,
    not an anatomical diagnosis.
    """
    regions: list[SegmentedRegion] = []
    depth, timepoints = volume.shape[2], volume.shape[3]
    for t in range(timepoints):
        for z in range(depth):
            plane = volume[:, :, z, t]
            mask = plane > threshold
            labeled, count = ndimage.label(mask)
            for region_id in range(1, count + 1):
                voxels = labeled == region_id
                voxel_count = int(voxels.sum())
                if voxel_count < min_voxels:
                    continue
                mean_intensity = float(plane[voxels].mean())
                ys, xs = np.nonzero(voxels)
                bbox = (int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max()))
                regions.append(
                    SegmentedRegion(
                        region_id=f"region-t{t}-z{z}-{region_id}",
                        label="high-intensity candidate",
                        voxel_count=voxel_count,
                        mean_intensity=round(mean_intensity, 1),
                        slice_index=z,
                        timepoint=t,
                        bbox=bbox,
                    )
                )
    return regions


def segment_volume(nifti_path: Path, percentile: float = 97.0) -> SegmentationEvidence:
    volume = load_volume(nifti_path)
    threshold = float(np.percentile(volume, percentile))
    regions = segment_high_intensity_regions(volume, threshold=threshold)
    by_timepoint = {
        t: len([r for r in regions if r.timepoint == t])
        for t in range(volume.shape[3])
    }
    status = "completed" if regions else "no_regions_found"
    t0, t1 = by_timepoint.get(0, 0), by_timepoint.get(1, 0)
    claim = (
        f"{len(regions)} high-intensity region(s) across "
        f"{volume.shape[2]} slices and {volume.shape[3]} timepoints "
        f"({t0} at t=0, {t1} at t=1)"
        if regions
        else f"no region exceeded the {percentile:.0f}th percentile threshold"
    )
    return SegmentationEvidence(
        capability="medical-segmentation",
        status=status,
        claim=claim,
        evidence_ids=tuple(r.region_id for r in regions),
        source=str(nifti_path),
        model="percentile-threshold-connected-components",
        volume_shape=tuple(int(d) for d in volume.shape),
        regions=tuple(regions),
    )


def evidence_to_dict(evidence: SegmentationEvidence) -> dict[str, object]:
    payload = asdict(evidence)
    payload["regions"] = [asdict(r) for r in evidence.regions]
    return payload
