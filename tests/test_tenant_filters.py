import numpy as np
import pytest

from multimodal_agents.tenant_filters import (
    UnsupportedFilterError,
    apply_filter,
    apply_filter_pipeline,
    enhance_contrast,
    gaussian_blur,
    median_filter,
    morphological_operation,
    normalize_intensity,
    sharpen,
    subtract_background,
    volume_intensity_stats,
)


def real_blob_volume(depth: int = 6, size: int = 24) -> np.ndarray:
    volume = np.zeros((depth, size, size), dtype=np.float32)
    volume[1:3, 4:9, 4:9] = 200.0
    volume[1:3, 15:20, 15:20] = 200.0
    return volume


def test_gaussian_blur_reduces_real_noise_variance():
    rng = np.random.default_rng(0)
    pure_noise = rng.normal(100, 20, (6, 24, 24)).astype(np.float32)
    blurred = gaussian_blur(pure_noise, sigma=2.0)
    assert blurred.std() < pure_noise.std()
    assert blurred.shape == pure_noise.shape


def test_median_filter_removes_a_real_outlier_pixel():
    volume = np.full((6, 24, 24), 50.0, dtype=np.float32)
    volume[3, 12, 12] = 5000.0  # one real extreme outlier voxel
    filtered = median_filter(volume, size=3)
    assert filtered[3, 12, 12] == pytest.approx(50.0)


def test_sharpen_output_is_bounded_in_the_real_unit_range():
    volume = real_blob_volume()
    sharpened = sharpen(volume, radius=1.0, amount=1.0)
    assert sharpened.min() >= 0.0
    assert sharpened.max() <= 1.0


def test_enhance_contrast_output_is_bounded_in_the_real_unit_range():
    volume = real_blob_volume()
    enhanced = enhance_contrast(volume, clip_limit=0.05)
    assert enhanced.min() >= 0.0
    assert enhanced.max() <= 1.0


def test_subtract_background_removes_a_real_broad_background():
    size = 24
    gradient = np.tile(np.linspace(50, 150, size), (size, 1))
    background = np.broadcast_to(gradient, (6, size, size)).copy()
    volume = background.astype(np.float32)
    volume[1:3, 4:9, 4:9] += 200.0  # a real bright blob above the gradient

    subtracted = subtract_background(volume, radius=3)
    background_region_before = volume[1, 0, 0]
    background_region_after = subtracted[1, 0, 0]
    blob_region_after = subtracted[1, 6, 6]
    assert background_region_after < background_region_before
    assert blob_region_after > background_region_after


def test_morphological_erosion_shrinks_a_real_bright_region():
    volume = real_blob_volume()
    eroded = morphological_operation(volume, "erosion", radius=1)
    bright_before = int((volume > 100).sum())
    bright_after = int((eroded > 100).sum())
    assert bright_after < bright_before


def test_morphological_dilation_grows_a_real_bright_region():
    volume = real_blob_volume()
    dilated = morphological_operation(volume, "dilation", radius=1)
    bright_before = int((volume > 100).sum())
    bright_after = int((dilated > 100).sum())
    assert bright_after > bright_before


def test_morphological_operation_rejects_an_unknown_operation():
    volume = real_blob_volume()
    with pytest.raises(UnsupportedFilterError, match="unknown morph"):
        morphological_operation(volume, "not-a-real-operation")


def test_normalize_intensity_rescales_to_the_requested_range():
    volume = real_blob_volume()
    normalized = normalize_intensity(volume, out_range=(0.0, 1.0))
    assert normalized.min() == pytest.approx(0.0)
    assert normalized.max() == pytest.approx(1.0)


def test_apply_filter_rejects_an_unknown_filter_name():
    volume = real_blob_volume()
    with pytest.raises(UnsupportedFilterError, match="unknown filter"):
        apply_filter(volume, "not-a-real-filter")


def test_apply_filter_rejects_a_real_hallucinated_parameter_name():
    volume = real_blob_volume()
    with pytest.raises(UnsupportedFilterError, match="real parameters are"):
        apply_filter(
            volume,
            "gaussian_blur",
            {"sigma_x": 3, "sigma_y": 3, "sigma_z": 3},
        )


def test_apply_filter_pipeline_chains_real_steps_in_order():
    volume = real_blob_volume()
    result = apply_filter_pipeline(
        volume,
        steps=[
            {"filter": "gaussian_blur", "params": {"sigma": 1.0}},
            {"filter": "normalize_intensity"},
        ],
    )
    # normalize_intensity ran last, so the final real range is [0, 1]
    # regardless of gaussian_blur's own real intermediate output range.
    assert result.min() == pytest.approx(0.0)
    assert result.max() == pytest.approx(1.0)


def test_volume_intensity_stats_reports_real_min_max_mean():
    volume = np.array([[[1.0, 2.0], [3.0, 4.0]]], dtype=np.float32)
    stats = volume_intensity_stats(volume)
    assert stats == {"min": 1.0, "max": 4.0, "mean": 2.5}
