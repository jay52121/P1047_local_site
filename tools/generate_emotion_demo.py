#!/usr/bin/env python3
import json
from pathlib import Path

from demo_generation.emotion import build_emotion_dataset
from demo_generation.scenario import build_scenario


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/demo/P-1047/emotion"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    details, summary = build_emotion_dataset(build_scenario())
    for detail in details:
        write_json(BASE / "weeks" / f"{detail['weekId']}.json", detail)
    write_json(BASE / "weekly-summary.json", summary)
    print(f"Generated {len(details)} emotion weeks")


if __name__ == "__main__":
    main()
