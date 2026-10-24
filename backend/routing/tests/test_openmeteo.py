from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from routing.clients import openmeteo


def _ok_payload(lat: float, lon: float) -> dict:
    return {
        "latitude": lat,
        "longitude": lon,
        "hourly": {
            "time": ["2026-10-24T00:00"],
            "wind_speed_10m": [10.0],
            "precipitation": [0.0],
            "snowfall": [0.0],
            "temperature_2m": [25.0],
        },
    }


class FetchHourlyWeatherTests(SimpleTestCase):
    @patch("routing.clients.openmeteo.httpx.Client")
    def test_dedupes_near_identical_points(self, client_cls):
        client = MagicMock()
        client_cls.return_value.__enter__.return_value = client
        client.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                _ok_payload(6.454, 3.390),
                _ok_payload(9.074, 7.476),
            ],
            text="ok",
            headers={},
        )

        points = [
            (3.38975, 6.453928),
            (3.38980, 6.453900),  # same 3-decimal key
            (7.475731, 9.073523),
        ]
        series = openmeteo.fetch_hourly_weather(points, forecast_days=1)
        self.assertEqual(len(series), 3)
        # Two unique keys → one multi-location request, not three.
        self.assertEqual(client.get.call_count, 1)
        params = client.get.call_args.kwargs["params"]
        self.assertEqual(params["latitude"].count(","), 1)

    @patch("routing.clients.openmeteo.time.sleep", return_value=None)
    @patch("routing.clients.openmeteo.httpx.Client")
    def test_retries_on_429_then_succeeds(self, client_cls, _sleep):
        client = MagicMock()
        client_cls.return_value.__enter__.return_value = client
        limited = MagicMock(
            status_code=429,
            text="Rate limited",
            headers={"Retry-After": "0"},
            json=lambda: {},
        )
        ok = MagicMock(
            status_code=200,
            json=lambda: _ok_payload(6.45, 3.39),
            text="ok",
            headers={},
        )
        client.get.side_effect = [limited, ok]

        series = openmeteo.fetch_hourly_weather([(3.39, 6.45)], forecast_days=1)
        self.assertEqual(len(series), 1)
        self.assertEqual(client.get.call_count, 2)
