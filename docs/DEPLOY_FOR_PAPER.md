# Code to Include for Paper / GitHub Deployment

This document lists the code needed to run the **completeness pipeline** (synthetic injection → detection → matching → 5-filter photometry → CI cut) and the final **NN training** step (`scripts/perform_ml_to_learn_completeness.py`).

---

## 1. Pipeline (stages 1–5)

**Entry point:** `scripts/run_small_test.py`  
- Orchestrates: cleanup → Phase A (injection) → Phase B (detection, matching, optional 5-filter inject + photometry + catalogue) → optional completeness plots.

### 1.1 Phase A – White-light injection

| Include | Purpose |
|--------|---------|
| `scripts/generate_white_clusters.py` | Injects synthetic clusters on white-light image; writes coord files, synthetic FITS, physprop .npy. |
| `cluster_pipeline/data/slug_reader.py` | Reads SLUG library (mass, age, photometry). |
| `cluster_pipeline/data/cluster_library.py` | Cluster library interface. |
| `cluster_pipeline/data/slug_library_loader.py` | SLUG library loading. |

**External:** BAOlab binary (e.g. under `.deps/local/bin`), PSF files, SLUG library dir, galaxy FITS and `galaxy_filter_dict.npy`, `header_info_*.txt`.

### 1.2 Phase B – Detection, matching, photometry, catalogue

| Include | Purpose |
|--------|---------|
| **Config & data** | |
| `cluster_pipeline/config/` | `pipeline_config.py`, `__init__.py` – paths, nframe, reff_list, etc. |
| `cluster_pipeline/data/models.py` | `DetectionResult`, `MatchResult`. |
| `cluster_pipeline/data/schemas.py` | Parquet column schemas. |
| `cluster_pipeline/data/galaxy_metadata.py` | Zeropoints, aperture, CI from readme. |
| **Detection** | |
| `cluster_pipeline/detection/sextractor_runner.py` | Runs SExtractor on synthetic FITS. |
| `cluster_pipeline/detection/__init__.py` | |
| **Matching** | |
| `cluster_pipeline/matching/coordinate_matcher.py` | Matches injected vs detected coordinates. |
| `cluster_pipeline/matching/__init__.py` | |
| **Pipeline runner** | |
| `cluster_pipeline/pipeline/pipeline_runner.py` | Runs per (frame, reff): detection → matching → inject 5-filter → photometry → catalogue. |
| `cluster_pipeline/pipeline/stages.py` | Stage helpers. |
| `cluster_pipeline/pipeline/injection_5filter.py` | Writes per-filter coords for inject script. |
| `cluster_pipeline/pipeline/diagnostics.py` | Match summaries, etc. |
| `cluster_pipeline/pipeline/__init__.py` | |
| **5-filter injection** | |
| `scripts/inject_clusters_to_5filters.py` | Injects matched clusters onto HLSP 5-filter science images; called as subprocess by pipeline. |
| **Photometry & CI** | |
| `cluster_pipeline/photometry/aperture_photometry.py` | IRAF/daophot aperture photometry on matched coords. |
| `cluster_pipeline/photometry/ci_filter.py` | CI = mag(1px)−mag(3px), CI ≥ threshold (e.g. 1.4). |
| `cluster_pipeline/photometry/__init__.py` | |
| **Catalogue & labels** | |
| `cluster_pipeline/catalogue/catalogue_filters.py` | Builds in_catalogue from photometry (CI, merr, multiband). |
| `cluster_pipeline/catalogue/label_builder.py` | Builds final detection .npy from catalogue + match order. |
| `cluster_pipeline/catalogue/__init__.py` | |
| **Utils** | |
| `cluster_pipeline/utils/filesystem.py` | ensure_dir, temporary_directory, etc. |
| `cluster_pipeline/utils/logging_utils.py` | Logger. |
| `cluster_pipeline/utils/mag_parser.py` | Parse .mag coords. |
| `cluster_pipeline/utils/fits_arithmetic.py` | (if used by pipeline) |
| `cluster_pipeline/utils/__init__.py` | |

**Optional reference (same logic as pipeline):**  
`perform_photometry_ci_cut_on_5filters.py` – standalone photometry+CI script (in `scripts/`); pipeline uses `cluster_pipeline` + inject script instead, but you can include it as the “source of truth” for aperture/CI/readme parsing.

---

## 2. Build ML inputs from pipeline outputs

`scripts/perform_ml_to_learn_completeness.py` expects:

- **`--det-path`**: 3D array shape `(n_clusters, n_frames, n_reff)` – detection labels (0/1) per cluster, frame, reff.
- **`--npz-path`**: `.npz` (or `.npz.npy` loaded with `allow_pickle=True`) containing dict:
  - `mass`, `age`, `av`: 1D arrays length `n_clusters * n_frames * n_reff`
  - `phot`: 2D shape `(n_clusters * n_frames * n_reff, 5)` (e.g. 5 filters)  
  Flatten order must be **CFR** (cluster → frame → reff) by default.

Pipeline outputs:

- **Detection:** `ngc628-c/white/detection_labels/detection_frame{i}_{outname}_reff{r:.2f}.npy` (1D, length n_clusters per frame/reff).
- **Physprop:** `physprop/mass_select_model*_frame{i}_reff{r}_{outname}.npy` (and same for `age`, `av`, `mag_BAO_select`, `mag_VEGA_select`).

You need a **small script** that:

1. Loads all `detection_frame*_reff*.npy` and stacks into 3D `(n_clusters, n_frames, n_reff)`.
2. Loads all physprop .npy for mass, age, av, mag_VEGA (5 bands); concatenates in **CFR** order into one flat array each; saves as one `.npz` with keys `mass`, `age`, `av`, `phot`.

**Provided:** `scripts/build_ml_inputs.py` does the above. Example:

```bash
python scripts/build_ml_inputs.py --main-dir . --galaxy ngc628-c --outname test \
  --nframe 2 --reff-list 1 3 6 10 \
  --out-det det_3d.npy --out-npz allprop.npz
```

Use `--use-white-match` to build labels from white-match detection (detection rate) instead of final post–CI labels. The script prints the exact `scripts/perform_ml_to_learn_completeness.py` command to run next.

---

## 3. NN training (final step)

| Include | Purpose |
|--------|---------|
| `scripts/perform_ml_to_learn_completeness.py` | Loads det 3D + npz; optional drop-frame; sweep + train MLP (phys and phot features); saves best model, scalers, plots. |
| `scripts/nn_utils.py` | `plot_train_val_loss`, `scatter_param_vs_val`, `plot_lr_wd_grid` for figures. |

**CLI example:**

```bash
python scripts/perform_ml_to_learn_completeness.py \
  --det-path /path/to/det_3d.npy \
  --npz-path /path/to/allprop.npz \
  --out-dir ./nn_sweep_out \
  --outname model0 \
  --clusters-per-frame 500 \
  --nframes 50 \
  --nreff 10 \
  --prop-flatten-order CFR \
  --save-best
```

**Dependencies:** `torch`, `numpy`, `scikit-learn`, `joblib`, `matplotlib`. No pipeline/IRAF/BAOlab needed for this step.

---

## 4. Suggested repo layout (minimal for paper)

```
your-repo/
├── README.md
├── requirements.txt          # or environment.yml
├── docs/
│   └── DEPLOY_FOR_PAPER.md   # this file
├── scripts/
│   ├── run_small_test.py
│   ├── inject_clusters_to_5filters.py
│   └── build_ml_inputs.py    # pipeline outputs → det_3d + allprop.npz
├── cluster_pipeline/        # full package as above
├── scripts/
│   ├── generate_white_clusters.py
│   ├── perform_photometry_ci_cut_on_5filters.py   # optional reference
│   ├── perform_ml_to_learn_completeness.py
│   ├── nn_utils.py
│   ├── run_small_test.py
│   ├── inject_clusters_to_5filters.py
│   └── ...
└── tests/                    # optional
```

**Exclude from Git:**  
`.venv/`, `__pycache__/`, `.deps/` (or document where to get IRAF/BAOlab), large data (SLUG library, FITS, PSF), `*.npy`/`*.npz` outputs, `tmp_pipeline_test/`, notebook checkpoints.

**Include in README:**  
(1) Environment (Python, IRAF/PyRAF, SExtractor, BAOlab).  
(2) Data: galaxy FITS, `galaxy_filter_dict.npy`, readme, SLUG library, PSF.  
(3) Run pipeline: `python scripts/run_small_test.py --cleanup --nframe N --reff_list "1,3,..." [--run_photometry]`.  
(4) Build ML inputs: `python scripts/build_ml_inputs.py --main-dir . --galaxy ... --outname ... --nframe N --reff-list 1 3 ...` (optionally `--use-white-match`); then run the printed `scripts/perform_ml_to_learn_completeness.py` command.  
(5) Train NN: `python scripts/perform_ml_to_learn_completeness.py --det-path ... --npz-path ...`.

---

## 5. Summary checklist

- [ ] **Pipeline:** `cluster_pipeline/` (config, data, detection, matching, pipeline, photometry, catalogue, utils), `scripts/generate_white_clusters.py`, `scripts/run_small_test.py`, `scripts/inject_clusters_to_5filters.py`.
- [ ] **Reference:** `scripts/perform_photometry_ci_cut_on_5filters.py` (optional).
- [ ] **ML inputs:** `scripts/build_ml_inputs.py` builds `det_3d.npy` + `allprop.npz` from pipeline outputs (CFR order).
- [ ] **NN:** `scripts/perform_ml_to_learn_completeness.py`, `scripts/nn_utils.py`.
- [ ] **Docs:** README (env, data, run order), this deploy list.
- [ ] **Exclude:** venv, big data, generated outputs.
