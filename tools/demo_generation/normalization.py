from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .common import clamp, mad, median
from .metric_specs import INDEX_SPECS, RAW_METRICS


@dataclass(frozen=True)
class BaselineScale:
    center: float
    robust_scale: float
    sensitivity_floor: float

    @property
    def scale(self) -> float:
        return max(self.robust_scale, self.sensitivity_floor)


def build_baseline_scale(values: list[float], sensitivity_floor: float) -> BaselineScale:
    if len(values) < 3:
        raise ValueError("A baseline requires at least three values")
    center = median(values)
    return BaselineScale(center, 1.4826 * mad(values, center), sensitivity_floor)


def normalize_value(value: Optional[float], baseline: BaselineScale, direction: str) -> Optional[float]:
    if value is None:
        return None
    delta = (float(value) - baseline.center) / baseline.scale
    if direction in {"higher", "burden"}:
        return clamp(100.0 + 10.0 * delta, 70.0, 130.0)
    if direction == "lower":
        return clamp(100.0 - 10.0 * delta, 70.0, 130.0)
    raise ValueError(f"Unsupported direction: {direction}")


def build_baselines(weekly_metrics: List[Dict[str, Optional[float]]], baseline_weeks: int = 5) -> Dict[str, BaselineScale]:
    if len(weekly_metrics) < baseline_weeks:
        raise ValueError("Not enough weeks to establish baseline")
    baselines = {}
    for key, spec in RAW_METRICS.items():
        values = [week.get(key) for week in weekly_metrics[:baseline_weeks]]
        available = [float(value) for value in values if value is not None]
        if len(available) >= 3:
            baselines[key] = build_baseline_scale(available, spec.sensitivity_floor)
    return baselines


def calculate_indexes(metrics: Dict[str, Optional[float]], baselines: Dict[str, BaselineScale], index_keys: Tuple[str, ...]) -> Tuple[Dict[str, Optional[float]], Dict[str, Dict[str, Optional[float]]]]:
    indexes = {}
    components_by_index = {}
    for index_key in index_keys:
        index_spec = INDEX_SPECS[index_key]
        components = {}
        weighted = 0.0
        total_weight = 0.0
        for component in index_spec.components:
            raw_spec = RAW_METRICS[component.raw_metric]
            value = metrics.get(component.raw_metric)
            baseline = baselines.get(component.raw_metric)
            normalized = normalize_value(value, baseline, raw_spec.direction) if baseline else None
            components[component.raw_metric] = normalized
            if normalized is not None:
                weighted += normalized * component.weight
                total_weight += component.weight
        components_by_index[index_key] = components
        indexes[index_key] = weighted / total_weight if total_weight else None
    return indexes, components_by_index
