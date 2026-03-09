"""Unit tests for cluster_pipeline.matching.coordinate_matcher."""
import numpy as np

from cluster_pipeline.matching.coordinate_matcher import (
    MatchResult,
    match_coordinates,
)


def test_match_coordinates_all_matched():
    """Exact same coords: all injected match."""
    inj = np.array([[10.0, 20.0], [30.0, 40.0]])
    det = np.array([[10.0, 20.0], [30.0, 40.0]])
    result = match_coordinates(inj, det, tolerance_pix=2.0)
    assert result.n_injected == 2
    assert result.n_matched == 2
    assert result.matched_indices == [0, 1]


def test_match_coordinates_none_matched():
    """Detected coords far away: no matches."""
    inj = np.array([[10.0, 20.0]])
    det = np.array([[100.0, 200.0]])
    result = match_coordinates(inj, det, tolerance_pix=3.0)
    assert result.n_matched == 0
    assert result.matched_indices == []


def test_match_coordinates_within_tolerance():
    """One injected within tolerance of one detected."""
    inj = np.array([[10.0, 20.0], [50.0, 50.0]])
    det = np.array([[10.5, 20.5], [100.0, 100.0]])
    result = match_coordinates(inj, det, tolerance_pix=1.0)
    assert result.n_matched == 1
    assert result.matched_indices == [0]


def test_match_result_detection_labels():
    """MatchResult.detection_labels is 0/1 per injected."""
    result = MatchResult(
        injected_path=__import__("pathlib").Path("."),
        detected_path=__import__("pathlib").Path("."),
        cluster_ids=[0, 1, 2],
        matched_indices=[0, 2],
        matched_positions=[(1.0, 1.0), (3.0, 3.0)],
        n_injected=3,
        n_matched=2,
        tolerance_pix=3.0,
    )
    assert result.detection_labels == [1, 0, 1]


def test_match_empty_injected():
    """Zero injected returns valid result."""
    result = match_coordinates(np.array([]).reshape(0, 2), np.array([[1, 1]]), tolerance_pix=3.0)
    assert result.n_injected == 0
    assert result.n_matched == 0


def test_match_empty_detected():
    """Zero detected: no matches."""
    result = match_coordinates(np.array([[1, 1]]), np.array([]).reshape(0, 2), tolerance_pix=3.0)
    assert result.n_injected == 1
    assert result.n_matched == 0
