from unittest.mock import patch

from django.test import SimpleTestCase

from routing.clients import mapbox


def _route(distance: float, duration: float, coords=None) -> dict:
    return {
        "distance_meters": distance,
        "duration_seconds": duration,
        "coordinates": coords or [[0.0, 0.0], [1.0, 1.0]],
    }


class GetRouteAlternativesTests(SimpleTestCase):
    origin = (-87.6298, 41.8781)
    destination = (-83.0458, 42.3314)

    @patch("routing.clients.mapbox._fetch_directions")
    def test_skips_fill_in_when_base_returns_three(self, fetch_mock):
        fetch_mock.return_value = [
            _route(400_000, 14_000),
            _route(420_000, 15_000),
            _route(450_000, 16_500),
        ]
        routes = mapbox.get_route_alternatives(self.origin, self.destination)
        self.assertEqual(len(routes), 3)
        self.assertEqual([r["id"] for r in routes], ["route-1", "route-2", "route-3"])
        self.assertEqual(fetch_mock.call_count, 1)

    @patch("routing.clients.mapbox._fetch_directions")
    def test_fills_to_three_when_base_returns_two(self, fetch_mock):
        base = [_route(400_000, 14_000), _route(420_000, 15_000)]
        fill = [_route(480_000, 18_000)]

        def side_effect(coords, *, alternatives=True, exclude=None, raise_on_error=True):
            if exclude == "motorway":
                return fill
            if exclude is None and coords.count(";") == 1:
                return base
            return []

        fetch_mock.side_effect = side_effect
        routes = mapbox.get_route_alternatives(self.origin, self.destination)
        self.assertEqual(len(routes), 3)
        distances = [r["distance_meters"] for r in routes]
        self.assertIn(480_000, distances)
        # Primary + motorway fill; stops once we have 3
        self.assertEqual(fetch_mock.call_count, 2)

    @patch("routing.clients.mapbox._fetch_directions")
    def test_rejects_near_duplicate_fill_in(self, fetch_mock):
        base = [_route(400_000, 14_000), _route(420_000, 15_000)]
        # Within 2% of first route — should be rejected
        near_dup = [_route(401_000, 14_050)]
        distinct = [_route(500_000, 20_000)]

        def side_effect(coords, *, alternatives=True, exclude=None, raise_on_error=True):
            if exclude == "motorway":
                return near_dup
            if exclude == "toll":
                return distinct
            if coords.count(";") >= 2:
                return []
            return base

        fetch_mock.side_effect = side_effect
        routes = mapbox.get_route_alternatives(self.origin, self.destination)
        self.assertEqual(len(routes), 3)
        distances = [r["distance_meters"] for r in routes]
        self.assertNotIn(401_000, distances)
        self.assertIn(500_000, distances)

    def test_routes_similar_within_tolerance(self):
        a = _route(100_000, 3_600)
        b = _route(101_000, 3_620)  # 1% / ~0.5%
        self.assertTrue(mapbox._routes_similar(a, b))
        c = _route(120_000, 4_000)  # clearly different
        self.assertFalse(mapbox._routes_similar(a, c))
