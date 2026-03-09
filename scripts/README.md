# Scripts

Runnable scripts for the cluster completeness pipeline. All paths assume you are in the **repo root** when running (e.g. `python scripts/run_small_test.py`).

## Quick reference

| Script | Purpose |
|--------|---------|
| **run_small_test.py** | Main entry: Phase A + Phase B (detection, matching, optional photometry), optional plots |
| **run_full_with_iraf.sh** | Same as above with IRAF env for full 5-filter photometry |
| **run_stage123_and_plot_diagnostics.py** | Run stages 1–3 only, then plot completeness vs magnitude |
| **inject_clusters_to_5filters.py** | Inject matched clusters onto 5-filter HLSP images (called by pipeline when `run_photometry`) |
| **build_ml_inputs.py** | Build `det_3d.npy` and `allprop.npz` from pipeline outputs for NN training |
| **plot_completeness_mag_mass_age.py** | Plot completeness vs mag/mass/age |
| **sample_slug_white_mag.py** | Sample SLUG and compute white-light mag for `--input_coords` |
| **extract_white.py** | Legacy white extraction / batch processing |
| **setup_env.sh** | Create venv, install deps, optional SExtractor/BAOlab install |
| **generate_x11_stubs.py** | X11 stubs for IRAF/PyRAF headless |

## Inputs and outputs

- **Full list of files per stage:** see **`docs/PIPELINE_FILES.md`**.
- **Script index with inputs/outputs:** see **`docs/SCRIPTS.md`**.
- **How to run and required dirs:** see **`docs/RUNNING.md`**.

## Root-level entry points (not in `scripts/`)

- **`generate_white_clusters.py`** – Phase A white injection (SLUG → synthetic FITS + physprop). Called by `run_small_test.py`.
- **`perform_photometry_ci_cut_on_5filters.py`** – Standalone photometry + CI reference.
- **`perform_ml_to_learn_completeness.py`** – NN training (uses `det_3d.npy`, `allprop.npz` from `build_ml_inputs.py`).
