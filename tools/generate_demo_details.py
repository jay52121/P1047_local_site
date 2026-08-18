#!/usr/bin/env python3
"""Deterministically build per-week demo evidence from canonical weekly summaries."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/demo"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clear_json(directory):
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.glob("*.json"):
        path.unlink()


def generate_life():
    summary = load(DATA / "P-1047/life/weekly-summary.json")
    output = DATA / "P-1047/life/weeks"
    clear_json(output)
    for week in summary["weeks"]:
        metrics = week["metrics"]
        write(output / f"{week['weekId']}.json", {
            "schemaVersion": "1.0",
            "personId": "P-1047",
            "domain": "life",
            "weekId": week["weekId"],
            "sourceType": "simulation",
            "representativeSession": {
                "sessionType": "sit_to_stand",
                "poseTemplate": "/pose/pose-sessions.html",
                "durationSec": round(metrics["transferCompletionSec"] + 3.2, 2),
                "parameters": {
                    "powerPhaseSec": metrics["powerPhaseSec"],
                    "handSupportRatePct": metrics["handSupportRatePct"],
                    "retryRatePct": metrics["retryRatePct"],
                    "stabilizationSec": metrics["standingStabilizationSec"],
                    "swayHeightPct": metrics["lateralSwayHeightPct"],
                },
            },
        })


def generate_attention():
    base = DATA / "C-2308/attention"
    for summary_path in sorted(base.glob("*-weekly-summary.json")):
        summary = load(summary_path)
        task_id = summary["taskId"]
        output = base / "weeks" / task_id
        clear_json(output)
        for week in summary["weeks"]:
            first = week["metrics"]["firstDistractionMin"]
            duration = 30.0
            prompt = min(duration - 1, round(first + 1.2, 2))
            recovery = min(duration, round(prompt + .8, 2))
            write(output / f"{week['weekId']}.json", {
                "schemaVersion": "1.0",
                "personId": "C-2308",
                "domain": "attention",
                "taskId": task_id,
                "weekId": week["weekId"],
                "sourceType": "simulation",
                "representativeSession": {
                    "durationMin": duration,
                    "segments": [
                        {"startMin": 0, "endMin": first, "state": "focused"},
                        {"startMin": first, "endMin": recovery, "state": "distracted"},
                        {"startMin": recovery, "endMin": duration, "state": "focused"},
                    ],
                    "events": [
                        {"minute": first, "type": "distraction", "order": 1},
                        {"minute": prompt, "type": "prompt"},
                        {"minute": recovery, "type": "recovery"},
                        {"minute": duration, "type": "completion"},
                    ],
                },
            })


def main():
    generate_life()
    generate_attention()
    print("Generated 40 life details and 6 attention tasks × 24 details")


if __name__ == "__main__":
    main()
