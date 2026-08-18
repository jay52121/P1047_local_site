from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .common import clamp, weighted_mean


@dataclass(frozen=True)
class UnitQuality:
    coverage_pct: float
    continuity_pct: float
    structural_completeness_pct: float

    @property
    def confidence_pct(self) -> float:
        return (
            0.50 * self.coverage_pct
            + 0.30 * self.continuity_pct
            + 0.20 * self.structural_completeness_pct
        )


def coverage_pct(observed_minutes: float, target_minutes: float) -> float:
    if target_minutes <= 0:
        raise ValueError("target_minutes must be positive")
    return clamp(observed_minutes / target_minutes, 0.0, 1.0) * 100.0


def continuity_pct(unknown_gaps_minutes: Iterable[float], observation_window_minutes: float) -> float:
    if observation_window_minutes <= 0:
        raise ValueError("observation_window_minutes must be positive")
    long_gap_minutes = sum(max(float(gap) - 15.0, 0.0) for gap in unknown_gaps_minutes)
    return clamp(1.0 - long_gap_minutes / observation_window_minutes, 0.0, 1.0) * 100.0


def unit_quality(observed_minutes: float, target_minutes: float, unknown_gaps_minutes: Iterable[float], observation_window_minutes: float, structural_completeness_pct: float) -> UnitQuality:
    return UnitQuality(
        coverage_pct(observed_minutes, target_minutes),
        continuity_pct(unknown_gaps_minutes, observation_window_minutes),
        clamp(structural_completeness_pct, 0.0, 100.0),
    )


def week_confidence(units: Iterable[dict], expected_units: int) -> Optional[float]:
    if expected_units <= 0:
        return None
    valid = [unit for unit in units if unit.get("valid")]
    if not valid:
        return 0.0
    mean_confidence = weighted_mean(
        (unit["quality"]["confidencePct"], unit.get("observedMinutes", 1.0))
        for unit in valid
    )
    adequacy = min(len(valid) / expected_units, 1.0) * 100.0
    return 0.75 * float(mean_confidence) + 0.25 * adequacy


def emotion_or_participation_day_valid(observed_minutes: float, unknown_gaps_minutes: Iterable[float]) -> bool:
    return observed_minutes >= 480 and max([0.0, *[float(gap) for gap in unknown_gaps_minutes]]) <= 180


def sleep_day_valid(observed_minutes: float, required_events: dict) -> bool:
    return observed_minutes >= 1080 and all(required_events.get(key) is not None for key in ("bedEntry", "finalRise", "sleepOnset", "finalWake"))


def cognition_session_valid(session: dict) -> bool:
    return (
        len(session.get("expectedSteps", [])) >= 4
        and session.get("taskAvailableSec") is not None
        and session.get("taskStartSec") is not None
        and session.get("terminalEvent") is not None
        and session.get("timelineCoveragePct", 0) >= 90
    )


def cognition_week_sufficient(sessions: Iterable[dict]) -> bool:
    valid = [session for session in sessions if cognition_session_valid(session)]
    return len(valid) >= 4 and len({session["taskType"] for session in valid}) >= 3 and len({session["date"] for session in valid}) >= 3
