# cluster_pipeline

Modular scientific pipeline for cluster completeness modeling. See project root **ARCHITECTURE.md** for full design.

## Layout

- **config** — `PipelineConfig`, `get_config()` (env + overrides)
- **data** — Data models (`SyntheticCluster`, `MatchResult`, …), galaxy metadata, cluster library loader
- **simulation** — (Stub) Cluster sampling, radius models, photometry
- **injection** — (Stub) BAOlab frame injector
- **detection** — `SExtractorRunner`, `run_sextractor()`
- **matching** — `CoordinateMatcher`, `match_coordinates()`
- **dataset** — (Stub) Detection dataset builder for ML
- **pipeline** — `run_galaxy_pipeline`, `run_ast_pipeline`, `run_frame_pipeline`; manifest (job state)
- **utils** — `ensure_dir`, `safe_remove_tree`, `temporary_directory`, `get_logger`, `setup_logging`

## Usage

```python
from pathlib import Path
from cluster_pipeline.config import get_config
from cluster_pipeline.matching import CoordinateMatcher, match_coordinates
from cluster_pipeline.detection import SExtractorRunner
from cluster_pipeline.pipeline import run_galaxy_pipeline

# Config (env or overrides)
config = get_config(overrides={"main_dir": "/data/pipeline"})

# Match injected vs detected coordinates
matcher = CoordinateMatcher(tolerance_pix=3.0)
result = matcher.match(Path("injected.txt"), Path("detected.coo"))

# Run full pipeline for one galaxy (injection → detection → match → cleanup)
run_galaxy_pipeline("ngc628-c_white-R17v100", config=config, keep_frames=False)
```

## Requirements

- Python 3.9+
- numpy, scipy, astropy, pandas, pyarrow, matplotlib (core)
- SExtractor (`sex`) for detection (stage 2)
- BAOlab (`bl`) for injection (stage 1)
- pyraf: **optional**, only needed for stage 4 (IRAF daophot aperture photometry)

**Note:** slugpy is NOT required. SLUG library FITS files are read directly by the built-in `cluster_pipeline.data.slug_reader` (pure Python, no C extensions, no GSL).

One-command install: `make setup` (or `bash scripts/setup_env.sh`)
