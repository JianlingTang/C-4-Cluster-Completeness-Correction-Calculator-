"""
Catalogue filters and binary label builder.
Applies photometric quality cuts and builds final_detection = detection_filters.
"""
from .catalogue_filters import apply_catalogue_filters, write_catalogue_parquet
from .label_builder import build_final_detection, save_final_detection

__all__ = ["apply_catalogue_filters", "write_catalogue_parquet", "build_final_detection", "save_final_detection"]
