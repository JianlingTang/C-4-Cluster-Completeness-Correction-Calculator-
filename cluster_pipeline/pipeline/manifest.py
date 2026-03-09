"""
Manifest tracking state of each (galaxy_id, frame_id, reff) job.
Stored as parquet: one row per job with status column.
Enables resume and parallel execution without duplicate work.
"""
from pathlib import Path

import pandas as pd

MANIFEST_SCHEMA = {
    "galaxy_id": "str",
    "frame_id": "int32",
    "reff": "float64",
    "status": "str",  # pending, injection_done, ... catalogue_done, dataset_done, failed
    "outname": "str",
    "updated_at": "str",  # ISO timestamp
}

STATUS_PENDING = "pending"
STATUS_INJECTION_DONE = "injection_done"
STATUS_DETECTION_DONE = "detection_done"
STATUS_MATCHING_DONE = "matching_done"
STATUS_PHOTOMETRY_DONE = "photometry_done"
STATUS_CATALOGUE_DONE = "catalogue_done"
STATUS_DATASET_DONE = "dataset_done"
STATUS_FAILED = "failed"


def manifest_path(config_base: Path, galaxy_id: str, outname: str = "pipeline") -> Path:
    """Path to manifest parquet for a galaxy run."""
    return config_base / galaxy_id / "white" / f"manifest_{outname}.parquet"


def load_manifest(path: Path) -> pd.DataFrame:
    """Load manifest from parquet; empty DataFrame with correct columns if missing."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=list(MANIFEST_SCHEMA.keys()))
    return pd.read_parquet(path)


def save_manifest(df: pd.DataFrame, path: Path) -> None:
    """Write manifest to parquet."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def get_job_status(
    manifest_path: Path, galaxy_id: str, frame_id: int, reff: float
) -> str | None:
    """Return status for (galaxy_id, frame_id, reff) or None if not in manifest."""
    df = load_manifest(manifest_path)
    if df.empty:
        return None
    m = (df["galaxy_id"] == galaxy_id) & (df["frame_id"] == frame_id) & (df["reff"] == reff)
    rows = df[m]
    if len(rows) == 0:
        return None
    return str(rows.iloc[0]["status"])


def set_job_status(
    manifest_path: Path,
    galaxy_id: str,
    frame_id: int,
    reff: float,
    status: str,
    outname: str = "pipeline",
) -> None:
    """Update or insert status for one job. Creates manifest file if needed."""
    from datetime import datetime
    path = Path(manifest_path)
    df = load_manifest(path)
    now = datetime.utcnow().isoformat() + "Z"
    if df.empty:
        df = pd.DataFrame([{
            "galaxy_id": galaxy_id,
            "frame_id": frame_id,
            "reff": reff,
            "status": status,
            "outname": outname,
            "updated_at": now,
        }])
    else:
        mask = (
            (df["galaxy_id"] == galaxy_id)
            & (df["frame_id"] == frame_id)
            & (df["reff"] == reff)
        )
        if mask.any():
            df.loc[mask, "status"] = status
            df.loc[mask, "updated_at"] = now
        else:
            df = pd.concat([
                df,
                pd.DataFrame([{
                    "galaxy_id": galaxy_id,
                    "frame_id": frame_id,
                    "reff": reff,
                    "status": status,
                    "outname": outname,
                    "updated_at": now,
                }]),
            ], ignore_index=True)
    save_manifest(df, path)


def list_pending_jobs(
    manifest_path: Path, galaxy_id: str
) -> list[tuple]:
    """Return list of (frame_id, reff) for jobs with status pending or failed."""
    df = load_manifest(manifest_path)
    if df.empty:
        return []
    m = (df["galaxy_id"] == galaxy_id) & (
        df["status"].isin([STATUS_PENDING, STATUS_FAILED])
    )
    rows = df[m]
    return [(int(r["frame_id"]), float(r["reff"])) for _, r in rows.iterrows()]
