#!/usr/bin/env python3
"""
Build ML inputs from pipeline outputs for perform_ml_to_learn_completeness.py.

Reads detection_labels (or white_match) and physprop .npy, produces:
  - det_3d.npy: shape (n_clusters, n_frames, n_reff), dtype 0/1
  - allprop.npz: dict with mass, age, av, phot (flattened in CFR order)

Optional: --cleanup-after removes all pipeline outputs (including all .fits) under
the project after saving the ML files, to save space.

Usage:
  python scripts/build_ml_inputs.py --main-dir . --galaxy ngc628-c --outname test \\
    --nframe 2 --reff-list 1 3 6 10 --out-det det_3d.npy --out-npz allprop.npz
  python scripts/build_ml_inputs.py ... --cleanup-after   # then delete pipeline outputs + all .fits
"""
import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def cleanup_pipeline_outputs(main_dir: Path, galaxy: str) -> None:
    """Remove all pipeline-generated outputs and all .fits under the galaxy dir."""
    main_dir = Path(main_dir).resolve()
    white_dir = main_dir / galaxy / "white"
    physprop_dir = main_dir / "physprop"
    tmp_dir = main_dir / "tmp_pipeline_test"
    gal_dir = main_dir / galaxy

    # physprop
    if physprop_dir.exists():
        for f in physprop_dir.glob("*.npy"):
            f.unlink()
        print("  Removed physprop/*.npy")

    # white subdirs and position files
    for name in ["detection_labels", "diagnostics", "matched_coords", "baolab", "synthetic_fits", "synthetic_frames"]:
        d = white_dir / name
        if d.exists():
            shutil.rmtree(d)
            print(f"  Removed {d.relative_to(main_dir)}")
    for f in set(white_dir.glob("white_position_*.txt")) | set(white_dir.glob("*_position_*_test_*.txt")):
        f.unlink()
        print(f"  Removed {f.name}")
    cat_dir = white_dir / "catalogue"
    if cat_dir.exists():
        for f in cat_dir.glob("*.parquet"):
            f.unlink()
        print("  Removed catalogue/*.parquet")

    # tmp
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
        print(f"  Removed {tmp_dir.relative_to(main_dir)}")

    # per-filter dirs under galaxy (e.g. F275w, F336w, ...)
    if gal_dir.exists():
        for sub in gal_dir.iterdir():
            if sub.is_dir() and sub.name != "white":
                for name in ["synthetic_fits", "baolab", "synthetic_frames"]:
                    d = sub / name
                    if d.exists():
                        shutil.rmtree(d)
                        print(f"  Removed {d.relative_to(main_dir)}")
        # remove any remaining .fits under galaxy (e.g. under white or filter dirs)
        fits_list = list(gal_dir.rglob("*.fits"))
        for f in fits_list:
            f.unlink()
        if fits_list:
            print(f"  Removed {len(fits_list)} .fits under {galaxy}/")
    print("Cleanup done.\n")


def main():
    ap = argparse.ArgumentParser(description="Build det_3d.npy and allprop.npz from pipeline outputs.")
    ap.add_argument("--main-dir", type=Path, default=ROOT, help="Project root (contains galaxy dirs, physprop)")
    ap.add_argument("--galaxy", type=str, default="ngc628-c")
    ap.add_argument("--outname", type=str, default="test")
    ap.add_argument("--nframe", type=int, required=True)
    ap.add_argument("--reff-list", type=float, nargs="+", required=True, help="e.g. 1 3 6 10")
    ap.add_argument("--use-white-match", action="store_true", help="Use white_match labels instead of final (after CI)")
    ap.add_argument("--out-det", type=Path, default=None, help="Output path for 3D detection array")
    ap.add_argument("--out-npz", type=Path, default=None, help="Output path for allprop .npz")
    ap.add_argument("--cleanup-after", action="store_true", help="After saving ML files, remove all pipeline outputs (incl. all .fits)")
    args = ap.parse_args()

    main_dir = Path(args.main_dir).resolve()
    white_dir = main_dir / args.galaxy / "white"
    labels_dir = white_dir / "detection_labels"
    physprop_dir = main_dir / "physprop"
    nframe = args.nframe
    reff_list = sorted([float(r) for r in args.reff_list])
    n_reff = len(reff_list)
    mrmodel = "flat"

    # Infer n_clusters from first available detection file
    n_clusters = None
    for i_frame in range(nframe):
        for r in reff_list:
            if args.use_white_match:
                p = labels_dir / f"detection_labels_white_match_frame{i_frame}_{args.outname}_reff{r:.2f}.npy"
            else:
                p = labels_dir / f"detection_frame{i_frame}_{args.outname}_reff{r:.2f}.npy"
            if p.exists():
                lab = np.load(p)
                n_clusters = len(lab)
                break
        if n_clusters is not None:
            break
    if n_clusters is None:
        print("No detection .npy found; check --galaxy, --outname, --nframe, --reff-list", file=sys.stderr)
        sys.exit(1)

    # Build det_3d (n_clusters, n_frames, n_reff)
    det_3d = np.zeros((n_clusters, nframe, n_reff), dtype=np.float32)
    for i_frame in range(nframe):
        for ir, r in enumerate(reff_list):
            if args.use_white_match:
                p = labels_dir / f"detection_labels_white_match_frame{i_frame}_{args.outname}_reff{r:.2f}.npy"
            else:
                p = labels_dir / f"detection_frame{i_frame}_{args.outname}_reff{r:.2f}.npy"
            if not p.exists():
                print(f"Missing {p.name}", file=sys.stderr)
                continue
            lab = np.load(p)
            n = min(n_clusters, len(lab))
            det_3d[:n, i_frame, ir] = lab[:n]

    # Build allprop in CFR order: for each cluster c, for each frame f, for each reff r -> one row
    mass_list = []
    age_list = []
    av_list = []
    phot_list = []
    for i_frame in range(nframe):
        for ir, r in enumerate(reff_list):
            base = f"reff{int(r)}_{args.outname}"
            mass_path = physprop_dir / f"mass_select_model{mrmodel}_frame{i_frame}_{base}.npy"
            age_path = physprop_dir / f"age_select_model{mrmodel}_frame{i_frame}_{base}.npy"
            av_path = physprop_dir / f"av_select_model{mrmodel}_frame{i_frame}_{base}.npy"
            mag_path = physprop_dir / f"mag_VEGA_select_model{mrmodel}_frame{i_frame}_{base}.npy"
            for p in (mass_path, age_path, av_path, mag_path):
                if not p.exists():
                    print(f"Missing {p.name}", file=sys.stderr)
                    sys.exit(1)
            mass = np.load(mass_path)
            age = np.load(age_path)
            av = np.load(av_path)
            mag = np.load(mag_path)
            if mag.ndim == 1:
                mag = mag.reshape(-1, 1)
            for c in range(n_clusters):
                idx = c if c < len(mass) else -1
                mass_list.append(mass[idx] if idx >= 0 else np.nan)
                age_list.append(age[idx] if idx >= 0 else np.nan)
                av_list.append(av[idx] if idx >= 0 else np.nan)
                phot_list.append(mag[idx] if idx >= 0 else np.full(mag.shape[1], np.nan))

    mass_arr = np.array(mass_list, dtype=np.float64)
    age_arr = np.array(age_list, dtype=np.float64)
    av_arr = np.array(av_list, dtype=np.float64)
    phot_arr = np.array(phot_list, dtype=np.float64)
    if phot_arr.ndim == 1:
        phot_arr = phot_arr.reshape(-1, 1)

    expected = n_clusters * nframe * n_reff
    assert len(mass_arr) == expected, f"Length {len(mass_arr)} != {expected}"

    allprop = {"mass": mass_arr, "age": age_arr, "av": av_arr, "phot": phot_arr}

    out_det = args.out_det or main_dir / "det_3d.npy"
    out_npz = args.out_npz or main_dir / "allprop.npz"
    out_det = Path(out_det).resolve()
    out_npz = Path(out_npz).resolve()
    np.save(out_det, det_3d)
    np.savez(out_npz, **allprop)
    print(f"Saved {out_det} shape {det_3d.shape}")
    print(f"Saved {out_npz} keys {list(allprop.keys())} lengths {[len(v) for k, v in allprop.items() if hasattr(v, '__len__')]}")
    print(f"Run: python scripts/perform_ml_to_learn_completeness.py --det-path {out_det} --npz-path {out_npz} --clusters-per-frame {n_clusters} --nframes {nframe} --nreff {n_reff}")
    if args.cleanup_after:
        print("Cleanup: removing pipeline outputs (including all .fits)...")
        cleanup_pipeline_outputs(main_dir, args.galaxy)


if __name__ == "__main__":
    main()
