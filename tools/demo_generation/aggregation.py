from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Sequence

from .common import effective_count, lcs_length, median, sample_cv_pct


def pooled_ratio_pct(numerators: Iterable[float], denominators: Iterable[float]) -> Optional[float]:
    numerator = sum(float(value) for value in numerators)
    denominator = sum(float(value) for value in denominators)
    return numerator / denominator * 100.0 if denominator > 0 else None


def exposure_rate(events: float, observed_minutes: float, hours: float = 8.0) -> Optional[float]:
    if observed_minutes <= 0:
        return None
    return float(events) / (float(observed_minutes) / 60.0) * hours


def median_or_none(values: Iterable[Optional[float]]) -> Optional[float]:
    available = [float(value) for value in values if value is not None]
    return median(available) if available else None


def equal_weight_by_group(rows: Iterable[dict], group_key: str, value_key: str) -> Optional[float]:
    grouped = defaultdict(list)
    for row in rows:
        value = row.get(value_key)
        if value is not None:
            grouped[row[group_key]].append(float(value))
    group_values = [median(values) for values in grouped.values() if values]
    return sum(group_values) / len(group_values) if group_values else None


def deduplicated_expected_steps(actual_steps: Sequence[str], expected_steps: Sequence[str]) -> List[str]:
    expected = set(expected_steps)
    seen = set()
    result = []
    for step in actual_steps:
        if step in expected and step not in seen:
            seen.add(step)
            result.append(step)
    return result


def cognition_session_result(session: dict) -> dict:
    expected = session["expectedSteps"]
    actual = session["actualSteps"]
    unique_actual = deduplicated_expected_steps(actual, expected)
    expected_executions = sum(1 for step in actual if step in set(expected))
    extra_executions = max(0, expected_executions - len(unique_actual))
    order_integrity = lcs_length(expected, unique_actual) / len(unique_actual) * 100.0 if unique_actual else 0.0
    errors = session.get("errors", [])
    correctable = [error for error in errors if error.get("correctable", True)]
    self_corrected = [error for error in correctable if error.get("selfCorrected")]
    correction_latencies = [error["correctionLatencySec"] for error in self_corrected if error.get("correctionLatencySec") is not None]
    prompt_count = len(session.get("prompts", []))
    return {
        "startupLatencySec": session["taskStartSec"] - session["taskAvailableSec"],
        "stepCoveragePct": len(unique_actual) / len(expected) * 100.0,
        "completed": bool(session.get("completed")),
        "orderIntegrityPct": order_integrity,
        "repeatRatePct": extra_executions / len(expected) * 100.0,
        "hesitationSecPerStep": sum(session.get("hesitationDurationsSec", [])) / len(expected),
        "selfCorrectionRatePct": len(self_corrected) / len(correctable) * 100.0 if correctable else None,
        "correctionLatencySec": median(correction_latencies) if correction_latencies else None,
        "promptPerStep": prompt_count / len(expected),
        "unpromptedCompletion": bool(session.get("completed")) and prompt_count == 0,
    }


def effective_category_count(minutes_by_category: Dict[str, float]) -> float:
    return effective_count(minutes_by_category)


def within_week_cv_pct(values: Sequence[float]) -> Optional[float]:
    return sample_cv_pct(values)
