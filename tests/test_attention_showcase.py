import unittest

from tools.demo_generation.attention_showcase import generate_attention_showcase


class AttentionShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.summary, self.details = generate_attention_showcase()

    def test_deterministic_24_week_session_data(self):
        self.assertEqual((self.summary, self.details), generate_attention_showcase())
        self.assertEqual(24, len(self.summary["weeks"]))
        self.assertTrue(all(4 <= week["validSessions"] <= 10 for week in self.summary["weeks"]))

    def test_tasks_have_real_duration_and_distraction_variation(self):
        by_task = {}
        for detail in self.details.values():
            for session in detail["sessions"]:
                row = by_task.setdefault(session["taskId"], {"duration": set(), "distraction": set()})
                row["duration"].add(session["durationMin"])
                row["distraction"].add(session["result"]["distractionCount"])
                cursor = 0
                for segment in session["segments"]:
                    self.assertAlmostEqual(cursor, segment["startMin"], places=3)
                    cursor = segment["endMin"]
                self.assertAlmostEqual(cursor, session["durationMin"], places=3)
        for row in by_task.values():
            self.assertGreater(len(row["duration"]), 5)
            self.assertTrue({0, 1}.issubset(row["distraction"]))
            self.assertTrue(any(value >= 2 for value in row["distraction"]))

    def test_pressure_and_recovery_story_is_visible(self):
        weeks = {week["weekId"]: week for week in self.summary["weeks"]}
        self.assertGreaterEqual(sum(weeks["2026-W20"]["indexes"][key] < weeks["2026-W13"]["indexes"][key] for key in weeks["2026-W20"]["indexes"]), 4)
        self.assertGreaterEqual(sum(weeks["2026-W28"]["indexes"][key] > weeks["2026-W20"]["indexes"][key] for key in weeks["2026-W20"]["indexes"]), 4)


if __name__ == "__main__":
    unittest.main()
