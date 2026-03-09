"""Integration test: build_ml_inputs produces correct det_3d and allprop from mock pipeline outputs."""
import sys
from pathlib import Path

import numpy as np

# Project root
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_build_ml_inputs_from_mock_outputs(tmp_path):
    """Create mock detection + physprop .npy, run build_ml_inputs, check det_3d and allprop."""
    n_clusters = 20
    nframe = 2
    reff_list = [1.0, 3.0]
    outname = "test"
    galaxy = "mock_galaxy"
    mrmodel = "flat"

    main_dir = tmp_path / "main"
    main_dir.mkdir()
    white_dir = main_dir / galaxy / "white" / "detection_labels"
    white_dir.mkdir(parents=True)
    physprop_dir = main_dir / "physprop"
    physprop_dir.mkdir()

    np.random.seed(42)
    for i_frame in range(nframe):
        for r in reff_list:
            lab = (np.random.rand(n_clusters) > 0.5).astype(np.float32)
            np.save(
                white_dir / f"detection_frame{i_frame}_{outname}_reff{r:.2f}.npy",
                lab,
            )
            base = f"reff{int(r)}_{outname}"
            mass = np.random.uniform(1e5, 1e7, n_clusters)
            age = np.random.uniform(1e7, 1e9, n_clusters)
            av = np.random.uniform(0, 2, n_clusters)
            mag = np.random.uniform(20, 25, (n_clusters, 5))
            np.save(physprop_dir / f"mass_select_model{mrmodel}_frame{i_frame}_{base}.npy", mass)
            np.save(physprop_dir / f"age_select_model{mrmodel}_frame{i_frame}_{base}.npy", age)
            np.save(physprop_dir / f"av_select_model{mrmodel}_frame{i_frame}_{base}.npy", av)
            np.save(physprop_dir / f"mag_VEGA_select_model{mrmodel}_frame{i_frame}_{base}.npy", mag)

    out_det = main_dir / "det_3d.npy"
    out_npz = main_dir / "allprop.npz"

    # Run build_ml_inputs
    import scripts.build_ml_inputs as b
    sys.argv = [
        "build_ml_inputs.py",
        "--main-dir", str(main_dir),
        "--galaxy", galaxy,
        "--outname", outname,
        "--nframe", str(nframe),
        "--reff-list", "1", "3",
        "--out-det", str(out_det),
        "--out-npz", str(out_npz),
    ]
    b.main()

    assert out_det.exists()
    assert out_npz.exists()
    det_3d = np.load(out_det)
    assert det_3d.shape == (n_clusters, nframe, len(reff_list))
    assert det_3d.dtype == np.float32
    assert np.all(np.isin(det_3d, [0, 1]))

    data = np.load(out_npz, allow_pickle=False)
    expected_len = n_clusters * nframe * len(reff_list)
    for key in ("mass", "age", "av"):
        arr = data[key]
        assert arr.shape == (expected_len,), f"{key} shape {arr.shape}"
    assert data["phot"].shape == (expected_len, 5)
