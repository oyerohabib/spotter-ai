from datetime import datetime, timezone

from django.test import SimpleTestCase

from routing.sampling import haversine_miles, interpolate_along_line, sample_checkpoints


class SamplingTests(SimpleTestCase):
    def test_haversine_known_distance(self):
        # Roughly Chicago to a point ~10 miles east
        miles = haversine_miles(-87.6298, 41.8781, -87.4298, 41.8781)
        self.assertAlmostEqual(miles, 10.3, delta=0.5)

    def test_interpolate_midpoint(self):
        coords = [[0.0, 0.0], [0.0, 1.0]]  # ~69 miles north
        total = haversine_miles(0, 0, 0, 1)
        mid = interpolate_along_line(coords, total / 2)
        assert mid is not None
        lon, lat, miles = mid
        self.assertAlmostEqual(lon, 0.0, places=5)
        self.assertAlmostEqual(lat, 0.5, delta=0.01)
        self.assertAlmostEqual(miles, total / 2, places=5)

    def test_sample_includes_start_and_end(self):
        coords = [[-87.6298, 41.8781], [-87.0, 41.8781], [-86.5, 41.8781]]
        departure = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        checkpoints = sample_checkpoints(
            coords,
            interval_miles=25,
            total_duration_seconds=7200,
            departure_at=departure,
            total_distance_miles=60,
        )
        self.assertEqual(checkpoints[0]["miles_from_origin"], 0.0)
        self.assertEqual(checkpoints[-1]["miles_from_origin"], 60.0)
        self.assertEqual(checkpoints[0]["eta"], departure.isoformat())
        # Mid checkpoints at 25 and 50
        miles = [c["miles_from_origin"] for c in checkpoints]
        self.assertIn(25.0, miles)
        self.assertIn(50.0, miles)
