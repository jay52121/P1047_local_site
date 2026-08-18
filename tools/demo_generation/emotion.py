from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional

from .aggregation import exposure_rate, median_or_none, pooled_ratio_pct
from .common import clamp
from .normalization import build_baselines, calculate_indexes
from .quality import emotion_or_participation_day_valid, unit_quality, week_confidence
from .randomness import stable_rng


WINDOW_MIN = 1020.0
TARGET_OBSERVED_MIN = 780.0
EMOTION_METRICS = (
    "activeRatePct", "initiativeEventsPer8h", "selfInitiatedSharePct",
    "interestOpportunityAcceptancePct", "interestEngagementPct",
    "responseRatePct", "responseLatencySec", "longStillRatePct",
    "medianLowActivityEpisodeMin",
)
EMOTION_INDEXES = (
    "behaviorActivation", "initiative", "interestEngagement",
    "socialResponsiveness", "withdrawalBurden",
)
WEEKDAY_OFFSETS = (0.00, -0.01, 0.01, 0.00, -0.01, -0.02, 0.03)
EVENT_SHAPES = {
    "2026-W06": (-0.12, -0.08, 0.10, 0.12, 0.10, -0.04, -0.08),
    "2026-W08": (0.06, 0.04, 0.02, 0.00, -0.02, -0.04, -0.06),
    "2026-W22": (0.00, 0.02, 0.03, 0.04, 0.03, -0.05, -0.07),
}
QUALITY_OVERRIDES = {
    "2026-01-06": "long_unknown_gap",  # W02
    "2026-03-17": "low_coverage",       # W12
    "2026-06-09": "long_unknown_gap",  # W24
    "2026-07-28": "low_coverage",       # W31
}


def _round(value: Optional[float], digits: int = 4) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def _split_total(total: float, count: int, rng, minimum: float = 1.0) -> List[float]:
    if count <= 0:
        return []
    remaining = max(0.0, total - count * minimum)
    weights = [rng.uniform(0.7, 1.3) for _ in range(count)]
    weight_sum = sum(weights)
    values = [minimum + remaining * weight / weight_sum for weight in weights]
    values[-1] += total - sum(values)
    return values


def _max_unknown_gap(segments: Iterable[dict]) -> float:
    return max([0.0, *[segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "unknown"]])


def _observed_runs(segments: List[dict]) -> List[tuple[float, float]]:
    runs = []
    start = None
    end = None
    for segment in segments:
        if segment["state"] != "unknown":
            start = segment["startMin"] if start is None else start
            end = segment["endMin"]
        elif start is not None:
            runs.append((start, end))
            start = end = None
    if start is not None:
        runs.append((start, end))
    return runs


def _point_in_observed(segments: List[dict], at_min: float) -> bool:
    return any(segment["startMin"] <= at_min <= segment["endMin"] and segment["state"] != "unknown" for segment in segments)


def derive_emotion_day_result(segments: List[dict], events: List[dict]) -> dict:
    observed = sum(segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] != "unknown")
    active = sum(segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "active")
    long_still = sum(segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "long_still")
    low_episodes = []
    current = 0.0
    for segment in segments:
        if segment["state"] in {"low_activity", "long_still"}:
            current += segment["endMin"] - segment["startMin"]
        elif current:
            low_episodes.append(current)
            current = 0.0
    if current:
        low_episodes.append(current)

    starts = [event for event in events if event["type"] == "activity_start"]
    interests = [event for event in events if event["type"] == "interest_opportunity"]
    socials = [event for event in events if event["type"] == "social_opportunity"]
    self_starts = sum(event["origin"] == "self" for event in starts)
    accepted = [event for event in interests if event["accepted"]]
    responded = [event for event in socials if event["responded"]]
    opportunity_min = sum(event["endMin"] - event["startMin"] for event in interests)
    engaged_min = sum(event["engagementEndMin"] - event["engagementStartMin"] for event in accepted)
    latencies = [(event["responseAtMin"] - event["atMin"]) * 60.0 for event in responded]

    result = {
        "observedAwakeMin": observed,
        "activeMin": active,
        "longStillMin": long_still,
        "lowActivityEpisodesMin": low_episodes,
        "allActivityStarts": len(starts),
        "selfInitiatedStarts": self_starts,
        "interestOpportunityCount": len(interests),
        "interestAcceptedCount": len(accepted),
        "interestOpportunityMin": opportunity_min,
        "interestEngagedMin": engaged_min,
        "socialOpportunityCount": len(socials),
        "socialRespondedCount": len(responded),
        "responseLatenciesSec": latencies,
        "activeRatePct": pooled_ratio_pct([active], [observed]),
        "initiativeEventsPer8h": exposure_rate(self_starts, observed),
        "selfInitiatedSharePct": pooled_ratio_pct([self_starts], [len(starts)]),
        "interestOpportunityAcceptancePct": pooled_ratio_pct([len(accepted)], [len(interests)]),
        "interestEngagementPct": pooled_ratio_pct([engaged_min], [opportunity_min]),
        "responseRatePct": pooled_ratio_pct([len(responded)], [len(socials)]),
        "responseLatencySec": median_or_none(latencies),
        "longStillRatePct": pooled_ratio_pct([long_still], [observed]),
        "medianLowActivityEpisodeMin": median_or_none(low_episodes),
    }
    return {key: _round(value) if isinstance(value, float) else value for key, value in result.items()}


def generate_emotion_day(person_id: str, day: date, week_id: str, week_burden: float, weekday_index: int) -> dict:
    behavior_rng = stable_rng(person_id, "emotion", day.isoformat(), "behavior")
    context_rng = stable_rng(person_id, "emotion", day.isoformat(), "context")
    quality_rng = stable_rng(person_id, "emotion", day.isoformat(), "quality")
    event_shape = EVENT_SHAPES.get(week_id, (0.0,) * 7)[weekday_index]
    burden = clamp(week_burden + WEEKDAY_OFFSETS[weekday_index] + event_shape + behavior_rng.gauss(0, 0.02), 0, 0.90)
    override = QUALITY_OVERRIDES.get(day.isoformat())
    if override == "low_coverage":
        unknown_total, unknown_count = 570.0, 4
    elif override == "long_unknown_gap":
        unknown_total, unknown_count = 310.0, 2
    else:
        unknown_total, unknown_count = quality_rng.uniform(130.0, 300.0), 3
    observed = WINDOW_MIN - unknown_total
    active_share = clamp(0.46 - 0.20 * burden + behavior_rng.gauss(0, 0.025), 0.25, 0.55)
    long_share = clamp(0.055 + 0.11 * burden + behavior_rng.gauss(0, 0.01), 0.04, 0.18)
    long_min = max(45.1, observed * long_share)
    active_min = observed * active_share
    low_min = observed - active_min - long_min
    active_count = int(clamp(round(7 - 1.5 * burden + behavior_rng.gauss(0, 0.7)), 4, 9))
    low_count = int(clamp(round(6 - 2 * burden + behavior_rng.gauss(0, 0.5)), 3, 7))
    tokens = []
    for index in range(max(active_count, low_count)):
        if index < low_count:
            tokens.append("low_activity")
        if index < active_count:
            tokens.append("active")
    tokens.insert(max(1, len(tokens) // 2), "long_still")
    insert_positions = sorted(quality_rng.sample(range(1, len(tokens)), k=min(unknown_count, len(tokens) - 1)), reverse=True)
    for position in insert_positions:
        tokens.insert(position, "unknown")
    while tokens.count("unknown") < unknown_count:
        tokens.insert(-1, "unknown")
    duration_pool = {
        "active": iter(_split_total(active_min, active_count, behavior_rng, 8.0)),
        "low_activity": iter(_split_total(low_min, low_count, behavior_rng, 8.0)),
        "long_still": iter([long_min]),
        "unknown": iter(_split_total(unknown_total, unknown_count, quality_rng, 10.0)),
    }
    segments = []
    cursor = 0.0
    for index, state in enumerate(tokens):
        duration = next(duration_pool[state])
        end = WINDOW_MIN if index == len(tokens) - 1 else cursor + duration
        segments.append({"startMin": round(cursor, 4), "endMin": round(end, 4), "state": state})
        cursor = end

    events = []
    active_segments = [segment for segment in segments if segment["state"] == "active"]
    p_self = clamp(0.90 - 0.80 * burden + behavior_rng.gauss(0, 0.01), 0.28, 0.92)
    self_count = round(len(active_segments) * p_self)
    for index, segment in enumerate(active_segments, 1):
        origin = "self" if index <= self_count else ("prompted" if behavior_rng.random() < 0.60 else "external")
        events.append({"id": f"{day.isoformat()}-a{index}", "type": "activity_start", "atMin": round(segment["startMin"] + 0.1, 4), "origin": origin, "context": behavior_rng.choice(("routine", "interest", "social", "other"))})

    runs = [run for run in _observed_runs(segments) if run[1] - run[0] >= 55]
    interest_count = 2
    p_accept = clamp(0.94 - 0.90 * burden + behavior_rng.gauss(0, 0.015), 0.25, 0.94)
    for index in range(interest_count):
        run = runs[index % len(runs)]
        duration = min(context_rng.uniform(25, 50), run[1] - run[0] - 2)
        start = run[0] + 1 + (index * 7) % max(1, run[1] - run[0] - duration - 1)
        end = start + duration
        accepted = behavior_rng.random() < p_accept
        engagement_ratio = clamp(0.88 - 0.70 * burden + behavior_rng.gauss(0, 0.02), 0.25, 0.92)
        engaged = duration * engagement_ratio
        engagement_start = start + min(2.0, duration * 0.08) if accepted else None
        engagement_end = min(end, engagement_start + engaged) if accepted else None
        events.append({"id": f"{day.isoformat()}-i{index + 1}", "type": "interest_opportunity", "startMin": round(start, 4), "endMin": round(end, 4), "interestType": context_rng.choice(("reading", "music", "gardening", "television")), "accepted": accepted, "engagementStartMin": _round(engagement_start), "engagementEndMin": _round(engagement_end)})

    social_count = 3
    p_response = clamp(0.98 - 0.62 * burden + behavior_rng.gauss(0, 0.015), 0.42, 0.97)
    response_count = round(social_count * p_response)
    for index in range(social_count):
        run = runs[(index + 1) % len(runs)]
        at_min = run[0] + min(run[1] - run[0] - 2, 4 + index * 9)
        responded = index < response_count
        latency_sec = clamp(10 + 38 * burden + behavior_rng.gauss(0, 6), 2, 90)
        events.append({"id": f"{day.isoformat()}-s{index + 1}", "type": "social_opportunity", "atMin": round(at_min, 4), "source": context_rng.choice(("household_member", "visitor", "phone_call")), "responded": responded, "responseAtMin": round(at_min + latency_sec / 60.0, 4) if responded else None})
    events.sort(key=lambda event: event.get("atMin", event.get("startMin", 0)))
    result = derive_emotion_day_result(segments, events)
    unknown_gaps = [segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "unknown"]
    structural = 100.0
    valid = emotion_or_participation_day_valid(result["observedAwakeMin"], unknown_gaps) and structural == 100
    reason = None if valid else ("structural_error" if structural < 100 else "long_unknown_gap" if _max_unknown_gap(segments) > 180 else "low_coverage")
    quality = unit_quality(result["observedAwakeMin"], TARGET_OBSERVED_MIN, unknown_gaps, WINDOW_MIN, structural)
    return {
        "id": f"emotion-{day.isoformat()}", "date": day.isoformat(), "valid": valid,
        "invalidReason": reason, "observedMinutes": result["observedAwakeMin"],
        "quality": {"coveragePct": _round(quality.coverage_pct), "continuityPct": _round(quality.continuity_pct), "structuralCompletenessPct": structural, "confidencePct": _round(quality.confidence_pct)},
        "segments": segments, "events": events, "result": result,
    }


def aggregate_emotion_week(units: Iterable[dict]) -> dict:
    valid = [unit for unit in units if unit.get("valid")]
    results = [unit["result"] for unit in valid]
    total = lambda key: sum(float(result[key]) for result in results)
    observed = total("observedAwakeMin")
    interest_count = total("interestOpportunityCount")
    interest_min = total("interestOpportunityMin")
    social_count = total("socialOpportunityCount")
    social_responded = total("socialRespondedCount")
    interest_ready = interest_count >= 3 and interest_min >= 60
    social_ready = social_count >= 3
    metrics = {
        "activeRatePct": pooled_ratio_pct([total("activeMin")], [observed]),
        "initiativeEventsPer8h": exposure_rate(total("selfInitiatedStarts"), observed),
        "selfInitiatedSharePct": pooled_ratio_pct([total("selfInitiatedStarts")], [total("allActivityStarts")]),
        "interestOpportunityAcceptancePct": pooled_ratio_pct([total("interestAcceptedCount")], [interest_count]) if interest_ready else None,
        "interestEngagementPct": pooled_ratio_pct([total("interestEngagedMin")], [interest_min]) if interest_ready else None,
        "responseRatePct": pooled_ratio_pct([social_responded], [social_count]) if social_ready else None,
        "responseLatencySec": median_or_none(value for result in results for value in result["responseLatenciesSec"]) if social_ready else None,
        "longStillRatePct": pooled_ratio_pct([total("longStillMin")], [observed]),
        "medianLowActivityEpisodeMin": median_or_none(value for result in results for value in result["lowActivityEpisodesMin"]),
    }
    evidence = {
        "observedMinutes": observed, "activeMin": total("activeMin"),
        "selfInitiatedStarts": int(total("selfInitiatedStarts")), "allActivityStarts": int(total("allActivityStarts")),
        "interestOpportunityCount": int(interest_count), "interestAcceptedCount": int(total("interestAcceptedCount")),
        "interestOpportunityMin": interest_min, "interestEngagedMin": total("interestEngagedMin"),
        "socialOpportunityCount": int(social_count), "socialRespondedCount": int(social_responded),
        "longStillMin": total("longStillMin"),
        "lowActivityEpisodeCount": sum(len(result["lowActivityEpisodesMin"]) for result in results),
    }
    return {"metrics": {key: _round(value) for key, value in metrics.items()}, "evidenceTotals": {key: _round(value) if isinstance(value, float) else value for key, value in evidence.items()}}


def emotion_data_status(valid_units: int, expected_units: int, in_progress: bool = False) -> str:
    sufficient = 3 if in_progress else 5
    partial = 2 if in_progress else 3
    return "sufficient" if valid_units >= sufficient else "partial" if valid_units >= partial else "insufficient"


def calculate_emotion_metric_confidence(week_confidence_pct: float, metrics: dict, totals: dict) -> dict:
    opportunity_count = totals["interestOpportunityCount"]
    opportunity_min = totals["interestOpportunityMin"]
    social_count = totals["socialOpportunityCount"]
    result = {
        "behaviorActivation": week_confidence_pct,
        "withdrawalBurden": week_confidence_pct,
        "initiative": week_confidence_pct if metrics["selfInitiatedSharePct"] is not None else week_confidence_pct * 0.60,
        "interestEngagement": week_confidence_pct if metrics["interestEngagementPct"] is not None else week_confidence_pct * min(opportunity_count / 3, opportunity_min / 60, 1),
        "socialResponsiveness": week_confidence_pct if social_count >= 3 and totals["socialRespondedCount"] > 0 else week_confidence_pct * (0.70 if social_count >= 3 else min(social_count / 3, 1)),
    }
    return {key: _round(value) for key, value in result.items()}


def build_emotion_dataset(scenario_weeks: Iterable[object], person_id: str = "P-1047") -> tuple[List[dict], dict]:
    details = []
    for scenario in scenario_weeks:
        start = date.fromisoformat(scenario.week_start)
        day_count = 4 if scenario.status == "in_progress" else 7
        units = [generate_emotion_day(person_id, start + timedelta(days=index), scenario.week_id, scenario.burdens["emotion"], index) for index in range(day_count)]
        aggregate = aggregate_emotion_week(units)
        details.append({
            "schemaVersion": "1.0", "personId": person_id, "domain": "emotion",
            "weekId": scenario.week_id, "weekStart": scenario.week_start, "weekEnd": scenario.week_end,
            "sourceType": "simulation", "calculationMode": "generated-from-events", "calculationVersion": "v2-events-1", "evidenceOrigin": "generated",
            "expectedUnits": day_count, "observedThroughDate": scenario.observed_through_date,
            "units": units, "weekAggregate": aggregate,
        })
    weekly_metrics = [detail["weekAggregate"]["metrics"] for detail in details]
    baselines = build_baselines(weekly_metrics)
    summary_weeks = []
    for scenario, detail in zip(scenario_weeks, details):
        valid_units = sum(unit["valid"] for unit in detail["units"])
        status = emotion_data_status(valid_units, detail["expectedUnits"], scenario.status == "in_progress")
        confidence = week_confidence(detail["units"], detail["expectedUnits"])
        metrics = detail["weekAggregate"]["metrics"]
        indexes, components = calculate_indexes(metrics, baselines, EMOTION_INDEXES)
        if status != "sufficient":
            indexes = {key: None for key in EMOTION_INDEXES}
        event = scenario.event
        summary_weeks.append({
            "weekId": scenario.week_id, "weekIndex": scenario.week_index, "weekStart": scenario.week_start, "weekEnd": scenario.week_end,
            "status": scenario.status, "dataStatus": status, "provisional": scenario.status == "in_progress", "observedThroughDate": scenario.observed_through_date,
            "expectedUnits": detail["expectedUnits"], "validUnits": valid_units, "confidencePct": _round(confidence),
            "metricConfidencePct": calculate_emotion_metric_confidence(confidence, metrics, detail["weekAggregate"]["evidenceTotals"]),
            "phase": scenario.phase, "event": event.label if event else None, "eventKind": event.kind if event else None,
            "note": "当前周数据截至 2026-08-13，结果为暂定" if scenario.status == "in_progress" else None,
            "metrics": metrics, "indexes": {key: _round(value) for key, value in indexes.items()},
            "indexComponents": {key: {metric: _round(value) for metric, value in values.items()} for key, values in components.items()},
        })
    summary = {
        "schemaVersion": "1.0", "personId": person_id, "domain": "emotion",
        "sourceType": "simulation", "calculationMode": "generated-from-events", "calculationVersion": "v2-events-1", "evidenceOrigin": "generated",
        "baseline": {"weekIds": [week.week_id for week in list(scenario_weeks)[:5]]}, "weeks": summary_weeks,
    }
    return details, summary
