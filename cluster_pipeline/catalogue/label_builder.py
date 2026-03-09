"""
Binary label builder: final_detection = detection_filters (after catalogue cuts).
Stored as detection_labels aligned with cluster properties by cluster_id.
"""
from pathlib import Path

import numpy as np
import pandas as pd


def build_final_detection(
    catalogue_parquet_path: Path,
    match_results_parquet_path: Path | None = None,
) -> np.ndarray:
    """
    Build final binary detection vector C from catalogue in_catalogue column.
    If match_results parquet is provided, align by cluster_id; otherwise use catalogue order.

    Parameters
    ----------
    catalogue_parquet_path : Path
        Parquet with cluster_id, in_catalogue.
    match_results_parquet_path : Path, optional
        If provided, used to establish order (cluster_id list).

    Returns
    -------
    np.ndarray
        1-D array of 0/1 (detection_labels) aligned with cluster_id order.
    """
    cat = pd.read_parquet(catalogue_parquet_path)
    if match_results_parquet_path is not None and Path(match_results_parquet_path).exists():
        match_df = pd.read_parquet(match_results_parquet_path)
        order = match_df["cluster_id"].unique().tolist()
    else:
        order = cat["cluster_id"].unique().tolist()
    cid_to_label = dict(zip(cat["cluster_id"], cat["in_catalogue"]))
    labels = np.array([cid_to_label.get(cid, 0) for cid in order], dtype=np.uint8)
    return labels


def save_final_detection(labels: np.ndarray, path: Path) -> None:
    """Save final_detection as .npy (legacy-compatible)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, labels)
