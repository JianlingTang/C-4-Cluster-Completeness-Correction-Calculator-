"""
Catalogue filters: photometric error cut, multi-band availability, CI cut result.
Combined into a single in_catalogue flag per cluster_id.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.schemas import CATALOGUE_FILTERS_SCHEMA


def apply_catalogue_filters(
    photometry_parquet_path: Path,
    merr_cut: float = 0.3,
    vband_filter: str = "F555W",
    required_filters: list[str] | None = None,
) -> pd.DataFrame:
    """
    Build catalogue table: one row per (cluster_id, frame_id, reff) with passes_ci, passes_merr,
    passes_multiband, in_catalogue. Uses photometry parquet (with ci, merr per filter).

    Parameters
    ----------
    photometry_parquet_path : Path
        Parquet with columns cluster_id, galaxy_id, frame_id, reff, filter_name, mag, merr, ci.
    merr_cut : float
        Maximum merr to pass.
    vband_filter : str
        Filter name for CI cut (e.g. F555W).
    required_filters : list of str, optional
        All filters that must have valid photometry for passes_multiband.

    Returns
    -------
    pd.DataFrame
        Columns per CATALOGUE_FILTERS_SCHEMA.
    """
    df = pd.read_parquet(photometry_parquet_path)
    if "passes_ci" not in df.columns:
        df["passes_ci"] = 1
    if "passes_merr" not in df.columns:
        df["passes_merr"] = (df["merr"] <= merr_cut).astype(np.int8)
    grp = df.groupby(["cluster_id", "galaxy_id", "frame_id", "reff"])
    agg = grp.agg(
        passes_ci=("passes_ci", "max"),
        passes_merr=("passes_merr", "min"),
    ).reset_index()
    if required_filters is not None:
        n_required = len(required_filters)
        n_filters_per_row = grp["filter_name"].nunique().reset_index()
        n_filters_per_row = n_filters_per_row.rename(columns={"filter_name": "n_filters"})
        agg = agg.merge(n_filters_per_row, on=["cluster_id", "galaxy_id", "frame_id", "reff"])
        agg["passes_multiband"] = (agg["n_filters"] >= n_required).astype(np.int8)
        agg = agg.drop(columns=["n_filters"])
    else:
        agg["passes_multiband"] = 1
    agg["in_catalogue"] = (
        (agg["passes_ci"] == 1) & (agg["passes_merr"] == 1) & (agg["passes_multiband"] == 1)
    ).astype(np.int8)
    return agg[list(CATALOGUE_FILTERS_SCHEMA.keys())]


def write_catalogue_parquet(df: pd.DataFrame, path: Path) -> None:
    """Write catalogue table to parquet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
