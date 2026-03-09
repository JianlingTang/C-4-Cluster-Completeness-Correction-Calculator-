"""
Concentration Index (CI) cut: CI = mag(1px) - mag(3px). Applied only on V-band (F555W).
Sources with CI >= threshold are retained. Source of truth: perform_photometry_ci_cut_on_5filters.py.
"""
from pathlib import Path

import numpy as np


def apply_ci_cut(
    mag_txt_path: Path,
    ci_threshold: float,
    merr_cut: float = 0.3,
    filter_is_vband: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Parse mag_*.txt (aper, _, _, _, mag, merr), compute CI = mag_1px - mag_3px,
    apply merr cut and (if V-band) CI >= threshold.

    Parameters
    ----------
    mag_txt_path : Path
        Output from aperture photometry (e.g. mag_*.txt).
    ci_threshold : float
        Minimum CI to retain (e.g. 1.4 from readme).
    merr_cut : float
        Maximum magnitude error to retain.
    filter_is_vband : bool
        If True, apply CI cut; if False, only merr cut.

    Returns
    -------
    (mag_4, merr_4, ci_values), (passes_ci, passes_merr, keep)
        mag_4/user aperture mag and merr_4; ci_values = mag_1px - mag_3px; keep = passes_merr & (passes_ci if V-band).
    """
    data = np.loadtxt(mag_txt_path, unpack=True, skiprows=0, usecols=(0, 1, 2, 3, 4, 5), dtype="str")
    aper, _, _, _, mag, merr = data
    id_1 = np.where(aper == "1.00")
    mag_1 = np.asarray(list(map(float, mag[id_1])))
    id_3 = np.where(aper == "3.00")
    mag_3 = np.asarray(list(map(float, mag[id_3])))
    ci_values = np.subtract(mag_1, mag_3)  # CI = mag(1px) - mag(3px), same as perform_photometry_ci_cut_on_5filters.py
    user_ap = "3.00"
    id_ap = np.where(aper == user_ap)
    mag_4 = np.asarray(list(map(float, mag[id_ap])))
    merr_4 = np.asarray(list(map(float, merr[id_ap])))
    passes_merr = merr_4 <= merr_cut
    if filter_is_vband:
        passes_ci = ci_values >= ci_threshold
        keep = passes_merr & passes_ci
    else:
        passes_ci = np.ones_like(passes_merr, dtype=bool)
        keep = passes_merr
    return (mag_4, merr_4, ci_values), (passes_ci, passes_merr, keep)


def build_ci_cut_coo_file(
    mag_txt_path: Path,
    mag_raw_path: Path,
    coords_path: Path,
    ci_threshold: float,
    merr_cut: float,
    output_path: Path,
    filter_is_vband: bool = True,
) -> None:
    """
    Write ci_cut_*.coo file: x y mag merr ci for sources passing CI (and merr) cut.
    Coordinates come from coords_path (same order as mag file rows after grep "*").
    """
    from ..utils.mag_parser import parse_mag_coords

    data = np.loadtxt(mag_txt_path, unpack=True, skiprows=0, usecols=(0, 1, 2, 3, 4, 5), dtype="str")
    aper, _, _, _, mag, merr = data
    id_1 = np.where(aper == "1.00")[0]
    id_3 = np.where(aper == "3.00")[0]
    mag_1 = np.asarray(list(map(float, mag[id_1])))
    mag_3 = np.asarray(list(map(float, mag[id_3])))
    ci_values = mag_1 - mag_3  # CI = mag(1px) - mag(3px), same as perform_photometry_ci_cut_on_5filters.py
    user_ap = "3.00"
    id_ap = np.where(aper == user_ap)[0]
    mag_4 = np.asarray(list(map(float, mag[id_ap])))
    merr_4 = np.asarray(list(map(float, merr[id_ap])))
    passes_merr = merr_4 <= merr_cut
    if filter_is_vband:
        keep = passes_merr & (ci_values >= ci_threshold)
    else:
        keep = passes_merr

    xc, yc = parse_mag_coords(mag_raw_path)
    xc = np.atleast_1d(xc).astype(str)
    yc = np.atleast_1d(yc).astype(str)
    if len(xc) != len(mag_4):
        xc = np.resize(xc, len(mag_4))
        yc = np.resize(yc, len(mag_4))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for k in np.where(keep)[0]:
            f.write(f"{xc[k]}  {yc[k]} {mag_4[k]} {merr_4[k]} {ci_values[k]}\n")


class CIFilter:
    """CI cut with configurable threshold and merr_cut."""

    def __init__(self, ci_threshold: float, merr_cut: float = 0.3):
        self.ci_threshold = ci_threshold
        self.merr_cut = merr_cut

    def apply(
        self,
        mag_txt_path: Path,
        filter_is_vband: bool = True,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return apply_ci_cut(
            mag_txt_path,
            ci_threshold=self.ci_threshold,
            merr_cut=self.merr_cut,
            filter_is_vband=filter_is_vband,
        )
