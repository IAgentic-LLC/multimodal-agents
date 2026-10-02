"""Real DICOM ingestion, with a mandatory, non-optional scrub of patient-
identifying tags before anything is stored or indexed.

This is a deliberate, curated allowlist of real DICOM attributes known to
carry patient identity (aligned with the tags DICOM PS 3.15's own
Attribute Confidentiality Profile and the HIPAA Safe Harbor identifier
list both call out), not a naive substring match on "Patient": several
real DICOM tags contain the word "Patient" but are purely spatial or
technical (ImagePositionPatient, PatientPosition) and must survive, since
they carry no identity and real volume reconstruction needs them.

This is a best-effort scrub appropriate for a research tool that should
never have received real clinical PHI in the first place, not a
certified HIPAA de-identification pipeline: it does not detect burned-in
pixel text, does not handle private manufacturer tags, and does not
implement DICOM PS 3.15's full profile. A deployment that will genuinely
receive real patient data needs that full program, not this function.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image
from pydicom.uid import generate_uid

from multimodal_agents.medical_segmentation import (
    segment_high_intensity_regions,
)

IDENTIFYING_TAGS = (
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientSex",
    "PatientAge",
    "PatientWeight",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "PatientMotherBirthName",
    "OtherPatientIDs",
    "OtherPatientIDsSequence",
    "OtherPatientNames",
    "EthnicGroup",
    "Occupation",
    "AdditionalPatientHistory",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "OperatorsName",
    "InstitutionName",
    "InstitutionAddress",
    "StationName",
    "AccessionNumber",
    "StudyID",
    "RequestingPhysician",
    "NameOfPhysiciansReadingStudy",
)

MAX_DICOM_VOXELS = 50_000_000


class UnsupportedDicomError(ValueError):
    pass


def strip_identifying_tags(dataset: pydicom.Dataset) -> pydicom.Dataset:
    """Delete every real tag on the curated identifying list, present or
    not, and regenerate fresh UIDs rather than keep the originals, which
    could otherwise be looked up against a source system.
    """
    for tag in IDENTIFYING_TAGS:
        if tag in dataset:
            delattr(dataset, tag)
    for uid_tag in (
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
    ):
        if uid_tag in dataset:
            setattr(dataset, uid_tag, generate_uid())
    return dataset


def load_scrubbed_dicom(path: Path) -> pydicom.Dataset:
    dataset = pydicom.dcmread(path)
    if "PixelData" not in dataset:
        raise UnsupportedDicomError("DICOM file has no pixel data")
    return strip_identifying_tags(dataset)


def pixel_array_as_volume(dataset: pydicom.Dataset) -> np.ndarray:
    """Return (X, Y, Z, T): a single 2D frame padded to one slice and one
    timepoint, or a real multi-frame series treated as real z-slices.
    """
    array = dataset.pixel_array.astype(np.float64)
    if array.ndim == 2:
        volume = array[:, :, np.newaxis, np.newaxis]
    elif array.ndim == 3:
        volume = np.moveaxis(array, 0, 2)[:, :, :, np.newaxis]
    else:
        raise UnsupportedDicomError(
            f"expected a 2D frame or 3D multi-frame series, got "
            f"{array.ndim} dimensions"
        )
    if volume.size > MAX_DICOM_VOXELS:
        raise UnsupportedDicomError(
            f"volume has {volume.size} voxels, exceeding the "
            f"{MAX_DICOM_VOXELS} limit"
        )
    return volume


def describe_regions(regions: list, volume_shape: tuple[int, ...]) -> str:
    if not regions:
        return "no region exceeded the intensity threshold"
    depth = volume_shape[2]
    return (
        f"{len(regions)} high-intensity region(s) across "
        f"{depth} real slice(s)"
    )


def analyze_dicom(path: Path, percentile: float = 97.0) -> dict:
    dataset = load_scrubbed_dicom(path)
    volume = pixel_array_as_volume(dataset)
    threshold = float(np.percentile(volume, percentile))
    regions = segment_high_intensity_regions(volume, threshold=threshold)
    return {
        "modality": getattr(dataset, "Modality", "unknown"),
        "claim": describe_regions(regions, volume.shape),
        "volume_shape": tuple(int(d) for d in volume.shape),
        "region_count": len(regions),
    }


def render_representative_frame_png(
    path: Path, frame_index: int | None = None, timepoint: int = 0
) -> bytes:
    """frame_index defaults to the real middle frame (this function's
    own original always-middle choice); timepoint defaults to 0, its
    own original always-first-timepoint behavior. Both are explicit,
    validated choices now rather than silently hardcoded.
    """
    dataset = load_scrubbed_dicom(path)
    volume = pixel_array_as_volume(dataset)
    depth, timepoints = volume.shape[2], volume.shape[3]
    if frame_index is None:
        frame_index = depth // 2
    if not 0 <= frame_index < depth:
        raise UnsupportedDicomError(
            f"frame_index {frame_index} out of range for {depth} real "
            f"frames"
        )
    if not 0 <= timepoint < timepoints:
        raise UnsupportedDicomError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    plane = volume[:, :, frame_index, timepoint]
    finite = plane[np.isfinite(plane)]
    low, high = (
        (float(finite.min()), float(finite.max()))
        if finite.size
        else (0.0, 1.0)
    )
    span = max(high - low, 1e-6)
    normalized = np.clip((plane - low) / span, 0.0, 1.0)
    image = Image.fromarray((normalized * 255).astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def save_scrubbed_dicom(path: Path, destination: Path) -> None:
    """Persist only the scrubbed dataset, never the original bytes, so a
    real identifying tag never reaches disk even transiently beyond the
    initial read.
    """
    dataset = load_scrubbed_dicom(path)
    dataset.save_as(destination, enforce_file_format=True)
