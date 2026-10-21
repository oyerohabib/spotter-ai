from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from routing.clients import mapbox
from routing.views import PlaceSuggestView


class SuggestPlacesClientTests(SimpleTestCase):
    @patch("routing.clients.mapbox._geocode_features")
    def test_suggest_maps_features(self, features_mock):
        features_mock.return_value = [
            {
                "id": "place.1",
                "place_name": "Chicago, Illinois, United States",
                "center": [-87.6298, 41.8781],
            }
        ]
        results = mapbox.suggest_places("Chi", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Chicago, Illinois, United States")
        self.assertEqual(results[0]["lon"], -87.6298)

    @patch("routing.clients.mapbox._geocode_features")
    def test_suggest_empty_list_when_no_matches(self, features_mock):
        features_mock.return_value = []
        self.assertEqual(mapbox.suggest_places("zzzzz"), [])


class PlaceSuggestViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = PlaceSuggestView.as_view()

    def test_rejects_short_query(self):
        request = self.factory.get("/api/places/suggest/", {"q": "a"})
        response = self.view(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn("2 characters", response.data["detail"])

    @patch("routing.views.mapbox.suggest_places")
    def test_returns_results(self, suggest_mock):
        suggest_mock.return_value = [
            {"id": "1", "name": "Detroit, MI", "lon": -83.0, "lat": 42.3}
        ]
        request = self.factory.get("/api/places/suggest/", {"q": "Det"})
        response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
