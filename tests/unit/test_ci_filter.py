"""Unit tests for cluster_pipeline.photometry.ci_filter."""
from pathlib import Path

import numpy as np

from cluster_pipeline.photometry.ci_filter import CIFilter, apply_ci_cut


def _write_mag_file(path: Path, rows_1px: list, rows_3px: list):
    """Write a minimal mag file: 6 columns (aper, _, _, _, mag, merr)."""
    lines = []
    for (mag_1, merr_1) in rows_1px:
        lines.append(f"1.00 0 0 0 {mag_1} {merr_1}\n")
    for (mag_3, merr_3) in rows_3px:
        lines.append(f"3.00 0 0 0 {mag_3} {merr_3}\n")
    path.write_text("".join(lines))


def test_ci_formula_mag1_minus_mag3(tmp_path):
    """CI = mag(1px) - mag(3px); sources with CI >= threshold are kept."""
    mag_path = tmp_path / "mag.txt"
    # One source: mag_1=22, mag_3=20.5 -> CI = 1.5; threshold 1.4 -> keep
    _write_mag_file(mag_path, [(22.0, 0.1)], [(20.5, 0.1)])
    (mag_4, merr_4, ci_values), (passes_ci, passes_merr, keep) = apply_ci_cut(
        mag_path, ci_threshold=1.4, merr_cut=0.3
    )
    np.testing.assert_array_almost_equal(ci_values, [22.0 - 20.5])
    assert bool(passes_ci[0]) is True
    assert bool(keep[0]) is True


def test_ci_cut_below_threshold_rejected(tmp_path):
    """Source with CI < threshold is rejected."""
    mag_path = tmp_path / "mag.txt"
    # CI = 22 - 21 = 1.0 < 1.4
    _write_mag_file(mag_path, [(22.0, 0.1)], [(21.0, 0.1)])
    (_, _, _), (passes_ci, _, keep) = apply_ci_cut(mag_path, ci_threshold=1.4)
    assert bool(passes_ci[0]) is False
    assert bool(keep[0]) is False


def test_merr_cut(tmp_path):
    """Sources with merr > merr_cut are rejected."""
    mag_path = tmp_path / "mag.txt"
    # CI high enough, but merr_4 = 0.5 > 0.3
    _write_mag_file(mag_path, [(22.0, 0.1)], [(20.0, 0.5)])
    (_, _, _), (_, passes_merr, keep) = apply_ci_cut(mag_path, ci_threshold=1.0, merr_cut=0.3)
    assert bool(passes_merr[0]) is False
    assert bool(keep[0]) is False


def test_ci_filter_class(tmp_path):
    """CIFilter.apply delegates to apply_ci_cut with config."""
    mag_path = tmp_path / "mag.txt"
    _write_mag_file(mag_path, [(23.0, 0.05)], [(21.0, 0.05)])
    filt = CIFilter(ci_threshold=1.4, merr_cut=0.3)
    (mag_4, merr_4, ci_values), (passes_ci, _, keep) = filt.apply(mag_path)
    np.testing.assert_array_almost_equal(ci_values, [2.0])
    assert bool(keep[0]) is True
