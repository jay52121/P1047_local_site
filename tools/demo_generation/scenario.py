from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ScenarioEvent:
    kind: str
    label: str


@dataclass(frozen=True)
class ScenarioWeek:
    week_id: str
    week_index: int
    week_start: str
    week_end: str
    phase: str
    event: Optional[ScenarioEvent]
    burdens: Dict[str, float]
    status: str = "complete"
    observed_through_date: Optional[str] = None

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["event"] = asdict(self.event) if self.event else None
        return payload


EVENTS = {
    "2025-W52": ScenarioEvent("milestone", "日常活动增加"),
    "2026-W04": ScenarioEvent("milestone", "活动量开始减少"),
    "2026-W06": ScenarioEvent("external", "家中异常事件，短期活动明显减少"),
    "2026-W08": ScenarioEvent("intervention", "开始规律康复训练"),
    "2026-W16": ScenarioEvent("milestone", "恢复到较稳定活动水平"),
    "2026-W22": ScenarioEvent("external", "高温天气，外出活动减少"),
    "2026-W27": ScenarioEvent("milestone", "连续数周活动量偏低"),
    "2026-W29": ScenarioEvent("milestone", "日常活动逐步恢复"),
    "2026-W33": ScenarioEvent("data_status", "当前周（进行中）"),
}


BURDEN_KEYFRAMES = {
    "emotion": {1: 0.08, 7: 0.04, 11: 0.22, 13: 0.62, 15: 0.50, 23: 0.18, 29: 0.36, 34: 0.48, 36: 0.32, 40: 0.20},
    "participation": {1: 0.08, 7: 0.03, 11: 0.28, 13: 0.66, 15: 0.54, 23: 0.16, 29: 0.62, 34: 0.58, 36: 0.38, 40: 0.22},
    "sleep": {1: 0.10, 7: 0.08, 11: 0.20, 13: 0.48, 15: 0.42, 23: 0.20, 29: 0.34, 34: 0.40, 36: 0.30, 40: 0.22},
    "cognition": {1: 0.08, 7: 0.07, 11: 0.14, 13: 0.26, 15: 0.24, 23: 0.16, 29: 0.18, 34: 0.24, 36: 0.22, 40: 0.18},
}


def interpolate(keyframes: Dict[int, float], week_index: int) -> float:
    points = sorted(keyframes.items())
    if week_index <= points[0][0]:
        return points[0][1]
    if week_index >= points[-1][0]:
        return points[-1][1]
    for (left_week, left_value), (right_week, right_value) in zip(points, points[1:]):
        if left_week <= week_index <= right_week:
            fraction = (week_index - left_week) / (right_week - left_week)
            return left_value + fraction * (right_value - left_value)
    raise AssertionError("unreachable")


def phase_for_week(week_index: int) -> str:
    if week_index <= 5:
        return "稳定建立期"
    if week_index <= 7:
        return "轻度改善期"
    if week_index <= 12:
        return "缓慢下降期"
    if week_index <= 14:
        return "事件后快速变化期"
    if week_index <= 22:
        return "干预恢复期"
    if week_index <= 28:
        return "部分恢复后波动期"
    if week_index <= 35:
        return "环境影响与再次下降期"
    return "近期恢复期"


def build_scenario() -> List[ScenarioWeek]:
    start = date(2025, 11, 10)
    weeks = []
    for index in range(1, 41):
        week_start = start + timedelta(days=(index - 1) * 7)
        iso_year, iso_week, _ = week_start.isocalendar()
        week_id = f"{iso_year}-W{iso_week:02d}"
        weeks.append(ScenarioWeek(
            week_id=week_id,
            week_index=index,
            week_start=week_start.isoformat(),
            week_end=(week_start + timedelta(days=6)).isoformat(),
            phase=phase_for_week(index),
            event=EVENTS.get(week_id),
            burdens={domain: round(interpolate(points, index), 4) for domain, points in BURDEN_KEYFRAMES.items()},
            status="in_progress" if week_id == "2026-W33" else "complete",
            observed_through_date="2026-08-13" if week_id == "2026-W33" else None,
        ))
    return weeks
