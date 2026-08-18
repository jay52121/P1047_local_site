from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from typing import Optional


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def median(values: Iterable[float]) -> float:
    items = [float(value) for value in values]
    if not items:
        raise ValueError("median requires at least one value")
    return float(statistics.median(items))


def mad(values: Iterable[float], center: Optional[float] = None) -> float:
    items = [float(value) for value in values]
    if not items:
        raise ValueError("MAD requires at least one value")
    resolved_center = median(items) if center is None else float(center)
    return median(abs(value - resolved_center) for value in items)


def weighted_mean(pairs: Iterable[tuple[float, float]]) -> Optional[float]:
    numerator = 0.0
    denominator = 0.0
    for value, weight in pairs:
        if weight <= 0:
            continue
        numerator += float(value) * float(weight)
        denominator += float(weight)
    return numerator / denominator if denominator else None


def sample_cv_pct(values: Sequence[float], zero_floor: float = 1e-9) -> Optional[float]:
    items = [float(value) for value in values]
    if len(items) < 2:
        return None
    mean = statistics.fmean(items)
    if abs(mean) <= zero_floor:
        return None
    return statistics.stdev(items) / abs(mean) * 100.0


def effective_count(minutes_by_category: dict[str, float]) -> float:
    positive = [float(value) for value in minutes_by_category.values() if value > 0]
    total = sum(positive)
    if total <= 0:
        return 0.0
    entropy = -sum((value / total) * math.log(value / total) for value in positive)
    return math.exp(entropy)


def lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_value in left:
        current = [0]
        for index, right_value in enumerate(right, start=1):
            if left_value == right_value:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]
