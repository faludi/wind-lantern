import json
import unittest

from lantern_config import (
    DEFAULT_SETTINGS,
    normalize_brightness,
    normalize_color_temperature,
    normalize_flicker_intensity,
    normalize_night_hour,
    normalize_night_brightness,
    normalize_settings,
    normalize_settings_update_interval,
    serialize_settings,
    settings_match,
)


class LanternConfigTests(unittest.TestCase):
    def test_normalizers_coerce_and_clamp_values(self):
        self.assertEqual(normalize_brightness("75"), 75)
        self.assertEqual(normalize_brightness(-1), 0)
        self.assertEqual(normalize_brightness(101), 100)
        self.assertEqual(normalize_night_brightness(30), 30)
        self.assertEqual(normalize_night_hour(-1), 0)
        self.assertEqual(normalize_night_hour(24), 23)
        self.assertEqual(normalize_color_temperature(-11), -10)
        self.assertEqual(normalize_color_temperature(11), 10)
        self.assertEqual(normalize_flicker_intensity(6), 5)
        self.assertEqual(normalize_settings_update_interval(0), 1)
        self.assertEqual(normalize_settings_update_interval(10081), 10080)

    def test_normalize_settings_uses_defaults_and_ignores_unknown_keys(self):
        settings = normalize_settings({"lantern_brightness": "42", "not_a_setting": 1})

        self.assertEqual(settings["lantern_brightness"], 42.0)
        self.assertEqual(settings["night_brightness"], DEFAULT_SETTINGS["night_brightness"])
        self.assertNotIn("not_a_setting", settings)

    def test_color_temperature_matches_integer_contract(self):
        settings = normalize_settings({"color_temperature": "4"})

        self.assertEqual(settings["color_temperature"], 4)
        self.assertIsInstance(settings["color_temperature"], int)

        fallback = DEFAULT_SETTINGS.copy()
        fallback["color_temperature"] = 3
        settings = normalize_settings({"color_temperature": "4.5"}, fallback)
        self.assertEqual(settings["color_temperature"], 3)

    def test_brightness_fields_match_integer_contract(self):
        settings = normalize_settings({
            "lantern_brightness": "42",
            "night_brightness": "18",
        })

        self.assertEqual(settings["lantern_brightness"], 42)
        self.assertIsInstance(settings["lantern_brightness"], int)
        self.assertEqual(settings["night_brightness"], 18)
        self.assertIsInstance(settings["night_brightness"], int)

        fallback = DEFAULT_SETTINGS.copy()
        fallback.update({"lantern_brightness": 35, "night_brightness": 12})
        settings = normalize_settings({
            "lantern_brightness": "42.5",
            "night_brightness": "18.5",
        }, fallback)
        self.assertEqual(settings["lantern_brightness"], 35)
        self.assertEqual(settings["night_brightness"], 12)

    def test_integer_settings_reject_fractional_remote_values(self):
        fallback = DEFAULT_SETTINGS.copy()
        fallback.update({
            "settings_update_interval": 30,
            "night_start": 20,
            "night_end": 7,
        })

        settings = normalize_settings({
            "settings_update_interval": 15.5,
            "night_start": 21.5,
            "night_end": 6.5,
        }, fallback)

        self.assertEqual(settings["settings_update_interval"], 30)
        self.assertEqual(settings["night_start"], 20)
        self.assertEqual(settings["night_end"], 7)

    def test_invalid_remote_values_preserve_supplied_fallbacks(self):
        fallback = DEFAULT_SETTINGS.copy()
        fallback.update({
            "night_brightness": 37,
            "night_start": 19,
            "night_end": 6,
        })

        settings = normalize_settings({
            "night_brightness": "invalid",
            "night_start": "invalid",
            "night_end": "invalid",
        }, fallback)

        self.assertEqual(settings["night_brightness"], 37)
        self.assertEqual(settings["night_start"], 19)
        self.assertEqual(settings["night_end"], 6)

    def test_settings_match_checks_known_fields_only(self):
        settings = DEFAULT_SETTINGS.copy()
        self.assertTrue(settings_match(dict(settings, extra="ignored"), settings))

        changed = settings.copy()
        changed["night_end"] = 9
        self.assertFalse(settings_match(settings, changed))

    def test_serialized_settings_round_trip(self):
        original = normalize_settings(DEFAULT_SETTINGS)
        restored = normalize_settings(json.loads(serialize_settings(original)))

        self.assertEqual(restored, original)


if __name__ == "__main__":
    unittest.main()