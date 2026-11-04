import json
import os
import tempfile
import unittest

from lantern_config import DEFAULT_SETTINGS
from settings_store import load_settings, save_settings


class SettingsStoreTests(unittest.TestCase):
    def test_missing_file_is_created_with_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")

            settings = load_settings(path)

            self.assertEqual(settings, DEFAULT_SETTINGS)
            with open(path, "r") as config_file:
                self.assertEqual(json.load(config_file), DEFAULT_SETTINGS)

    def test_existing_file_is_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w") as config_file:
                json.dump({"lantern_brightness": "42", "unknown": 1}, config_file)

            settings = load_settings(path)

            self.assertEqual(settings["lantern_brightness"], 42)
            self.assertEqual(settings["night_brightness"], DEFAULT_SETTINGS["night_brightness"])
            self.assertNotIn("unknown", settings)

    def test_malformed_file_falls_back_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            with open(path, "w") as config_file:
                config_file.write("{")

            settings = load_settings(path)

            self.assertEqual(settings, DEFAULT_SETTINGS)
            with open(path, "r") as config_file:
                self.assertEqual(config_file.read(), "{")

    def test_save_skips_unchanged_settings_and_writes_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "config.json")
            settings = DEFAULT_SETTINGS.copy()

            self.assertTrue(save_settings(settings, path))
            self.assertFalse(save_settings(settings, path))

            settings["lantern_brightness"] = 60
            self.assertTrue(save_settings(settings, path))
            with open(path, "r") as config_file:
                self.assertEqual(json.load(config_file)["lantern_brightness"], 60)


if __name__ == "__main__":
    unittest.main()