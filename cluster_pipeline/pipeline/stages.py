"""
Pipeline stage numbering: run only the first N stages via max_stage.
Stages are ordered; each depends on the previous (e.g. matching needs detection output).
"""

# Stage numbers (1-based). Run "up to stage N" = run stages 1, 2, ..., N.
STAGE_INJECTION = 1   # Copy/generate synthetic frame + coords
STAGE_DETECTION = 2   # SExtractor on frame
STAGE_MATCHING = 3    # Match injected vs detected coords; write matched_coords
STAGE_PHOTOMETRY = 4  # IRAF aperture photometry (optional)
STAGE_CATALOGUE = 5   # CI/merr cuts; in_catalogue flag
STAGE_DATASET = 6     # Build final dataset parquet/npy

STAGE_NAMES = {
    STAGE_INJECTION: "injection",
    STAGE_DETECTION: "detection",
    STAGE_MATCHING: "matching",
    STAGE_PHOTOMETRY: "photometry",
    STAGE_CATALOGUE: "catalogue",
    STAGE_DATASET: "dataset",
}

LAST_STAGE = STAGE_DATASET


def run_stage(stage: int, max_stage: int | None) -> bool:
    """
    True if stage should run when pipeline is limited to max_stage.
    If max_stage is None, no limit (caller uses individual run_* flags).
    """
    if max_stage is None:
        return True  # Caller decides via run_injection, run_detection, etc.
    return 1 <= stage <= max_stage
