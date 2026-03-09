# Scripts Index

Where each script lives, what it does, and where to find **inputs/outputs**.

**Full input/output file lists per stage:** see **`docs/PIPELINE_FILES.md`**.  
**How to run and required dirs:** see **`docs/RUNNING.md`**.

---

## Repository layout

| Location | Contents |
|----------|----------|
| **Root** | Config only: README.md, pyproject.toml, pytest.ini, requirements.txt, .gitignore (no Python entry scripts) |
| **`scripts/`** | All entry points and helpers: run_pipeline.py, generate_white_clusters.py, perform_photometry_ci_cut_on_5filters.py, perform_ml_to_learn_completeness.py, nn_utils.py, inject_clusters_to_5filters.py, build_ml_inputs.py, plot_completeness_mag_mass_age.py, extract_white.py, etc. |
| **`cluster_pipeline/`** | Package: config, data, detection, matching, pipeline, photometry, catalogue, dataset, utils |
| **`docs/`** | RUNNING, PIPELINE_FILES, SCRIPTS (this file), FILES_FOR_GIT, DEPLOY, ARCHITECTURE, INSTALL_IRAF, COMPLETENESS_FIGURE |
| **`tests/`** | unit/, integration/, e2e/ |

---

## Scripts by purpose

### Pipeline entry (run from repo root)

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| **`scripts/run_pipeline.py`** | Main entry: Phase A (white injection) + Phase B (detection, matching, optional photometry + catalogue), optional plots | See RUNNING.md; uses `--directory`, galaxy dirs, SExtractor config, etc. | `ngc628-c/white/`, `physprop/`, per-filter dirs; see PIPELINE_FILES.md |
| **`scripts/run_full_with_iraf.sh`** | Wraps `run_pipeline.py` with IRAF env for full photometry run | Same as run_pipeline + IRAF installed | Same + photometry outputs |
| **`scripts/run_stage123_and_plot_diagnostics.py`** | Run stages 1–3 only, then plot completeness vs magnitude | Config + existing or generated synthetic_fits + white_position_*.txt | Match summaries, diagnostics plot |

### White injection and 5-filter

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| **`scripts/generate_white_clusters.py`** | Phase A: SLUG → white synthetic FITS + coords + physprop | SLUG library, PSF, BAOlab, galaxy_filter_dict.npy, science frame, readme | `white/synthetic_fits/*.fits`, `white/white_position_*.txt`, `physprop/*.npy` |
| **`scripts/inject_clusters_to_5filters.py`** | Inject matched clusters onto 5-filter HLSP science images | matched_coords, physprop mag_VEGA, science FITS per filter | `{galaxy}/{filter}/synthetic_fits/*.fits` |
| **`scripts/extract_white.py`** | Legacy white extraction / batch processing | `--directory`, galaxy_names.npy, galaxy_filter_dict.npy, FITS | Various; use `--directory` or COMP_MAIN_DIR |

### ML and plotting

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| **`scripts/build_ml_inputs.py`** | Build det_3d.npy + allprop.npz from pipeline outputs | detection_labels/*.npy, physprop/*.npy | `det_3d.npy`, `allprop.npz` |
| **`scripts/perform_ml_to_learn_completeness.py`** | Train NN for completeness | det_3d.npy, allprop.npz | Best model, scalers, plots under `--out-dir` |
| **`scripts/plot_completeness_mag_mass_age.py`** | Plot completeness vs mag/mass/age (synthetic demo) | Pipeline outputs or mock | PNG/figures |
| **`scripts/perform_photometry_ci_cut_on_5filters.py`** | Standalone photometry + CI reference (optional) | Synthetic FITS, coords, readme | Photometry tables, catalogue |

### Utilities and setup

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| **`scripts/sample_slug_white_mag.py`** | Sample SLUG clusters and compute white-light mag for BAOlab / `--input_coords` | SLUG library, FITS path | Coords file (x y mag or 5-col) |
| **`scripts/setup_env.sh`** | Create venv, install deps, optionally install SExtractor/BAOlab | None | .venv, .deps |
| **`scripts/generate_x11_stubs.py`** | Generate X11 stubs (e.g. for IRAF/PyRAF headless) | None | Stub files |

---

## Where to find input/output details

- **Per-stage file list (all inputs/outputs):** **`docs/PIPELINE_FILES.md`**
- **Required files and run commands:** **`docs/RUNNING.md`**
- **Completeness figure workflow and assumptions:** **`docs/COMPLETENESS_FIGURE.md`** (from `scripts/COMPLETENESS_FIGURE_README.md`)
