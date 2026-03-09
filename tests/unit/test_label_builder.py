"""Unit tests for cluster_pipeline.catalogue.label_builder."""

import numpy as np
import pandas as pd

from cluster_pipeline.catalogue.label_builder import build_final_detection, save_final_detection


def test_build_final_detection_catalogue_only(tmp_path):
    """Build labels from catalogue order when no match_results given."""
    cat_path = tmp_path / "catalogue.parquet"
    df = pd.DataFrame({"cluster_id": [2, 0, 1], "in_catalogue": [True, False, True]})
    df.to_parquet(cat_path, index=False)
    labels = build_final_detection(cat_path, match_results_parquet_path=None)
    assert labels.shape == (3,)
    # Order follows catalogue unique cluster_id (implementation-defined order)
    assert set(labels) <= {0, 1}
    assert labels.dtype in (np.uint8, np.int64, np.int32)


def test_build_final_detection_with_match_order(tmp_path):
    """Build labels aligned to match_results cluster_id order."""
    cat_path = tmp_path / "cat.parquet"
    match_path = tmp_path / "match.parquet"
    pd.DataFrame({"cluster_id": [0, 1, 2], "in_catalogue": [1, 0, 1]}).to_parquet(cat_path, index=False)
    pd.DataFrame({"cluster_id": [2, 0, 1]}).to_parquet(match_path, index=False)
    labels = build_final_detection(cat_path, match_results_parquet_path=match_path)
    # Order follows match_df["cluster_id"].unique() (order of appearance in pandas)
    match_df = pd.read_parquet(match_path)
    order = match_df["cluster_id"].unique().tolist()
    cat = pd.read_parquet(cat_path)
    cid_to_label = dict(zip(cat["cluster_id"], cat["in_catalogue"]))
    expected = np.array([cid_to_label[cid] for cid in order], dtype=np.uint8)
    np.testing.assert_array_equal(labels, expected)


def test_save_final_detection(tmp_path):
    """save_final_detection writes .npy loadable as same array."""
    labels = np.array([1, 0, 1, 0], dtype=np.uint8)
    path = tmp_path / "det" / "labels.npy"
    save_final_detection(labels, path)
    assert path.exists()
    loaded = np.load(path)
    np.testing.assert_array_equal(loaded, labels)
