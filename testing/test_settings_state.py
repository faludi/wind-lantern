import unittest

from lantern_config import DEFAULT_SETTINGS
from settings_state import LanternSettings


class LanternSettingsTests(unittest.TestCase):
    def test_initial_state_uses_normalized_defaults(self):
        state = LanternSettings()

        self.assertEqual(state.snapshot(), DEFAULT_SETTINGS)

    def test_partial_update_preserves_other_settings(self):
        state = LanternSettings()

        state.apply({"lantern_brightness": "60"})

        self.assertEqual(state["lantern_brightness"], 60)
        self.assertEqual(state["night_brightness"], DEFAULT_SETTINGS["night_brightness"])

    def test_invalid_remote_values_keep_current_values(self):
        state = LanternSettings()
        state.apply({"night_brightness": 35, "night_start": 19})

        state.apply({"night_brightness": "invalid", "night_start": 21.5})

        self.assertEqual(state["night_brightness"], 35)
        self.assertEqual(state["night_start"], 19)

    def test_snapshot_is_independent_and_location_updates_are_scoped(self):
        state = LanternSettings()
        snapshot = state.snapshot()
        snapshot["address"] = "changed outside state"

        state.set_location(37.8, -122.4)

        self.assertEqual(state["address"], DEFAULT_SETTINGS["address"])
        self.assertEqual(state["latitude"], 37.8)
        self.assertEqual(state["longitude"], -122.4)


if __name__ == "__main__":
    unittest.main()