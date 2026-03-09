"""
Structured logging for the pipeline. Single logger name; configurable level and format.
"""
import logging
import sys


def get_logger(name: str = "cluster_pipeline") -> logging.Logger:
    """Return a logger for the given name (default: cluster_pipeline)."""
    return logging.getLogger(name)


def setup_logging(
    level: int = logging.INFO,
    format_string: str | None = None,
    stream: logging.StreamHandler | None = None,
) -> None:
    """
    Configure root logger for cluster_pipeline. Call once at entry point.
    """
    if format_string is None:
        format_string = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handler = stream or logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(format_string))
    log = get_logger()
    log.setLevel(level)
    if not log.handlers:
        log.addHandler(handler)
