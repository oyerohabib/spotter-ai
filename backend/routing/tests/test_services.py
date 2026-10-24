from unittest.mock import patch

from django.test import SimpleTestCase

from routing.services import AnalyzeError, plan_routes, score_routes


class PlanValidationTests(SimpleTestCase):
    def test_requires_origin(self):
        with self.assertRaises(AnalyzeError) as ctx:
            plan_routes({"origin": "", "destination": "Chicago"})
        self.assertEqual(ctx.exception.status, 400)
        self.assertEqual(ctx.exception.field, "origin")

    def test_interval_must_be_allowed(self):
        with self.assertRaises(AnalyzeError) as ctx:
            plan_routes(
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
            plan_routes(
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
            plan_routes(
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
            plan_routes(
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


class ScoreRoutesTests(SimpleTestCase):
    def _minimal_plan(self, *, checkpoints=1, heatmap_points=1):
        cps = [
            {
                "index": i,
                "lon": -87.6 + i * 0.1,
                "lat": 41.8,
                "miles_from_origin": float(i * 25),
                "eta": f"2026-06-01T{12 + i:02d}:00:00+00:00",
            }
            for i in range(checkpoints)
        ]
        hm = [
            {
                "lon": -87.5 + i * 0.1,
                "lat": 41.9,
                "miles_from_origin": float(i * 25),
            }
            for i in range(heatmap_points)
        ]
        return {
            "origin": {"query": "A", "name": "A", "lon": -87.6, "lat": 41.8},
            "destination": {"query": "B", "name": "B", "lon": -83.0, "lat": 42.3},
            "departure_at": "2026-06-01T12:00:00+00:00",
            "load_weight_lb": 20000,
            "sample_interval_miles": 25,
            "routes": [
                {
                    "id": "route-1",
                    "distance_miles": 100,
                    "duration_seconds": 7200,
                    "duration_minutes": 120,
                    "geometry": {"type": "LineString", "coordinates": [[-87.6, 41.8]]},
                    "checkpoints": cps,
                }
            ],
            "heatmap": {"hours": 48, "points": hm},
        }

    def _series(self):
        return {
            "times": ["2026-06-01T12:00", "2026-06-01T13:00"],
            "wind_mph": [10.0, 12.0],
            "precip_in": [0.0, 0.0],
            "snowfall": [0.0, 0.0],
            "temp_c": [20.0, 21.0],
        }

    def test_score_requires_matching_series_length(self):
        plan = self._minimal_plan()
        with self.assertRaises(AnalyzeError) as ctx:
            score_routes({"plan": plan, "weather_series": [self._series()]})
        self.assertEqual(ctx.exception.field, "weather_series")

    def test_score_attaches_weather_and_recommendation(self):
        plan = self._minimal_plan(checkpoints=1, heatmap_points=1)
        series = [self._series(), self._series()]
        result = score_routes({"plan": plan, "weather_series": series})
        self.assertEqual(result["recommended_route_id"], "route-1")
        cp = result["routes"][0]["checkpoints"][0]
        self.assertIn("weather", cp)
        self.assertIn("risk", cp)
        self.assertEqual(len(result["heatmap"]["points"]), 1)
        self.assertTrue(result["heatmap"]["points"][0]["hourly"])
