#!/usr/bin/env python3
"""Validate the static SISP demo package and its cross-file calculations."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from demo_generation.emotion import EMOTION_INDEXES, EMOTION_METRICS, aggregate_emotion_week, build_emotion_evidence_summary, derive_emotion_day_result
from demo_generation.normalization import build_baselines, calculate_indexes
from demo_generation.quality import unit_quality, week_confidence
from demo_generation.metric_specs import DOMAIN_INDEXES


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/demo"
ERRORS = []


def load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        ERRORS.append(f"{path.relative_to(ROOT)}: {error}")
        return None


def check(condition, message):
    if not condition:
        ERRORS.append(message)


def validate_weeks(summary, expected_count, detail_path):
    weeks = summary.get("weeks", [])
    check(len(weeks) == expected_count, f"{summary.get('personId')}/{summary.get('domain')}: expected {expected_count} weeks, got {len(weeks)}")
    previous_end = None
    ids = set()
    for week in weeks:
        start = date.fromisoformat(week["weekStart"])
        end = date.fromisoformat(week["weekEnd"])
        iso_year, iso_week, _ = start.isocalendar()
        expected_id = f"{iso_year}-W{iso_week:02d}"
        check(week["weekId"] == expected_id, f"{week['weekId']}: expected ISO id {expected_id}")
        check(week["weekId"] not in ids, f"duplicate week id {week['weekId']}")
        check(end - start == timedelta(days=6), f"{week['weekId']}: week must contain seven calendar days")
        if previous_end:
            check(start - previous_end == timedelta(days=1), f"{week['weekId']}: non-contiguous week range")
        previous_end = end
        ids.add(week["weekId"])
        check(0 <= week["confidencePct"] <= 100, f"{week['weekId']}: invalid confidence")
        check(detail_path(week).exists(), f"{week['weekId']}: missing detail file")


def validate_life():
    path = DATA / "P-1047/life/weekly-summary.json"
    summary = load(path)
    if not summary:
        return
    check(summary.get("schemaVersion") == "1.0", "life summary schemaVersion must be 1.0")
    check(summary.get("sourceType") == "simulation", "public life data must be simulation")
    validate_weeks(summary, 40, lambda week: path.parent / "weeks" / f"{week['weekId']}.json")
    for week in summary["weeks"]:
        detail = load(path.parent / "weeks" / f"{week['weekId']}.json")
        if not detail:
            continue
        session = detail["representativeSession"]
        check(session["durationSec"] > week["metrics"]["transferCompletionSec"], f"{week['weekId']}: invalid representative action duration")
        check(session["parameters"]["powerPhaseSec"] == week["metrics"]["powerPhaseSec"], f"{week['weekId']}: power phase mismatch")


def validate_attention():
    base = DATA / "C-2308/attention"
    summaries = sorted(base.glob("*-weekly-summary.json"))
    check(len(summaries) == 6, f"attention: expected 6 task summaries, got {len(summaries)}")
    for path in summaries:
        summary = load(path)
        if not summary:
            continue
        task_id = summary["taskId"]
        validate_weeks(summary, 24, lambda week: base / "weeks" / task_id / f"{week['weekId']}.json")
        for week in summary["weeks"]:
            detail = load(base / "weeks" / task_id / f"{week['weekId']}.json")
            if not detail:
                continue
            session = detail["representativeSession"]
            distractions = sorted(event["minute"] for event in session["events"] if event["type"] == "distraction")
            check(bool(distractions), f"{task_id}/{week['weekId']}: missing distraction event")
            if distractions:
                expected = week["metrics"]["firstDistractionMin"]
                check(abs(distractions[0] - expected) < 0.001, f"{task_id}/{week['weekId']}: first distraction mismatch")
            cursor = 0.0
            for segment in session["segments"]:
                check(abs(segment["startMin"] - cursor) < 0.001, f"{task_id}/{week['weekId']}: segment gap or overlap")
                check(segment["endMin"] >= segment["startMin"], f"{task_id}/{week['weekId']}: negative segment")
                cursor = segment["endMin"]
            check(abs(cursor - session["durationMin"]) < 0.001, f"{task_id}/{week['weekId']}: segments do not cover task duration")


def validate_attention_showcase():
    base = DATA / "C-2308/attention"
    summary = load(base / "weekly-summary.json")
    if not summary:
        return
    check(summary.get("calculationVersion") == "v2-attention-demo-1", "attention V2: calculation version mismatch")
    check(len(summary.get("weeks", [])) == 24, "attention V2: expected 24 weeks")
    task_variation = {}
    for week in summary["weeks"]:
        detail = load(base / "weeks" / f"{week['weekId']}.json")
        if not detail:
            continue
        check(4 <= len(detail["sessions"]) <= 10, f"attention V2/{week['weekId']}: session count must be 4-10")
        for session in detail["sessions"]:
            cursor = 0.0
            for segment in session["segments"]:
                check(close(segment["startMin"], cursor, 0.001), f"attention V2/{session['sessionId']}: segment gap")
                cursor = segment["endMin"]
            check(close(cursor, session["durationMin"], 0.001), f"attention V2/{session['sessionId']}: segments must cover duration")
            row = task_variation.setdefault(session["taskId"], {"duration": set(), "distraction": set()})
            row["duration"].add(session["durationMin"]); row["distraction"].add(session["result"]["distractionCount"])
    for task_id, row in task_variation.items():
        check(len(row["duration"]) > 5, f"attention V2/{task_id}: duration variation is too small")
        check({0, 1}.issubset(row["distraction"]) and any(value >= 2 for value in row["distraction"]), f"attention V2/{task_id}: distraction variation is too small")


def close(left, right, tolerance=0.01):
    if left is None or right is None:
        return left is None and right is None
    return abs(float(left) - float(right)) <= tolerance


def nested_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key).lower()
            yield from nested_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_keys(child)


def validate_emotion():
    path = DATA / "P-1047/emotion/weekly-summary.json"
    summary = load(path)
    if not summary:
        return
    expected_provenance = {
        "sourceType": "simulation", "calculationMode": "generated-from-events",
        "calculationVersion": "v2-events-1", "evidenceOrigin": "generated",
    }
    for key, value in expected_provenance.items():
        check(summary.get(key) == value, f"emotion summary: {key} must be {value}")
    validate_weeks(summary, 40, lambda week: path.parent / "weeks" / f"{week['weekId']}.json")
    check([week["weekId"] for week in summary["weeks"][:5]] == summary["baseline"]["weekIds"], "emotion: baseline week ids mismatch")
    forbidden_metrics = {"effectiveZoneCount", "zoneTransitionsPer8h", "outsideMinutesPerValidDay", "outingDaysRatePct", "outingsPerValidDay", "interactionMinutesPer8h", "interactionEpisodesPer8h", "activityEffectiveTypes", "activityCategoryCount"}
    forbidden_events = {"outing", "zone_transition", "location", "interaction_session"}
    forbidden_key_tokens = ("outside", "location", "zone", "outing", "interactionduration", "interaction_duration")
    mapping = load(path.parent / "emotion_metric_mapping.json")
    check(bool(mapping) and set(mapping.get("rawMetrics", {})) == set(EMOTION_METRICS), "emotion: metric mapping raw keys mismatch")
    check(bool(mapping) and set(mapping.get("indexes", {})) == set(EMOTION_INDEXES), "emotion: metric mapping index keys mismatch")
    recalculated_metrics = []
    details = []
    for week in summary["weeks"]:
        detail_path = path.parent / "weeks" / f"{week['weekId']}.json"
        detail = load(detail_path)
        if not detail:
            continue
        details.append(detail)
        for key, value in expected_provenance.items(): check(detail.get(key) == value, f"emotion/{week['weekId']}: {key} mismatch")
        check(detail.get("weekId") == week["weekId"], f"emotion/{week['weekId']}: detail week id mismatch")
        check(set(week["metrics"]) == set(EMOTION_METRICS), f"emotion/{week['weekId']}: raw metric keys must be exact")
        check(set(week["indexes"]) == set(EMOTION_INDEXES), f"emotion/{week['weekId']}: index keys must be exact")
        check(not forbidden_metrics.intersection(week["metrics"]), f"emotion/{week['weekId']}: participation metric leaked into emotion")
        leaked_keys = [key for key in nested_keys(detail) if any(token in key for token in forbidden_key_tokens)]
        check(not leaked_keys, f"emotion/{week['weekId']}: participation key leaked into emotion: {leaked_keys[:3]}")
        if week["weekId"] == "2026-W33":
            check(week["status"] == "in_progress" and week["observedThroughDate"] == "2026-08-13", "emotion/W33: current-week status mismatch")
            check([unit["date"] for unit in detail["units"]] == ["2026-08-10", "2026-08-11", "2026-08-12", "2026-08-13"], "emotion/W33: must contain Mon-Thu only")
        for unit in detail["units"]:
            segments = unit["segments"]
            check(bool(segments) and close(segments[0]["startMin"], 0, 0.001) and close(segments[-1]["endMin"], 1020, 0.001), f"emotion/{week['weekId']}/{unit['date']}: segments must cover 0-1020")
            cursor = 0.0
            for segment in segments:
                check(close(segment["startMin"], cursor, 0.001), f"emotion/{week['weekId']}/{unit['date']}: segment gap/overlap")
                check(segment["endMin"] > segment["startMin"], f"emotion/{week['weekId']}/{unit['date']}: non-positive segment")
                check(segment["state"] in {"active", "low_activity", "long_still", "unknown"}, f"emotion/{week['weekId']}/{unit['date']}: illegal state")
                if segment["state"] == "long_still": check(segment["endMin"] - segment["startMin"] >= 45, f"emotion/{week['weekId']}/{unit['date']}: long_still below 45 min")
                cursor = segment["endMin"]
            for event in unit["events"]:
                check(event["type"] not in forbidden_events, f"emotion/{week['weekId']}/{unit['date']}: forbidden participation event")
                if event["type"] == "activity_start":
                    check(any(segment["state"] != "unknown" and segment["startMin"] <= event["atMin"] <= segment["endMin"] for segment in segments), f"emotion/{week['weekId']}/{unit['date']}: activity event in unknown")
                elif event["type"] == "interest_opportunity":
                    check(event["startMin"] < event["endMin"], f"emotion/{week['weekId']}/{unit['date']}: invalid interest interval")
                    if event["accepted"]: check(event["startMin"] <= event["engagementStartMin"] < event["engagementEndMin"] <= event["endMin"], f"emotion/{week['weekId']}/{unit['date']}: invalid engagement interval")
                    else: check(event["engagementStartMin"] is None and event["engagementEndMin"] is None, f"emotion/{week['weekId']}/{unit['date']}: rejected interest has engagement")
                elif event["type"] == "social_opportunity":
                    check((event["responded"] and event["responseAtMin"] >= event["atMin"]) or (not event["responded"] and event["responseAtMin"] is None), f"emotion/{week['weekId']}/{unit['date']}: invalid social response")
                else: check(False, f"emotion/{week['weekId']}/{unit['date']}: unknown event type")
            result = derive_emotion_day_result(segments, unit["events"])
            for key, value in result.items():
                if isinstance(value, list):
                    check(len(value) == len(unit["result"][key]) and all(close(a, b, 0.01) for a, b in zip(value, unit["result"][key])), f"emotion/{week['weekId']}/{unit['date']}: {key} mismatch")
                else: check(close(value, unit["result"][key], 0.01), f"emotion/{week['weekId']}/{unit['date']}: {key} mismatch")
            unknown = [segment["endMin"] - segment["startMin"] for segment in segments if segment["state"] == "unknown"]
            quality = unit_quality(result["observedAwakeMin"], 780, unknown, 1020, unit["quality"]["structuralCompletenessPct"])
            for key, value in (("coveragePct", quality.coverage_pct), ("continuityPct", quality.continuity_pct), ("confidencePct", quality.confidence_pct)):
                check(close(unit["quality"][key], value, 0.01), f"emotion/{week['weekId']}/{unit['date']}: quality {key} mismatch")
        aggregate = aggregate_emotion_week(detail["units"])
        recalculated_metrics.append(aggregate["metrics"])
        for key in EMOTION_METRICS:
            check(close(aggregate["metrics"][key], detail["weekAggregate"]["metrics"][key]), f"emotion/{week['weekId']}: detail aggregate {key} mismatch")
            check(close(aggregate["metrics"][key], week["metrics"][key]), f"emotion/{week['weekId']}: summary metric {key} mismatch")
        confidence = week_confidence(detail["units"], detail["expectedUnits"])
        check(close(confidence, week["confidencePct"]), f"emotion/{week['weekId']}: confidence mismatch")
    if len(recalculated_metrics) == 40:
        baselines = build_baselines(recalculated_metrics)
        for week, detail, metrics in zip(summary["weeks"], details, recalculated_metrics):
            indexes, _ = calculate_indexes(metrics, baselines, EMOTION_INDEXES)
            if week["dataStatus"] != "sufficient": indexes = {key: None for key in EMOTION_INDEXES}
            for key in EMOTION_INDEXES: check(close(indexes[key], week["indexes"][key]), f"emotion/{week['weekId']}: index {key} mismatch")
            check(detail.get("evidenceSummary") == build_emotion_evidence_summary(metrics, baselines), f"emotion/{week['weekId']}: evidence summary mismatch")


def validate_public_boundary():
    for path in (ROOT / "data").rglob("*.json"):
        payload = path.read_text(encoding="utf-8")
        check('"sourceType": "real"' not in payload, f"{path.relative_to(ROOT)}: real data cannot be committed to public demo data")


def validate_showcase_domains():
    anchors = {
        "cognition": {"2025-W46", "2026-W06", "2026-W16", "2026-W33"},
        "sleep": {"2025-W46", "2026-W06", "2026-W16", "2026-W33"},
        "participation": {"2025-W46", "2026-W22", "2026-W29", "2026-W33"},
    }
    comparisons = {"cognition": ("2026-W06", "2026-W16"), "sleep": ("2026-W06", "2026-W16"), "participation": ("2026-W22", "2026-W29")}
    for domain in anchors:
        base = DATA / "P-1047" / domain
        summary, evidence, mapping = load(base / "weekly-summary.json"), load(base / "evidence-lite.json"), load(base / "metric-mapping.json")
        if not all((summary, evidence, mapping)):
            continue
        check(len(summary["weeks"]) == 40 and len(evidence["weeks"]) == 40, f"{domain}: expected 40 summary and lite weeks")
        check(set(mapping["indexes"]) == set(DOMAIN_INDEXES[domain]), f"{domain}: index mapping mismatch")
        check({path.stem for path in (base / "weeks").glob("*.json")} == anchors[domain], f"{domain}: full detail anchors mismatch")
        current = next(week for week in evidence["weeks"] if week["weekId"] == "2026-W33")
        units = current.get("sessions") or current.get("nights") or current.get("days")
        check(len(units) == 4, f"{domain}: W33 must contain Mon-Thu only")
        by_id = {week["weekId"]: week for week in summary["weeks"]}
        left, right = (by_id[week_id] for week_id in comparisons[domain])
        recovered = sum(right["indexes"][key] > left["indexes"][key] for key in DOMAIN_INDEXES[domain])
        check(recovered >= 4, f"{domain}: default comparison must recover in at least four indexes")


def main():
    validate_life()
    validate_attention()
    validate_attention_showcase()
    validate_emotion()
    validate_showcase_domains()
    validate_public_boundary()
    if ERRORS:
        print("Demo data validation failed:")
        print("\n".join(f"- {error}" for error in ERRORS))
        return 1
    print("Demo data validation passed: life, emotion and three showcase domains; 6 attention tasks × 24 weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
