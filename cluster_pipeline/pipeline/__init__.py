"""Pipeline orchestration."""

from .ast_pipeline import run_ast_pipeline, run_frame_pipeline
from .diagnostics import load_match_summaries, plot_completeness_diagnostics
from .pipeline_runner import run_galaxy_pipeline
from .stages import (
    STAGE_CATALOGUE,
    STAGE_DATASET,
    STAGE_DETECTION,
    STAGE_INJECTION,
    STAGE_MATCHING,
    STAGE_NAMES,
    STAGE_PHOTOMETRY,
    run_stage,
)

__all__ = [
    "run_galaxy_pipeline",
    "run_ast_pipeline",
    "run_frame_pipeline",
    "plot_completeness_diagnostics",
    "load_match_summaries",
    "STAGE_INJECTION",
    "STAGE_DETECTION",
    "STAGE_MATCHING",
    "STAGE_PHOTOMETRY",
    "STAGE_CATALOGUE",
    "STAGE_DATASET",
    "STAGE_NAMES",
    "run_stage",
]
