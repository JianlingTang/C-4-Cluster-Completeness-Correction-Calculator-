"""
Pipeline configuration: single source of truth for paths, sampling, matching, and detection.
No hardcoded paths in pipeline code; load from defaults + env + optional YAML.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    """
    All configurable parameters for the cluster completeness pipeline.
    Paths are absolute or relative to a configured root; pipeline uses pathlib.
    """

    # ---- Paths (str or Path; normalized to Path in helpers) ----
    main_dir: Path
    fits_path: Path
    psf_path: Path
    bao_path: Path
    slug_lib_dir: Path
    output_lib_dir: Path
    temp_base_dir: Path  # Base for ephemeral frame/catalog dirs
    make_LEGUS_CCT_dir: Path | None = None

    # ---- Sampling / simulation ----
    ncl: int = 500
    nframe: int = 50
    reff_list: list[float] = field(default_factory=lambda: [float(r) for r in range(1, 11)])
    mrmodel: str = "flat"
    dmod: float = 29.98
    M_LIMIT: float = 15.0  # Brightness cutoff (mag) for cluster sampling

    # ---- Matching ----
    thres_coord: float = 3.0  # Pixel tolerance for KD-tree match

    # ---- Detection (SExtractor) ----
    sextractor_config_path: Path | None = None
    sextractor_param_path: Path | None = None
    sextractor_nnw_path: Path | None = None

    # ---- Instrument constants ----
    pixscale_wfc3: float = 0.04
    pixscale_acs: float = 0.05
    sigma_pc: float = 100.0
    merr_cut: float = 0.3

    # ---- Optional ----
    validation: bool = False
    overwrite: bool = False
    """When set, before photometry the pipeline writes per-filter coords from matched+physprop and runs this script to inject matched clusters onto HLSP science images (see scripts/inject_clusters_to_5filters.py)."""
    inject_5filter_script: Path | None = None

    def galaxy_dir(self, galaxy_id: str) -> Path:
        return self.main_dir / galaxy_id

    def white_dir(self, galaxy_id: str) -> Path:
        return self.galaxy_dir(galaxy_id) / "white"

    def synthetic_fits_dir(self, galaxy_id: str) -> Path:
        return self.white_dir(galaxy_id) / "synthetic_fits"

    def s_extraction_dir(self, galaxy_id: str) -> Path:
        return self.white_dir(galaxy_id) / "s_extraction"

    def matched_coords_dir(self, galaxy_id: str) -> Path:
        return self.white_dir(galaxy_id) / "matched_coords"

    def diagnostics_dir(self, galaxy_id: str) -> Path:
        """Directory for per-run diagnostics (e.g. match summary tables for completeness plot)."""
        return self.white_dir(galaxy_id) / "diagnostics"

    def detection_labels_dir(self, galaxy_id: str) -> Path:
        """Directory for binary detection labels (0/1 per cluster, aligned with cluster_id order)."""
        return self.white_dir(galaxy_id) / "detection_labels"

    def filter_synthetic_fits_dir(self, galaxy_id: str, filter_name: str) -> Path:
        """Per-filter synthetic FITS dir (e.g. galaxy/ACS_F435W/synthetic_fits) for photometry."""
        return self.galaxy_dir(galaxy_id) / filter_name / "synthetic_fits"

    def photometry_dir(self, galaxy_id: str, filter_name: str) -> Path:
        """Per-filter photometry output dir (mag_*.txt, ci_cut_*.coo)."""
        return self.galaxy_dir(galaxy_id) / filter_name / "photometry"

    def catalogue_dir(self, galaxy_id: str) -> Path:
        """Directory for catalogue parquet (in_catalogue) and photometry parquet."""
        return self.white_dir(galaxy_id) / "catalogue"

    def physprop_dir(self) -> Path:
        return self.main_dir / "physprop"

    def temp_dir_for(self, galaxy_id: str, frame_id: int, reff: float) -> Path:
        """Unique temp dir for one (galaxy, frame, reff) for ephemeral frame + detection."""
        return self.temp_base_dir / f"{galaxy_id}_frame{frame_id}_reff{reff}"


def _p(path: str) -> Path:
    return Path(path).resolve()


def get_config(overrides: dict | None = None) -> PipelineConfig:
    """
    Build PipelineConfig from defaults, then env, then overrides.
    Env keys: COMP_MAIN_DIR, COMP_FITS_PATH, COMP_PSF_PATH, COMP_BAO_PATH,
    COMP_SLUG_LIB_DIR, COMP_OUTPUT_LIB_DIR, COMP_TEMP_BASE_DIR.
    """
    def _path(key: str, default: str) -> Path:
        return _p(os.environ.get(key, default))

    main_dir = _path("COMP_MAIN_DIR", "/g/data/jh2/jt4478/make_LC_copy")
    fits_path = _path("COMP_FITS_PATH", str(main_dir))
    psf_path = _path("COMP_PSF_PATH", "/g/data/jh2/jt4478/PSF_all")
    bao_path = _path("COMP_BAO_PATH", "/g/data/jh2/jt4478/baolab-0.94.1g")
    slug_lib_dir = _path("COMP_SLUG_LIB_DIR", "/g/data/jh2/jt4478/cluster_slug")
    output_lib_dir = _path("COMP_OUTPUT_LIB_DIR", "/g/data/jh2/jt4478/output_lib")
    temp_base_dir = _path("COMP_TEMP_BASE_DIR", "/tmp/cluster_pipeline")
    make_LEGUS_CCT_dir = os.environ.get("COMP_MAKE_LEGUS_CCT_DIR")
    if make_LEGUS_CCT_dir:
        make_LEGUS_CCT_dir = _p(make_LEGUS_CCT_dir)

    cfg = PipelineConfig(
        main_dir=main_dir,
        fits_path=fits_path,
        psf_path=psf_path,
        bao_path=bao_path,
        slug_lib_dir=slug_lib_dir,
        output_lib_dir=output_lib_dir,
        temp_base_dir=temp_base_dir,
        make_LEGUS_CCT_dir=make_LEGUS_CCT_dir,
    )
    if overrides:
        cfg = _apply_overrides(cfg, overrides)
    return cfg


def _apply_overrides(cfg: PipelineConfig, overrides: dict) -> PipelineConfig:
    """Return a new config with overrides applied (only simple/Path fields)."""
    d = {
        "main_dir": cfg.main_dir, "fits_path": cfg.fits_path, "psf_path": cfg.psf_path,
        "bao_path": cfg.bao_path, "slug_lib_dir": cfg.slug_lib_dir,
        "output_lib_dir": cfg.output_lib_dir, "temp_base_dir": cfg.temp_base_dir,
        "make_LEGUS_CCT_dir": cfg.make_LEGUS_CCT_dir,
        "ncl": cfg.ncl, "nframe": cfg.nframe, "reff_list": list(cfg.reff_list),
        "mrmodel": cfg.mrmodel, "dmod": cfg.dmod, "M_LIMIT": cfg.M_LIMIT,
        "thres_coord": cfg.thres_coord, "validation": cfg.validation, "overwrite": cfg.overwrite,
        "inject_5filter_script": cfg.inject_5filter_script,
        "sextractor_config_path": cfg.sextractor_config_path,
        "sextractor_param_path": cfg.sextractor_param_path,
        "sextractor_nnw_path": cfg.sextractor_nnw_path,
        "pixscale_wfc3": cfg.pixscale_wfc3, "pixscale_acs": cfg.pixscale_acs,
        "sigma_pc": cfg.sigma_pc, "merr_cut": cfg.merr_cut,
    }
    for k, v in overrides.items():
        if k in d:
            if k in ("main_dir", "fits_path", "psf_path", "bao_path", "slug_lib_dir",
                     "output_lib_dir", "temp_base_dir", "make_LEGUS_CCT_dir") and v is not None:
                d[k] = _p(str(v))
            elif k == "inject_5filter_script" and v is not None:
                d[k] = _p(str(v))
            else:
                d[k] = v
    return PipelineConfig(**d)
