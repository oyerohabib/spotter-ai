from django.test import SimpleTestCase

from routing.recommend import recommend_route, summarize_route_risk


class RecommendTests(SimpleTestCase):
    def test_summarize_mile_bands(self):
        checkpoints = [
            {"miles_from_origin": 0, "risk": "Low"},
            {"miles_from_origin": 10, "risk": "High"},
            {"miles_from_origin": 30, "risk": "Severe"},
            {"miles_from_origin": 40, "risk": "Low"},
        ]
        summary = summarize_route_risk(checkpoints)
        self.assertEqual(summary["high_miles"], 20.0)  # 10→30 owned by High
        self.assertEqual(summary["severe_miles"], 10.0)  # 30→40 owned by Severe
        self.assertEqual(summary["max_risk"], "Severe")
        self.assertGreater(summary["average_risk"], 0)

    def test_prefer_fewest_severe_miles(self):
        routes = [
            {
                "id": "a",
                "duration_seconds": 1000,
                "summary": {
                    "severe_miles": 20,
                    "high_miles": 0,
                    "average_risk": 1.0,
                },
            },
            {
                "id": "b",
                "duration_seconds": 3000,
                "summary": {
                    "severe_miles": 5,
                    "high_miles": 40,
                    "average_risk": 2.0,
                },
            },
        ]
        best_id, reason = recommend_route(routes)
        self.assertEqual(best_id, "b")
        self.assertIn("severe", reason.lower())

    def test_tie_break_on_time(self):
        routes = [
            {
                "id": "slow",
                "duration_seconds": 5000,
                "summary": {"severe_miles": 0, "high_miles": 0, "average_risk": 1.0},
            },
            {
                "id": "fast",
                "duration_seconds": 2000,
                "summary": {"severe_miles": 0, "high_miles": 0, "average_risk": 1.0},
            },
        ]
        best_id, _ = recommend_route(routes)
        self.assertEqual(best_id, "fast")
