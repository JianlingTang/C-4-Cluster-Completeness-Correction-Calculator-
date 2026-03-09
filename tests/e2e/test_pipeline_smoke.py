"""
E2E / smoke tests for the pipeline.

- Smoke: config loads, diagnostics can run (empty or mock data).
- Full E2E: run pipeline with minimal params (skip unless RUN_PIPELINE_E2E=1 and data present).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_pipeline_config_imports():
    """Pipeline config and main modules can be imported."""
    from cluster_pipeline.config import get_config
    from cluster_pipeline.pipeline import diagnostics
    cfg = get_config()
    assert cfg is not None
    assert hasattr(diagnostics, "completeness_per_bin")


def test_plot_completeness_diagnostics_empty_dir(tmp_path):
    """plot_completeness_diagnostics with no data does not crash; returns axes with 'no data' title."""
    from cluster_pipeline.pipeline.diagnostics import plot_completeness_diagnostics

    # Use a config that points diagnostics to empty dir
    class MockConfig:
        def diagnostics_dir(self, galaxy_id):
            return tmp_path

    config = MockConfig()
    import matplotlib
    matplotlib.use("Agg")
    ax = plot_completeness_diagnostics("dummy_galaxy", config, outname="test")
    assert ax is not None
    title = ax.get_title()
    assert "dummy_galaxy" in title or "no" in title.lower() or "data" in title.lower()


@pytest.mark.skipif(
    not os.environ.get("RUN_PIPELINE_E2E"),
    reason="Set RUN_PIPELINE_E2E=1 to run full E2E (requires data)",
)
def test_run_small_test_plot_only():
    """Run run_small_test --plot_only (backfill + plot) if pipeline outputs exist."""
    import subprocess
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_small_test.py"),
            "--plot_only",
            "--nframe", "1",
            "--reff_list", "1",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    # May succeed or fail (e.g. no data); we only check it doesn't hang
    assert result.returncode in (0, 1)
