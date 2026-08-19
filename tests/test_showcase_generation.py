import hashlib
import json
from pathlib import Path

from tools.demo_generation.scenario import build_scenario
from tools.demo_generation.showcase import ANCHORS, generate_cognition, generate_participation, generate_sleep


ROOT = Path(__file__).resolve().parents[1]
BUILDERS = {"cognition": generate_cognition, "sleep": generate_sleep, "participation": generate_participation}
PAIRS = {"cognition": ("2026-W06", "2026-W16"), "sleep": ("2026-W06", "2026-W16"), "participation": ("2026-W22", "2026-W29")}


def test_showcase_domains_are_deterministic_and_sparse():
    scenario = build_scenario()
    for domain, builder in BUILDERS.items():
        first = builder(scenario)
        second = builder(scenario)
        assert first == second
        summary, evidence, full = first
        assert len(summary["weeks"]) == 40
        assert len(evidence["weeks"]) == 40
        assert set(full) == ANCHORS[domain]
        current = next(week for week in evidence["weeks"] if week["weekId"] == "2026-W33")
        units = current.get("sessions") or current.get("nights") or current.get("days")
        assert len(units) == 4


def test_default_demo_comparisons_show_recovery():
    scenario = build_scenario()
    for domain, builder in BUILDERS.items():
        summary, _, _ = builder(scenario)
        weeks = {week["weekId"]: week for week in summary["weeks"]}
        left, right = (weeks[week_id] for week_id in PAIRS[domain])
        assert all(value is not None for value in left["indexes"].values())
        assert all(value is not None for value in right["indexes"].values())
        assert sum(right["indexes"][key] > left["indexes"][key] for key in left["indexes"]) >= 4


def test_protected_demo_assets_are_unchanged():
    protected = {
        "data/demo/P-1047/life/weekly-summary.json": "85856cb861a94e4f82ed88690c579cc56ca913f46b00cb53a2739e40c7722904",
        "pose/pose-sessions.html": "62cfce819783841db5668f72d77e981de459b3f861bf7a46d58b7566bf5058d9",
    }
    for relative, expected in protected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    attention = hashlib.sha256()
    attention_root = ROOT / "data/demo/C-2308/attention"
    v1_files = list(attention_root.glob("*-weekly-summary.json")) + [path for directory in attention_root.glob("weeks/*") if directory.is_dir() for path in directory.glob("*.json")]
    for path in sorted(v1_files):
        attention.update(path.relative_to(ROOT).as_posix().encode())
        attention.update(path.read_bytes())
    assert attention.hexdigest() == "42ae22762243f87aa7d508fcfcd2b68c743153d129e71c8f2827c9a942b0c72a"


def test_checked_in_showcase_data_matches_generator():
    scenario = build_scenario()
    for domain, builder in BUILDERS.items():
        summary, evidence, full = builder(scenario)
        base = ROOT / "data/demo/P-1047" / domain
        assert json.loads((base / "weekly-summary.json").read_text()) == summary
        assert json.loads((base / "evidence-lite.json").read_text()) == evidence
        for week_id, detail in full.items():
            assert json.loads((base / "weeks" / f"{week_id}.json").read_text()) == detail
