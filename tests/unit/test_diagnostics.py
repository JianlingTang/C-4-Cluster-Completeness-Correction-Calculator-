"""Unit tests for cluster_pipeline.pipeline.diagnostics."""
import numpy as np

from cluster_pipeline.pipeline.diagnostics import (
    completeness_per_bin,
    load_coords_with_mag,
    load_match_summaries,
)


def test_completeness_per_bin_empty():
    """Empty mags/matched returns valid bin structure with nan completeness."""
    mags = np.array([], dtype=float)
    matched = np.array([], dtype=np.int8)
    bin_centers, comp, edges = completeness_per_bin(mags, matched, mag_min=0, mag_max=10, n_bins=5)
    assert edges.shape == (6,)
    assert bin_centers.shape == (5,)
    assert comp.shape == (5,)
    assert np.all(np.isnan(comp))


def test_completeness_per_bin_all_matched():
    """If all sources matched, completeness is 1 in every non-empty bin."""
    mags = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    matched = np.ones(5, dtype=np.int8)
    bin_centers, comp, edges = completeness_per_bin(
        mags, matched, mag_bins=np.linspace(0, 6, 4)
    )
    assert comp.shape == (3,)
    # Bins [0,2), [2,4), [4,6]: 2 + 2 + 1 points
    valid = ~np.isnan(comp)
    np.testing.assert_array_almost_equal(comp[valid], 1.0)


def test_completeness_per_bin_none_matched():
    """If no sources matched, completeness is 0 in every non-empty bin."""
    mags = np.array([1.0, 2.0, 3.0])
    matched = np.zeros(3, dtype=np.int8)
    bin_centers, comp, edges = completeness_per_bin(
        mags, matched, mag_min=0, mag_max=4, n_bins=2
    )
    assert comp.shape == (2,)
    assert np.nansum(comp) == 0


def test_completeness_per_bin_faint_lower_than_bright():
    """Completeness in faint (high mag) bin should be <= bright (low mag) bin when detection decreases with mag."""
    # Simulate: bright (low mag) = more detected, faint (high mag) = less detected
    np.random.seed(42)
    mags = np.concatenate([
        np.random.uniform(18, 20, 100),   # bright
        np.random.uniform(24, 26, 100),   # faint
    ])
    matched = np.concatenate([
        np.ones(100, dtype=np.int8),     # all bright detected
        np.zeros(100, dtype=np.int8),     # no faint detected
    ])
    bin_centers, comp, edges = completeness_per_bin(
        mags, matched, mag_min=17, mag_max=27, n_bins=10
    )
    valid = np.isfinite(comp)
    if np.sum(valid) >= 2:
        # First bins (bright) should have higher completeness than last bins (faint)
        bright_comp = np.nanmean(comp[:5])
        faint_comp = np.nanmean(comp[5:])
        assert bright_comp >= faint_comp - 1e-6


def test_completeness_per_bin_values_in_zero_one():
    """Completeness values are in [0, 1] or nan."""
    np.random.seed(123)
    mags = np.random.uniform(20, 25, 200)
    matched = (np.random.rand(200) > 0.5).astype(np.int8)
    bin_centers, comp, edges = completeness_per_bin(mags, matched, n_bins=10)
    valid = np.isfinite(comp)
    assert np.all(comp[valid] >= 0)
    assert np.all(comp[valid] <= 1)


def test_load_coords_with_mag_two_cols():
    """Two-column file returns coords and None mags."""
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("100.0 200.0\n300.0 400.0\n")
        path = Path(f.name)
    try:
        coords, mags = load_coords_with_mag(path)
        assert coords.shape == (2, 2)
        np.testing.assert_array_almost_equal(coords[0], [100, 200])
        assert mags is None
    finally:
        path.unlink(missing_ok=True)


def test_load_coords_with_mag_three_cols():
    """Three-column file returns coords and mags."""
    import tempfile
    from pathlib import Path
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("100.0 200.0 22.5\n300.0 400.0 23.1\n")
        path = Path(f.name)
    try:
        coords, mags = load_coords_with_mag(path)
        assert coords.shape == (2, 2)
        assert mags.shape == (2,)
        np.testing.assert_array_almost_equal(mags, [22.5, 23.1])
    finally:
        path.unlink(missing_ok=True)


def test_load_match_summaries_empty_dir(tmp_path):
    """Empty diagnostics dir returns empty arrays."""
    mags, matched = load_match_summaries(tmp_path, outname="test")
    assert mags.shape == (0,)
    assert matched.shape == (0,)


def test_load_match_summaries_one_file(tmp_path):
    """Single match summary file is loaded correctly."""
    f = tmp_path / "match_summary_frame0_reff3.00_test.txt"
    f.write_text("22.0 1\n23.0 0\n24.0 1\n")
    mags, matched = load_match_summaries(tmp_path, outname="test")
    np.testing.assert_array_almost_equal(mags, [22.0, 23.0, 24.0])
    np.testing.assert_array_equal(matched, [1, 0, 1])
