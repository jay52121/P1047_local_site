#!/usr/bin/env python3
"""Validate the static SISP demo package and its cross-file calculations."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path


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


def validate_public_boundary():
    for path in (ROOT / "data").rglob("*.json"):
        payload = path.read_text(encoding="utf-8")
        check('"sourceType": "real"' not in payload, f"{path.relative_to(ROOT)}: real data cannot be committed to public demo data")


def main():
    validate_life()
    validate_attention()
    validate_public_boundary()
    if ERRORS:
        print("Demo data validation failed:")
        print("\n".join(f"- {error}" for error in ERRORS))
        return 1
    print("Demo data validation passed: 40 life weeks, 6 attention tasks × 24 weeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
