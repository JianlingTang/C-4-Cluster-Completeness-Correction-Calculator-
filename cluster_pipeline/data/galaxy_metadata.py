"""
Galaxy metadata: filters, zeropoints, FITS paths. Load from main_dir + galaxy_id.
Aperture radius, distance modulus, and CI cut follow perform_photometry_ci_cut_on_5filters.py
(readme when present).
"""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _read_aperture_from_readme(gal_dir: Path, gal_short: str) -> float | None:
    """Read aperture radius from readme (same pattern as perform_photometry_ci_cut_on_5filters.py)."""
    readmes = list(gal_dir.glob(f"automatic_catalog*_{gal_short}.readme"))
    if not readmes:
        return None
    try:
        content = readmes[0].read_text()
    except Exception:
        return None
    m = re.search(r"The aperture radius used for photometry is (\d+(\.\d+)?)\.", content)
    return float(m.group(1)) if m else None


def _read_dmod_and_ci_from_readme(gal_dir: Path, gal_short: str) -> tuple:
    """Read distance modulus (mag) and CI cut from readme; return (dmod, ci) or (None, None)."""
    readmes = list(gal_dir.glob(f"automatic_catalog*_{gal_short}.readme"))
    if not readmes:
        return None, None
    try:
        content = readmes[0].read_text()
    except Exception:
        return None, None
    dmod, ci = None, None
    m = re.search(
        r"Distance modulus used (\d+\.\d+) mag \((\d+\.\d+) Mpc\)", content
    )
    if m:
        dmod = float(m.group(1))
    m = re.search(
        r"This catalogue contains only sources with CI[ ]*>=[ ]*(\d+(\.\d+)?)\.", content
    )
    if m:
        ci = float(m.group(1))
    return dmod, ci


@dataclass
class GalaxyMetadata:
    """Metadata for one galaxy: filters, zeropoints, instrument, paths to science FITS."""

    galaxy_id: str
    filters: list[str]
    zeropoints: dict[str, float]
    instrument: dict[str, str]  # filter -> instrument name
    fits_paths: dict[str, Path]  # filter -> path to drc/sci FITS
    readme_path: Path | None = None
    header_info_path: Path | None = None
    aperture_radius: float | None = None
    distance_modulus: float | None = None
    ci_cut: float | None = None

    @classmethod
    def load(cls, main_dir: Path, galaxy_id: str) -> "GalaxyMetadata":
        """Load galaxy metadata from main_dir/galaxy_id (galaxy_filter_dict, header_info, readme)."""
        gal_dir = main_dir / galaxy_id
        gal_short = galaxy_id.split("_")[0]
        gal_filters = np.load(
            main_dir / "galaxy_filter_dict.npy", allow_pickle=True
        ).item()
        filters_list, instruments = gal_filters.get(gal_short, ([], []))
        filters = sorted(filters_list) if filters_list else []
        zp_path = gal_dir / f"header_info_{gal_short}.txt"
        zeropoints: dict[str, float] = {}
        instrument_map: dict[str, str] = {}
        if zp_path.exists():
            data = np.loadtxt(zp_path, unpack=True, skiprows=0, usecols=(0, 1, 2), dtype="str")
            if data.size > 0:
                filts, inst, zp = data[0], data[1], data[2]
                for f, i, z in zip(np.atleast_1d(filts), np.atleast_1d(inst), np.atleast_1d(zp)):
                    zeropoints[str(f)] = float(z)
                    instrument_map[str(f)] = str(i)
        fits_paths: dict[str, Path] = {}
        for f in filters:
            matches = list(gal_dir.glob(f"*{f}*drc.fits"))
            if not matches:
                matches = list(gal_dir.glob(f"*{f}*sci.fits"))
            if matches:
                fits_paths[f] = matches[0].resolve()
        ap = _read_aperture_from_readme(gal_dir, gal_short)
        dmod, ci = _read_dmod_and_ci_from_readme(gal_dir, gal_short)
        readme_path = None
        readmes = list(gal_dir.glob(f"automatic_catalog*_{gal_short}.readme"))
        if readmes:
            readme_path = readmes[0]
        return cls(
            galaxy_id=galaxy_id,
            filters=filters,
            zeropoints=zeropoints,
            instrument=instrument_map,
            fits_paths=fits_paths,
            header_info_path=zp_path if zp_path.exists() else None,
            readme_path=readme_path,
            aperture_radius=ap,
            distance_modulus=dmod,
            ci_cut=ci,
        )
