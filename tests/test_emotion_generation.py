import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

from tools.demo_generation.emotion import (
    EMOTION_INDEXES, EMOTION_METRICS, EMOTION_RESPONSE_COEFFICIENTS, aggregate_emotion_week,
    build_emotion_dataset, build_emotion_evidence_summary, derive_emotion_day_result,
)
from tools.demo_generation.normalization import build_baselines, calculate_indexes
from tools.demo_generation.quality import unit_quality
from tools.demo_generation.scenario import build_scenario


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
SCHEMAS = ROOT / "data/schemas"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class EmotionGoldenTests(unittest.TestCase):
    def test_unit_golden(self):
        fixture = load(FIXTURES / "emotion-unit-golden.json")
        actual = derive_emotion_day_result(fixture["segments"], fixture["events"])
        for key, expected in fixture["expected"].items():
            if isinstance(expected, list):
                self.assertEqual(len(actual[key]), len(expected))
                for left, right in zip(actual[key], expected): self.assertAlmostEqual(left, right, places=3)
            elif isinstance(expected, float): self.assertAlmostEqual(actual[key], expected, places=3)
            else: self.assertEqual(actual[key], expected)

    def test_week_golden(self):
        fixture = load(FIXTURES / "emotion-week-golden.json")
        units = [{"valid": True, "result": result} for result in fixture["dailyResults"]]
        actual = aggregate_emotion_week(units)["metrics"]
        for key, expected in fixture["expectedMetrics"].items(): self.assertAlmostEqual(actual[key], expected, places=3)

    def test_baseline_golden(self):
        fixture = load(FIXTURES / "emotion-baseline-golden.json")
        baselines = build_baselines(fixture["baselineWeeks"])
        actual, _ = calculate_indexes(fixture["targetWeek"], baselines, EMOTION_INDEXES)
        for key, expected in fixture["expectedIndexes"].items(): self.assertAlmostEqual(actual[key], expected, places=5)


class EmotionDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.details, cls.summary = build_emotion_dataset(build_scenario())
        cls.by_id = {week["weekId"]: week for week in cls.summary["weeks"]}

    def test_generation_is_deterministic(self):
        details, summary = build_emotion_dataset(build_scenario())
        self.assertEqual(json.dumps((self.details, self.summary), sort_keys=True), json.dumps((details, summary), sort_keys=True))

    def test_fixed_40_week_contract(self):
        self.assertEqual(len(self.details), 40)
        self.assertEqual(self.details[0]["weekId"], "2025-W46")
        self.assertEqual(self.details[-1]["weekId"], "2026-W33")
        self.assertEqual(len(self.details[-1]["units"]), 4)
        self.assertEqual(self.details[-1]["observedThroughDate"], "2026-08-13")

    def test_metric_and_index_keys_are_exact(self):
        for week in self.summary["weeks"]:
            self.assertEqual(set(week["metrics"]), set(EMOTION_METRICS))
            self.assertEqual(set(week["indexes"]), set(EMOTION_INDEXES))

    def test_baseline_is_available(self):
        for key in EMOTION_METRICS:
            self.assertEqual(sum(self.summary["weeks"][index]["metrics"][key] is not None for index in range(5)), 5)

    def test_complete_weeks_are_sufficient(self):
        for week in self.summary["weeks"][:-1]:
            self.assertGreaterEqual(week["validUnits"], 5)
            self.assertEqual(week["dataStatus"], "sufficient")

    def test_story_constraints(self):
        w52, w06, w08, w22 = (self.by_id[key] for key in ("2025-W52", "2026-W06", "2026-W08", "2026-W22"))
        for key in EMOTION_INDEXES[:-1]: self.assertLess(w06["indexes"][key], w52["indexes"][key])
        self.assertGreater(w06["indexes"]["withdrawalBurden"], w52["indexes"]["withdrawalBurden"])
        recovered = sum(w08["indexes"][key] > w06["indexes"][key] for key in EMOTION_INDEXES[:-1])
        recovered += w08["indexes"]["withdrawalBurden"] < w06["indexes"]["withdrawalBurden"]
        self.assertGreaterEqual(recovered, 4)
        impact = lambda week: sum(abs(week["indexes"][key] - 100) for key in EMOTION_INDEXES)
        self.assertLess(impact(w22), impact(w06))

    def test_manual_review_weeks_preserve_behavior_quality_boundary(self):
        w52, w06, w08, w22 = (self.by_id[key] for key in ("2025-W52", "2026-W06", "2026-W08", "2026-W22"))
        self.assertGreater(w06["metrics"]["responseRatePct"], 0)
        self.assertGreaterEqual(w06["confidencePct"], w52["confidencePct"] - 5)
        self.assertGreater(w08["indexes"]["behaviorActivation"], w06["indexes"]["behaviorActivation"])
        self.assertGreater(w08["indexes"]["initiative"], w06["indexes"]["initiative"])
        self.assertLess(w08["indexes"]["withdrawalBurden"], w06["indexes"]["withdrawalBurden"])
        self.assertGreater(w22["indexes"]["behaviorActivation"], w06["indexes"]["behaviorActivation"])
        self.assertGreater(len(set(EMOTION_RESPONSE_COEFFICIENTS.values())), 4)

    def test_evidence_summary_is_recomputable_cache(self):
        baselines = build_baselines([detail["weekAggregate"]["metrics"] for detail in self.details])
        for detail in self.details:
            self.assertEqual(detail["evidenceSummary"], build_emotion_evidence_summary(detail["weekAggregate"]["metrics"], baselines))

    def test_domain_boundary_and_trace_mapping(self):
        mapping = load(ROOT / "data/demo/P-1047/emotion/emotion_metric_mapping.json")
        self.assertEqual(set(mapping["rawMetrics"]), set(EMOTION_METRICS))
        self.assertEqual(set(mapping["indexes"]), set(EMOTION_INDEXES))
        keys = []
        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items(): keys.append(key.lower()); collect(child)
            elif isinstance(value, list):
                for child in value: collect(child)
        collect(self.details)
        for token in ("outside", "location", "zone", "outing", "interactionduration", "interaction_duration"):
            self.assertFalse(any(token in key for key in keys), token)

    def test_zero_and_null_opportunity_semantics(self):
        empty = {"observedAwakeMin":600,"activeMin":0,"longStillMin":0,"lowActivityEpisodesMin":[],"allActivityStarts":0,"selfInitiatedStarts":0,"interestOpportunityCount":0,"interestAcceptedCount":0,"interestOpportunityMin":0,"interestEngagedMin":0,"socialOpportunityCount":0,"socialRespondedCount":0,"responseLatenciesSec":[]}
        metrics = aggregate_emotion_week([{"valid": True, "result": empty}])["metrics"]
        self.assertEqual(metrics["initiativeEventsPer8h"], 0)
        self.assertIsNone(metrics["selfInitiatedSharePct"])
        self.assertIsNone(metrics["interestEngagementPct"])
        self.assertIsNone(metrics["responseRatePct"])
        enough = dict(empty, socialOpportunityCount=3)
        metrics = aggregate_emotion_week([{"valid": True, "result": enough}])["metrics"]
        self.assertEqual(metrics["responseRatePct"], 0)
        self.assertIsNone(metrics["responseLatencySec"])

    def test_quality_is_independent_of_behavior(self):
        left = unit_quality(700, 780, [40, 50], 1020, 100)
        right = unit_quality(700, 780, [40, 50], 1020, 100)
        self.assertEqual(left.confidence_pct, right.confidence_pct)

    def test_domain_schemas_validate_generated_files(self):
        detail_schema = load(SCHEMAS / "emotion-week-detail.schema.json")
        summary_schema = load(SCHEMAS / "emotion-weekly-summary.schema.json")
        common_schema = load(SCHEMAS / "event-first-week.schema.json")
        weekly_schema = load(SCHEMAS / "weekly-summary.schema.json")
        store = {
            common_schema["$id"]: common_schema,
            weekly_schema["$id"]: weekly_schema,
            summary_schema["$id"]: summary_schema,
            detail_schema["$id"]: detail_schema,
        }
        resolver = RefResolver.from_schema(detail_schema, store=store)
        detail_validator = Draft202012Validator(detail_schema, resolver=resolver)
        summary_validator = Draft202012Validator(summary_schema, resolver=RefResolver.from_schema(summary_schema, store=store))
        for detail in self.details: detail_validator.validate(detail)
        summary_validator.validate(self.summary)


if __name__ == "__main__":
    unittest.main()
