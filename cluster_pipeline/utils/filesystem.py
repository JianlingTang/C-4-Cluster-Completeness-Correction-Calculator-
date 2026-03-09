"""
Filesystem utilities: path helpers, safe temp dirs, no os.chdir.
All operations use pathlib and explicit paths.
"""
import contextlib
import shutil
import tempfile
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Create directory (and parents) if it does not exist. Return resolved path."""
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_remove_tree(path: Path) -> None:
    """Recursively remove directory; no-op if path does not exist or is not a dir."""
    p = Path(path).resolve()
    if p.exists() and p.is_dir():
        shutil.rmtree(p, ignore_errors=True)


@contextlib.contextmanager
def temporary_directory(suffix: str | None = None, prefix: str = "cluster_", base_dir: Path | None = None):
    """
    Context manager: create a temporary directory and remove it on exit.
    Yields pathlib.Path. Never use os.chdir; pass the path to callers.
    """
    base = str(base_dir) if base_dir is not None else None
    tmp = tempfile.mkdtemp(suffix=suffix or "", prefix=prefix, dir=base)
    try:
        yield Path(tmp)
    finally:
        safe_remove_tree(Path(tmp))
