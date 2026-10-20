from django.test import SimpleTestCase

from routing.services import AnalyzeError, analyze_routes


class AnalyzeValidationTests(SimpleTestCase):
    def test_requires_origin_destination(self):
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes({"origin": "", "destination": "Chicago"})
        self.assertEqual(ctx.exception.status, 400)

    def test_interval_must_be_allowed(self):
        with self.assertRaises(AnalyzeError):
            analyze_routes(
                {
                    "origin": "Chicago, IL",
                    "destination": "Detroit, MI",
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": 20000,
                    "sample_interval_miles": 15,
                }
            )

    def test_load_must_be_number(self):
        with self.assertRaises(AnalyzeError):
            analyze_routes(
                {
                    "origin": "Chicago, IL",
                    "destination": "Detroit, MI",
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": "heavy",
                    "sample_interval_miles": 25,
                }
            )
