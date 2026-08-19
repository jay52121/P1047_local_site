import unittest
from math import sqrt

from tools.demo_generation.attention_showcase import (
    attention_realism_stats,
    generate_attention_showcase,
    validate_attention_schedule_realism,
)


class AttentionShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.summary, self.details = generate_attention_showcase()

    def test_deterministic_24_week_session_data(self):
        self.assertEqual((self.summary, self.details), generate_attention_showcase())
        self.assertEqual(24, len(self.summary["weeks"]))
        self.assertTrue(all(9 <= week["validSessions"] <= 20 for week in self.summary["weeks"]))

    def test_schedule_matches_child_routine_constraints(self):
        self.assertEqual([], validate_attention_schedule_realism(self.summary, self.details))
        stats = attention_realism_stats(self.summary, self.details)
        self.assertEqual(366, stats["totalSessions"])
        self.assertEqual(113, stats["taskSessions"]["homework"])
        self.assertEqual((142, 16, 7, 3), (stats["taskDays"], stats["restDays"], stats["unobservedDays"], stats["invalidDays"]))
        self.assertGreater(stats["naturalMinuteRate"], .9)

    def test_sessions_do_not_overlap_and_repeated_homework_has_semantics(self):
        for detail in self.details.values():
            by_date = {}
            for session in detail["sessions"]:
                by_date.setdefault(session["date"], []).append(session)
            for sessions in by_date.values():
                sessions.sort(key=lambda session: session["startTime"])
                for left, right in zip(sessions, sessions[1:]):
                    self.assertLessEqual(left["endTime"], right["startTime"])
                homework = [session for session in sessions if session["taskId"] == "homework"]
                if len(homework) > 1:
                    self.assertEqual(len(homework), len({(session["subject"], session["sessionRole"]) for session in homework}))

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

    def test_day_summaries_and_real_times_are_recomputable(self):
        for detail in self.details.values():
            self.assertEqual(7, len(detail["daySummaries"]))
            for session in detail["sessions"]:
                hour, minute = map(int, session["startTime"].split(":"))
                end = hour * 60 + minute + round(session["durationMin"])
                self.assertEqual(f"{end // 60:02d}:{end % 60:02d}", session["endTime"])
            for day in detail["daySummaries"]:
                sessions = [next(item for item in detail["sessions"] if item["sessionId"] == session_id) for session_id in day["sessionIds"]]
                if not sessions:
                    self.assertIn(day["dayBand"], {"no_task", "rest_day", "unobserved", "invalid"})
                    continue
                weights = [sqrt(session["durationMin"]) for session in sessions]
                mean = sum(session["sessionScore"] * weight for session, weight in zip(sessions, weights)) / sum(weights)
                expected = .8 * mean + .2 * min(session["sessionScore"] for session in sessions)
                self.assertAlmostEqual(expected, day["dayScore"], places=3)
                self.assertIn(day["representativeSessionId"], day["sessionIds"])
            counts = detail["weekDaySummary"]
            self.assertEqual(counts["poorDays"], sum(day["dayBand"] == "poor" for day in detail["daySummaries"]))


if __name__ == "__main__":
    unittest.main()
