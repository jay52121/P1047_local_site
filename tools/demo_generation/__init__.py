"""Deterministic event-first calculation kernel for SISP demo data."""

from .normalization import BaselineScale, build_baseline_scale, normalize_value

__all__ = ["BaselineScale", "build_baseline_scale", "normalize_value"]
