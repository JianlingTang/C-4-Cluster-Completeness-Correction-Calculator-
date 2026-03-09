"""
Pure-Python parser for IRAF daophot .mag files.

Replaces the ``iraf.txdump`` call in ci_filter.py so that
post-processing of .mag outputs no longer requires pyraf.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?|INDEF")


def parse_mag_coords(mag_path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Extract XCENTER and YCENTER from an IRAF .mag file.

    The .mag format stores results as multi-line records separated by
    blank lines.  Inside each record the XCENTER and YCENTER fields
    appear on a line that looks like::

        123.456  789.012  ...

    after the header keyword line containing ``XCENTER``.  This parser
    locates those lines and returns two 1-D float arrays.
    """
    mag_path = Path(mag_path)
    xs: list[float] = []
    ys: list[float] = []

    lines = mag_path.read_text().splitlines()
    for i, line in enumerate(lines):
        if "XCENTER" in line and "YCENTER" in line:
            if i + 1 < len(lines):
                vals = _FLOAT_RE.findall(lines[i + 1])
                if len(vals) >= 2:
                    x = float(vals[0]) if vals[0] != "INDEF" else np.nan
                    y = float(vals[1]) if vals[1] != "INDEF" else np.nan
                    xs.append(x)
                    ys.append(y)

    return np.array(xs), np.array(ys)
