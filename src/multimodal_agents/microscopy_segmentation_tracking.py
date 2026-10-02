"""Evidence-first segmentation and tracking, checked against real annotated
ground truth, on a real 5D (time, channel, Z, Y, X) light-sheet microscopy
volume.

Production cell tracking uses a Bayesian tracker such as btrack over a full
time-lapse acquisition on a GPU-backed workstation. This module demonstrates
the same evidence contract on a real cropped subset of a real public
mouse intestinal organoid dataset (Zenodo DOI 10.5281/zenodo.22078388,
CC-BY 4.0), which ships with real expert-annotated ground truth: per-
timepoint instance segmentation masks and a real nuclear lineage graph
tracked across all 5 real timepoints. The baseline segments the real H2B
(histone) nuclear-marker channel independently at each timepoint with Otsu
thresholding and connected-component labeling, then reports how its own
instance count compares to the real annotated count at that same
timepoint. See the chapter text for why the full Bayesian lineage tracker
is described but not executed here, and why this baseline's own numbers
are checked against real ground truth rather than only shown on their own.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from skimage import filters, measure

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures"
RAW_LABELS_NPZ = FIXTURES_DIR / "ch09-organoid-crop.npz"
LINEAGE_JSON = FIXTURES_DIR / "ch09-organoid-crop.json"

NUCLEAR_CHANNEL_INDEX = 1  # H2B histone marker; channel 0 is the membrane marker.


@dataclass(frozen=True)
class TimepointComparison:
    timepoint: int
    baseline_instance_count: int
    ground_truth_instance_count: int
    matches_ground_truth: bool


@dataclass(frozen=True)
class GroundTruthLineage:
    total_tracked_nuclei: int
    total_lineage_edges: int
    root_nodes: int
    leaf_nodes: int
    split_nodes: int
    merge_nodes: int


@dataclass(frozen=True)
class TrackingEvidence:
    capability: str
    status: str
    claim: str
    evidence_ids: tuple[str, ...]
    source: str
    model: str
    volume_shape: tuple[int, int, int, int, int]
    comparisons: tuple[TimepointComparison, ...]
    ground_truth: GroundTruthLineage


def segment_timepoint(volume_3d: np.ndarray, min_voxels: int = 10) -> int:
    """Otsu threshold and label connected components in one real 3D (Z, Y, X)
    timepoint of the nuclear-marker channel. Returns the instance count."""
    count, _mask = segment_timepoint_with_mask(volume_3d, min_voxels)
    return count


def segment_timepoint_with_mask(
    volume_3d: np.ndarray, min_voxels: int = 10
) -> tuple[int, np.ndarray]:
    """The same real Otsu-threshold, connected-component segmentation
    segment_timepoint already runs, but also returns the real binary
    mask (1.0 where a kept instance's real labeled region is, 0.0
    elsewhere) rather than discarding it - the real data an overlay
    renders from, not a re-derived approximation.
    """
    threshold = filters.threshold_otsu(volume_3d)
    labeled = measure.label(volume_3d > threshold)
    kept_labels = {
        region.label
        for region in measure.regionprops(labeled)
        if region.area >= min_voxels
    }
    mask = np.isin(labeled, list(kept_labels)).astype(np.float32)
    return len(kept_labels), mask


def load_real_crop() -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    if not RAW_LABELS_NPZ.exists() or not LINEAGE_JSON.exists():
        raise FileNotFoundError(
            "Real organoid crop fixtures are missing. Regenerate them with "
            "scripts/crop_ch09_organoid_dataset.py against a local download "
            "of the real Zenodo dataset (DOI 10.5281/zenodo.22078388)."
        )
    data = np.load(RAW_LABELS_NPZ)
    lineage = json.loads(LINEAGE_JSON.read_text(encoding="utf-8"))
    return data["raw"], data["nucleus"], lineage


def summarize_ground_truth_lineage(lineage: dict[str, object]) -> GroundTruthLineage:
    nodes = lineage["nodes"]
    return GroundTruthLineage(
        total_tracked_nuclei=len(nodes),
        total_lineage_edges=len(lineage["edges"]),
        root_nodes=sum(1 for n in nodes if n["is_root_node"]),
        leaf_nodes=sum(1 for n in nodes if n["is_leaf_node"]),
        split_nodes=sum(1 for n in nodes if n["is_split_node"]),
        merge_nodes=sum(1 for n in nodes if n["is_merge_node"]),
    )


def run_microscopy_tracking() -> TrackingEvidence:
    raw, nucleus_labels, lineage = load_real_crop()
    timepoints = raw.shape[0]

    comparisons: list[TimepointComparison] = []
    for t in range(timepoints):
        nuclear_channel = raw[t, NUCLEAR_CHANNEL_INDEX]
        baseline_count = segment_timepoint(nuclear_channel)
        gt_ids = np.unique(nucleus_labels[t])
        gt_count = int((gt_ids != 0).sum())
        comparisons.append(
            TimepointComparison(
                timepoint=t,
                baseline_instance_count=baseline_count,
                ground_truth_instance_count=gt_count,
                matches_ground_truth=baseline_count == gt_count,
            )
        )

    ground_truth = summarize_ground_truth_lineage(lineage)
    matched = sum(1 for c in comparisons if c.matches_ground_truth)
    claim = (
        f"Otsu baseline instance count matches real annotated ground truth "
        f"at {matched} of {timepoints} real timepoints; the real dataset's "
        f"own lineage graph tracks {ground_truth.total_tracked_nuclei} real "
        f"nuclei across all {timepoints} timepoints with "
        f"{ground_truth.total_lineage_edges} real lineage edges"
    )
    return TrackingEvidence(
        capability="microscopy-segmentation-tracking",
        status="completed",
        claim=claim,
        evidence_ids=tuple(f"timepoint-{c.timepoint}" for c in comparisons),
        source=str(lineage["source"]),
        model="otsu-threshold-connected-components, checked against real annotated ground truth",
        volume_shape=tuple(int(d) for d in raw.shape),
        comparisons=tuple(comparisons),
        ground_truth=ground_truth,
    )


def evidence_to_dict(evidence: TrackingEvidence) -> dict[str, object]:
    payload = asdict(evidence)
    payload["comparisons"] = [asdict(c) for c in evidence.comparisons]
    payload["ground_truth"] = asdict(evidence.ground_truth)
    return payload
