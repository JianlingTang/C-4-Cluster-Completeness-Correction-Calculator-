"""
Pure-astropy replacements for IRAF imarith operations.

Drop-in replacements for safe_imarith_div, safe_imarith_div_to,
and safe_imarith_add_to so that generate_white_clusters.py no longer
requires pyraf for FITS arithmetic.
"""
from __future__ import annotations

import os
from pathlib import Path

from astropy.io import fits


def fits_div(in_path: str | Path, factor: float, out_path: str | Path | None = None) -> None:
    """Divide a FITS image by *factor* (scalar), write atomically.

    If *out_path* is None the input file is overwritten in-place.
    """
    in_path = str(in_path)
    out_path = str(out_path) if out_path is not None else in_path

    base, ext = os.path.splitext(out_path)
    tmp = base + "_tmp" + ext

    with fits.open(in_path) as hdul:
        hdul[0].data = hdul[0].data / factor
        hdul.writeto(tmp, overwrite=True)
    os.replace(tmp, out_path)


def fits_add(img1: str | Path, img2: str | Path, out_path: str | Path) -> None:
    """Add two FITS images pixel-by-pixel, write atomically."""
    img1, img2, out_path = str(img1), str(img2), str(out_path)

    base, ext = os.path.splitext(out_path)
    tmp = base + "_tmp" + ext

    with fits.open(img1) as h1, fits.open(img2) as h2:
        h1[0].data = h1[0].data + h2[0].data
        h1.writeto(tmp, overwrite=True)
    os.replace(tmp, out_path)
