"""
AST (Artificial Star Test) pipeline: frame-level and galaxy-level orchestration.
Runs: sampling -> injection -> detection -> matching -> photometry -> catalogue -> dataset.
Supports parallel execution per frame; manifest tracks job state; intermediate parquet.

Stages (use max_stage to run only the first N):
  1 = injection    copy/generate synthetic frame + coords
  2 = detection    SExtractor on frame
  3 = matching    match injected vs detected coords; write matched_coords
  4 = photometry
  5 = catalogue   CI/merr; in_catalogue
  6 = dataset     build final dataset parquet/npy
"""

from ..config import PipelineConfig, get_config
from ..detection import SExtractorRunner
from ..matching import CoordinateMatcher, load_coords
from ..utils.filesystem import ensure_dir, safe_remove_tree
from ..utils.logging_utils import get_logger
from .diagnostics import write_match_summary
from .manifest import (
    STATUS_CATALOGUE_DONE,
    STATUS_DATASET_DONE,
    STATUS_DETECTION_DONE,
    STATUS_FAILED,
    STATUS_INJECTION_DONE,
    STATUS_MATCHING_DONE,
    STATUS_PHOTOMETRY_DONE,
    manifest_path,
    set_job_status,
)
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

logger = get_logger(__name__)


def run_frame_pipeline(
    galaxy_id: str,
    frame_id: int,
    reff: float,
    config: PipelineConfig,
    *,
    outname: str = "pipeline",
    max_stage: int | None = None,
    run_sampling: bool = True,
    run_injection: bool = True,
    run_detection: bool = True,
    run_matching: bool = True,
    run_photometry: bool = False,
    run_catalogue: bool = False,
    run_dataset_append: bool = False,
    keep_frames: bool = False,
    cluster_ids: list[int] | None = None,
) -> None:
    """
    Run the full pipeline for one (galaxy_id, frame_id, reff): sampling -> injection -> detection
    -> matching -> [photometry -> catalogue -> dataset row]. Writes intermediate parquet; updates
    manifest; deletes temp frame if keep_frames is False.

    Parameters
    ----------
    galaxy_id, frame_id, reff : str, int, float
        Job identifier.
    config : PipelineConfig
        Pipeline config.
    outname : str
        Run name for filenames.
    run_* : bool
        Which stages to run.
    keep_frames : bool
        If False, synthetic frame is deleted after detection + matching.
    cluster_ids : list of int, optional
        If provided (e.g. from sampling), used for match result; else range(n_injected).
    max_stage : int, optional
        If set, run only stages 1..max_stage (e.g. max_stage=2 → injection + detection).
    """
    if max_stage is not None:
        run_injection = run_stage(STAGE_INJECTION, max_stage)
        run_detection = run_stage(STAGE_DETECTION, max_stage)
        run_matching = run_stage(STAGE_MATCHING, max_stage)
        run_photometry = run_stage(STAGE_PHOTOMETRY, max_stage)
        run_catalogue = run_stage(STAGE_CATALOGUE, max_stage)
        run_dataset_append = run_stage(STAGE_DATASET, max_stage)

    temp_dir = config.temp_dir_for(galaxy_id, frame_id, reff)
    manifest_file = manifest_path(config.main_dir, galaxy_id, outname)
    ensure_dir(config.temp_base_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Placeholder: sampling would produce SyntheticCluster list with cluster_id
        # Injection would write frame + coords and InjectionResult with cluster_ids
        frame_path = temp_dir / "injected.fits"
        coord_path = temp_dir / "injected_coords.txt"
        if run_injection:
            synthetic_fits = config.synthetic_fits_dir(galaxy_id)
            white_dir = config.white_dir(galaxy_id)
            frame_pattern = f"*_frame{frame_id}_{outname}_reff{reff:.2f}.fits"
            coord_name = f"white_position_{frame_id}_{outname}_reff{reff:.2f}.txt"
            existing_frames = list(synthetic_fits.glob(frame_pattern))
            existing_coord = white_dir / coord_name
            if existing_frames and existing_coord.exists():
                import shutil
                shutil.copy(existing_frames[0], frame_path)
                shutil.copy(existing_coord, coord_path)
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_INJECTION_DONE, outname)
        if not frame_path.exists() or not coord_path.exists():
            logger.warning("Skipping frame_id=%s reff=%s: missing frame or coords", frame_id, reff)
            return

        matcher = CoordinateMatcher(tolerance_pix=config.thres_coord)
        sextractor = SExtractorRunner(config)

        if run_detection:
            det = sextractor.run(
                frame_path=frame_path,
                output_dir=temp_dir,
                catalog_name=f"det_frame{frame_id}_reff{reff:.2f}.cat",
                coo_suffix=".coo",
            )
            logger.info("Detection frame_id=%s reff=%s n_detected=%s", frame_id, reff, det.n_detected)
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_DETECTION_DONE, outname)
        else:
            coo_path = temp_dir / f"{frame_path.stem}.coo"
            if not coo_path.exists():
                logger.warning("No detection run and no .coo file; skipping match")
                return
            from ..data.models import DetectionResult
            det = DetectionResult(
                catalog_path=temp_dir / "det.cat",
                coord_path=coo_path,
                n_detected=0,
                frame_path=frame_path,
            )

        if run_matching:
            injected = load_coords(coord_path)
            n_injected = len(injected)
            cids = cluster_ids if cluster_ids is not None else list(range(n_injected))
            match_result = matcher.match(coord_path, det.coord_path, cluster_ids=cids)
            logger.info(
                "Match frame_id=%s reff=%s n_matched=%s/%s",
                frame_id, reff, match_result.n_matched, match_result.n_injected,
            )
            out_matched = config.matched_coords_dir(galaxy_id) / (
                f"matched_frame{frame_id}_{outname}_reff{reff:.2f}.txt"
            )
            ensure_dir(out_matched.parent)
            matcher.write_matched_coords(match_result, out_matched, det.coord_path)
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_MATCHING_DONE, outname)
            # Write (mag, matched) per source for completeness diagnostics
            diag_dir = config.diagnostics_dir(galaxy_id)
            summary_path = diag_dir / f"match_summary_frame{frame_id}_reff{reff:.2f}_{outname}.txt"
            write_match_summary(coord_path, match_result, summary_path)
            # TODO: append match result to galaxy-level match parquet (cluster_id joins)
        if run_photometry:
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_PHOTOMETRY_DONE, outname)
        if run_catalogue:
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_CATALOGUE_DONE, outname)
        if run_dataset_append:
            set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_DATASET_DONE, outname)
    except Exception as e:
        logger.exception("Failed galaxy=%s frame=%s reff=%s: %s", galaxy_id, frame_id, reff, e)
        set_job_status(manifest_file, galaxy_id, frame_id, reff, STATUS_FAILED, outname)
        raise
    finally:
        if not keep_frames and temp_dir.exists():
            safe_remove_tree(temp_dir)
            logger.debug("Removed temp dir %s", temp_dir)


def run_ast_pipeline(
    galaxy: str,
    frames: int | None = None,
    clusters_per_frame: int | None = None,
    reff_grid: list[float] | None = None,
    config: PipelineConfig | None = None,
    *,
    outname: str = "pipeline",
    max_stage: int | None = None,
    run_injection: bool = True,
    run_detection: bool = True,
    run_matching: bool = True,
    run_photometry: bool = False,
    run_catalogue: bool = False,
    keep_frames: bool = False,
    parallel: bool = True,
    n_workers: int | None = None,
) -> None:
    """
    Galaxy-level orchestrator: run frame-level pipeline for each (frame_id, reff).

    Stages: 1=injection, 2=detection, 3=matching, 4=photometry, 5=catalogue, 6=dataset.
    Use max_stage to run only the first N stages (e.g. max_stage=2 → injection + detection).
    """
    cfg = config or get_config()
    nframe = frames if frames is not None else cfg.nframe
    reff_list = reff_grid if reff_grid is not None else list(cfg.reff_list)
    if max_stage is not None:
        logger.info(
            "AST pipeline galaxy=%s max_stage=%s (stages: %s)",
            galaxy, max_stage,
            [STAGE_NAMES[s] for s in range(1, max_stage + 1) if s in STAGE_NAMES],
        )
    logger.info(
        "Starting AST pipeline galaxy=%s frames=%s reff_list=%s",
        galaxy, nframe, reff_list,
    )
    jobs = [(galaxy, frame_id, reff) for frame_id in range(nframe) for reff in reff_list]
    if parallel and len(jobs) > 1:
        import multiprocessing as mp
        workers = n_workers or min(len(jobs), max(1, mp.cpu_count() - 1))
        with mp.Pool(workers) as pool:
            pool.map(_run_frame_job, [(g, f, r, cfg, dict(outname=outname, max_stage=max_stage, run_injection=run_injection, run_detection=run_detection, run_matching=run_matching, run_photometry=run_photometry, run_catalogue=run_catalogue, keep_frames=keep_frames)) for (g, f, r) in jobs])
    else:
        for (g, f, r) in jobs:
            run_frame_pipeline(
                g, f, r, cfg,
                outname=outname,
                max_stage=max_stage,
                run_injection=run_injection,
                run_detection=run_detection,
                run_matching=run_matching,
                run_photometry=run_photometry,
                run_catalogue=run_catalogue,
                keep_frames=keep_frames,
            )
    logger.info("AST pipeline finished for galaxy=%s", galaxy)


def _run_frame_job(args: tuple) -> None:
    """Worker for parallel AST: (galaxy_id, frame_id, reff, config, kwargs)."""
    (galaxy_id, frame_id, reff, config, kwargs) = args
    run_frame_pipeline(galaxy_id, frame_id, reff, config, **kwargs)
