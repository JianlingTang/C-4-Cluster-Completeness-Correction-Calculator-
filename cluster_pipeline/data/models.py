"""
Structured data models for the cluster completeness pipeline.
Clear contracts between stages; no implicit formats.
cluster_id is required and propagates through all stages for joins.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SyntheticCluster:
    """One synthetic cluster: physical + photometric properties and position."""

    mass: float
    age: float
    av: float
    radius: float  # Effective radius (pc)
    position: tuple[float, float]  # (x, y) pixel
    cluster_id: int  # Stable ID for joins across pipeline stages
    photometry: list[float] | None = None  # Magnitudes per filter

    def to_injection_row(self, mag_column: int = 2) -> str:
        """Format as one line for BAOlab/IRAF coord file: x y mag."""
        mag = self.photometry[mag_column] if self.photometry else 0.0
        return f"{self.position[0]:.2f} {self.position[1]:.2f} {mag:.4f}\n"


@dataclass
class InjectionResult:
    """Result of injecting clusters into one frame."""

    frame_path: Path
    coord_path: Path
    galaxy_id: str
    frame_id: int
    reff: float
    n_injected: int
    cluster_ids: list[int]  # Order matches injected coord file (row index -> cluster_id)


@dataclass
class DetectionResult:
    """Result of running SExtractor on one frame."""

    catalog_path: Path
    coord_path: Path  # .coo file (x y) for matching
    n_detected: int
    frame_path: Path


@dataclass
class MatchResult:
    """Result of matching injected coordinates to detected coordinates."""

    injected_path: Path
    detected_path: Path
    cluster_ids: list[int]  # Full list of cluster_id per injected row (same order as coords)
    matched_indices: list[int]  # Indices into injected list that have a match
    matched_positions: list[tuple[float, float]]  # Detected (x,y) for each matched
    n_injected: int
    n_matched: int
    tolerance_pix: float

    def get_matched_cluster_ids(self) -> list[int]:
        """Cluster IDs that were matched (in order of matched_positions)."""
        return [self.cluster_ids[i] for i in self.matched_indices]

    @property
    def detection_labels(self) -> list[int]:
        """Binary label per injected cluster: 1 if matched, 0 otherwise."""
        labels = [0] * self.n_injected
        for i in self.matched_indices:
            labels[i] = 1
        return labels

    def detection_label_by_cluster_id(self) -> dict:
        """Map cluster_id -> 0 or 1."""
        return {cid: (1 if i in self.matched_indices else 0) for i, cid in enumerate(self.cluster_ids)}


@dataclass
class DetectionLabelRecord:
    """One record for ML dataset: one cluster in one frame at one reff."""

    cluster_id: int
    frame_id: int
    reff_id: int
    reff: float
    detected: int  # 0 or 1
    galaxy_id: str
