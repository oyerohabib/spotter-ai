from unittest.mock import patch

from django.test import SimpleTestCase

from routing.services import AnalyzeError, analyze_routes


class AnalyzeValidationTests(SimpleTestCase):
    def test_requires_origin(self):
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes({"origin": "", "destination": "Chicago"})
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.field, "origin")

    def test_interval_must_be_allowed(self):
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes(
                {
                    "origin": "Chicago, IL",
                    "destination": "Detroit, MI",
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": 20000,
                    "sample_interval_miles": 15,
                }
            )
        self.assertEqual(ctx.exception.field, "sample_interval_miles")

    def test_load_must_be_number(self):
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes(
                {
                    "origin": "Chicago, IL",
                    "destination": "Detroit, MI",
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": "heavy",
                    "sample_interval_miles": 25,
                }
            )
        self.assertEqual(ctx.exception.field, "load_weight_lb")

    def test_same_coords_rejected(self):
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes(
                {
                    "origin": "Chicago, IL",
                    "destination": "Chicago Loop",
                    "origin_lon": -87.6298,
                    "origin_lat": 41.8781,
                    "destination_lon": -87.6298,
                    "destination_lat": 41.8781,
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": 20000,
                    "sample_interval_miles": 25,
                }
            )
        self.assertEqual(ctx.exception.field, "destination")

    @patch("routing.services.mapbox.geocode")
    def test_geocode_miss_maps_to_friendly_field_error(self, geocode_mock):
        from routing.clients.mapbox import MapboxError

        geocode_mock.side_effect = MapboxError("No geocoding results for 'xyzzy'.")
        with self.assertRaises(AnalyzeError) as ctx:
            analyze_routes(
                {
                    "origin": "xyzzy",
                    "destination": "Detroit, MI",
                    "departure_at": "2026-06-01T12:00:00Z",
                    "load_weight_lb": 20000,
                    "sample_interval_miles": 25,
                }
            )
        self.assertEqual(ctx.exception.field, "origin")
        self.assertIn("couldn’t find", str(ctx.exception).lower())
