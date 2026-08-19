import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from demo_generation.aggregation import cognition_session_result, effective_category_count, exposure_rate, pooled_ratio_pct
from demo_generation.common import mad, median
from demo_generation.metric_specs import DOMAIN_INDEXES, INDEX_SPECS, RAW_METRICS
from demo_generation.normalization import build_baseline_scale, normalize_value
from demo_generation.quality import continuity_pct, coverage_pct, unit_quality, week_confidence
from demo_generation.scenario import build_scenario


FIXTURE = json.loads((ROOT / "tests/fixtures/calculation-golden.json").read_text(encoding="utf-8"))


class GoldenFormulaTests(unittest.TestCase):
    def test_emotion_golden(self):
        days = FIXTURE["emotion"]["days"]
        expected = FIXTURE["emotion"]["expected"]
        actual = {
            "activeRatePct": pooled_ratio_pct([day["activeMin"] for day in days], [day["observedAwakeMin"] for day in days]),
            "initiativeEventsPer8h": exposure_rate(sum(day["selfStarts"] for day in days), sum(day["observedAwakeMin"] for day in days)),
            "selfInitiatedSharePct": pooled_ratio_pct([day["selfStarts"] for day in days], [day["allStarts"] for day in days]),
            "interestOpportunityAcceptancePct": pooled_ratio_pct([day["interestAccepted"] for day in days], [day["interestOpportunities"] for day in days]),
            "interestEngagementPct": pooled_ratio_pct([day["interestEngagedMin"] for day in days], [day["interestOpportunityMin"] for day in days]),
            "responseRatePct": pooled_ratio_pct([day["socialResponded"] for day in days], [day["socialOpportunities"] for day in days]),
            "responseLatencySec": median(value for day in days for value in day["responseLatenciesSec"]),
            "longStillRatePct": pooled_ratio_pct([day["longStillMin"] for day in days], [day["observedAwakeMin"] for day in days]),
            "medianLowActivityEpisodeMin": median(value for day in days for value in day["lowActivityEpisodesMin"]),
        }
        for key, expected_value in expected.items():
            self.assertAlmostEqual(actual[key], expected_value, places=8, msg=key)

    def test_cognition_golden(self):
        actual = cognition_session_result(FIXTURE["cognition"]["session"])
        for key, expected_value in FIXTURE["cognition"]["expected"].items():
            if isinstance(expected_value, bool):
                self.assertEqual(actual[key], expected_value)
            else:
                self.assertAlmostEqual(actual[key], expected_value, places=8, msg=key)

    def test_sleep_golden(self):
        nights = FIXTURE["sleep"]["nights"]
        expected = FIXTURE["sleep"]["expected"]
        actual = {
            "sleepContinuityPct": pooled_ratio_pct([night["estimatedSleepMin"] for night in nights], [night["sleepWindowMin"] for night in nights]),
            "awakeningsPerNight": sum(night["awakenings"] for night in nights) / len(nights),
            "outOfBedMinPerNight": sum(night["outOfBedMin"] for night in nights) / len(nights),
        }
        for key, expected_value in expected.items():
            self.assertAlmostEqual(actual[key], expected_value, places=8, msg=key)

    def test_participation_entropy_golden(self):
        actual = effective_category_count(FIXTURE["participation"]["zoneMinutes"])
        self.assertAlmostEqual(actual, FIXTURE["participation"]["expectedEffectiveZoneCount"], places=8)


class KernelRuleTests(unittest.TestCase):
    def test_robust_baseline_uses_median_mad_and_floor(self):
        scale = build_baseline_scale([10, 10, 10, 11, 50], 5)
        self.assertEqual(scale.center, 10)
        self.assertEqual(scale.robust_scale, 0)
        self.assertEqual(scale.scale, 5)
        self.assertEqual(normalize_value(15, scale, "higher"), 110)
        self.assertEqual(normalize_value(15, scale, "lower"), 90)
        self.assertEqual(normalize_value(15, scale, "burden"), 110)

    def test_quality_is_observability_only(self):
        quality = unit_quality(600, 720, [10, 45], 1020, 100)
        self.assertAlmostEqual(quality.coverage_pct, 83.3333333333, places=8)
        self.assertAlmostEqual(quality.continuity_pct, 97.0588235294, places=8)
        self.assertAlmostEqual(quality.confidence_pct, 90.7843137255, places=8)
        units = [{"valid": True, "observedMinutes": 600, "quality": {"confidencePct": quality.confidence_pct}}]
        self.assertAlmostEqual(week_confidence(units, 2), 80.5882352941, places=8)

    def test_specs_have_four_domains_and_five_indexes(self):
        self.assertEqual(set(DOMAIN_INDEXES), {"emotion", "cognition", "sleep", "participation"})
        for indexes in DOMAIN_INDEXES.values():
            self.assertEqual(len(indexes), 5)
            for key in indexes:
                self.assertIn(key, INDEX_SPECS)
                for component in INDEX_SPECS[key].components:
                    self.assertIn(component.raw_metric, RAW_METRICS)

    def test_scenario_has_fixed_worldline_and_provisional_week(self):
        scenario = build_scenario()
        self.assertEqual(len(scenario), 40)
        self.assertEqual(scenario[0].week_id, "2025-W46")
        self.assertEqual(scenario[-1].week_id, "2026-W33")
        self.assertEqual(scenario[-1].status, "in_progress")
        self.assertEqual(scenario[-1].observed_through_date, "2026-08-13")
        events = {week.week_id: week.event.kind for week in scenario if week.event}
        self.assertEqual(events["2026-W06"], "external")
        self.assertEqual(events["2026-W08"], "intervention")
        self.assertEqual(events["2026-W22"], "external")
        self.assertEqual(events["2026-W33"], "data_status")
        heat = next(week for week in scenario if week.week_id == "2026-W22")
        self.assertGreater(heat.burdens["participation"], heat.burdens["emotion"])
        self.assertGreater(heat.burdens["emotion"], heat.burdens["cognition"])


if __name__ == "__main__":
    unittest.main()
