"""
Photometry stage: aperture photometry on detected coordinates (all filters), CI computation.
Uses IRAF/daophot. I/O isolated; no os.chdir in this module.
"""
from .aperture_photometry import AperturePhotometryRunner, run_aperture_photometry
from .ci_filter import CIFilter, apply_ci_cut

__all__ = [
    "run_aperture_photometry",
    "AperturePhotometryRunner",
    "apply_ci_cut",
    "CIFilter",
]
