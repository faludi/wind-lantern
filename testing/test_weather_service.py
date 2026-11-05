import unittest
from types import SimpleNamespace

from weather_service import fetch_current_wind, format_weather_timestamp


class FakeClient:
    def __init__(self, forecast=None, error=None):
        self.forecast = forecast
        self.error = error
        self.call = None

    def get_weather(self, *args, **kwargs):
        self.call = (args, kwargs)
        if self.error is not None:
            raise self.error
        return self.forecast


class FakeWatchdog:
    def __init__(self):
        self.feed_count = 0

    def feed(self):
        self.feed_count += 1


class WeatherServiceTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient({"wind_speed_10m": 10, "wind_gusts_10m": 20})
        self.watchdog = FakeWatchdog()
        self.clock = SimpleNamespace(gmtime=lambda: (2026, 11, 5, 21, 30, 0, 0, 0))

    def test_fetch_returns_kph_mps_and_timestamp(self):
        reading = fetch_current_wind(self.client, self.watchdog, self.clock)

        self.assertEqual(self.client.call, (
            ("current", "wind_speed_10m,wind_gusts_10m"),
            {"forecast_days": 1, "expiry": 300},
        ))
        self.assertEqual(reading["wind_speed_kph"], 10)
        self.assertEqual(reading["wind_gusts_kph"], 20)
        self.assertAlmostEqual(reading["wind_speed_mps"], 2.7778)
        self.assertAlmostEqual(reading["wind_gusts_mps"], 5.5556)
        self.assertEqual(reading["timestamp"], "2026-11-05T21:30")
        self.assertEqual(self.watchdog.feed_count, 1)

    def test_empty_forecast_returns_none(self):
        self.client.forecast = None

        self.assertIsNone(fetch_current_wind(self.client, self.watchdog, self.clock))

    def test_request_error_returns_none_and_reports_error(self):
        self.client.error = OSError("network unavailable")
        messages = []

        reading = fetch_current_wind(
            self.client,
            self.watchdog,
            self.clock,
            output=lambda *message: messages.append(message),
        )

        self.assertIsNone(reading)
        self.assertEqual(messages, [("Error fetching weather data:", self.client.error)])

    def test_timestamp_formats_as_utc_display_time(self):
        self.assertEqual(
            format_weather_timestamp("2026-11-05T07:04"),
            "11/05/2026 07:04 UTC",
        )


if __name__ == "__main__":
    unittest.main()
