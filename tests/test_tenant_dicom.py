import pydicom
import pytest

from multimodal_agents.tenant_dicom import (
    IDENTIFYING_TAGS,
    UnsupportedDicomError,
    analyze_dicom,
    load_scrubbed_dicom,
    render_representative_frame_png,
    save_scrubbed_dicom,
    strip_identifying_tags,
)


def real_ct_sample_path():
    return pydicom.data.get_testdata_file("CT_small.dcm")


def test_the_real_sample_carries_identifying_tags_before_scrubbing():
    """Confirms the test fixture itself is a meaningful test: this real
    bundled file really does carry real patient-identifying tags, so a
    passing scrub test actually proves something.
    """
    raw = pydicom.dcmread(real_ct_sample_path())
    assert raw.PatientName not in ("", None)
    assert raw.PatientID == "1CT1"
    assert "PatientBirthDate" in raw


def test_strip_identifying_tags_removes_every_real_identifying_tag():
    dataset = pydicom.dcmread(real_ct_sample_path())
    original_study_uid = dataset.StudyInstanceUID
    scrubbed = strip_identifying_tags(dataset)
    for tag in IDENTIFYING_TAGS:
        assert tag not in scrubbed
    assert scrubbed.StudyInstanceUID != original_study_uid


def test_strip_identifying_tags_preserves_spatial_fields_despite_the_name():
    """ImagePositionPatient and PatientPosition contain the word
    "Patient" but are spatial/technical, not identity, and must survive
    a naive substring-based scrub. This repo's scrub is an explicit
    allowlist, not a substring match, specifically to avoid this trap.
    """
    dataset = pydicom.dcmread(real_ct_sample_path())
    has_image_position = "ImagePositionPatient" in dataset
    has_patient_position = "PatientPosition" in dataset
    scrubbed = strip_identifying_tags(dataset)
    assert ("ImagePositionPatient" in scrubbed) == has_image_position
    assert ("PatientPosition" in scrubbed) == has_patient_position


def test_load_scrubbed_dicom_returns_a_dataset_with_no_identifying_tags():
    scrubbed = load_scrubbed_dicom(real_ct_sample_path())
    for tag in IDENTIFYING_TAGS:
        assert tag not in scrubbed


def test_analyze_dicom_runs_real_segmentation_against_the_real_ct_sample():
    result = analyze_dicom(real_ct_sample_path())
    assert result["modality"] == "CT"
    assert result["volume_shape"][:2] == (128, 128)


def test_render_representative_frame_png_produces_real_png_bytes():
    png_bytes = render_representative_frame_png(real_ct_sample_path())
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_representative_frame_png_defaults_match_explicit_frame_t0():
    """The real bundled CT_small.dcm sample has exactly one real frame and
    one real timepoint, so the only real thing to prove here is that the
    default (frame_index=None) resolves to the same middle frame
    (0 // 1 is still a valid, in-range index) an explicit call produces.
    """
    default_bytes = render_representative_frame_png(real_ct_sample_path())
    explicit_bytes = render_representative_frame_png(
        real_ct_sample_path(), frame_index=0, timepoint=0
    )
    assert default_bytes == explicit_bytes


def test_render_representative_frame_png_rejects_an_out_of_range_frame():
    with pytest.raises(UnsupportedDicomError):
        render_representative_frame_png(
            real_ct_sample_path(), frame_index=999
        )


def test_render_representative_frame_png_rejects_an_out_of_range_timepoint():
    with pytest.raises(UnsupportedDicomError):
        render_representative_frame_png(real_ct_sample_path(), timepoint=99)


def test_save_scrubbed_dicom_never_writes_identifying_tags_to_disk(tmp_path):
    destination = tmp_path / "scrubbed.dcm"
    save_scrubbed_dicom(real_ct_sample_path(), destination)
    reloaded = pydicom.dcmread(destination)
    for tag in IDENTIFYING_TAGS:
        assert tag not in reloaded


def test_file_with_no_pixel_data_is_rejected(tmp_path):
    dataset = pydicom.Dataset()
    dataset.PatientID = "should never matter"
    dataset.file_meta = pydicom.dataset.FileMetaDataset()
    dataset.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
    dataset.file_meta.MediaStorageSOPClassUID = pydicom.uid.generate_uid()
    dataset.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
    no_pixel_path = tmp_path / "no-pixels.dcm"
    dataset.save_as(no_pixel_path, enforce_file_format=True)
    with pytest.raises(UnsupportedDicomError):
        load_scrubbed_dicom(no_pixel_path)
