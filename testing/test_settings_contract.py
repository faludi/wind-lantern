import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from lantern_config import DEFAULT_SETTINGS, normalize_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYTHON_TYPES = {
    "int": int,
    "float": float,
    "string": str,
    "url": str,
}


def run_php(code, input_text=""):
    return subprocess.run(
        ["php", "-r", code],
        cwd=PROJECT_ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


@unittest.skipUnless(shutil.which("php"), "PHP CLI is required for cross-layer contract checks")
class SettingsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        output = run_php(
            'require "html/settings_schema.php"; '
            'echo json_encode(lantern_settings_schema());'
        )
        cls.schema = json.loads(output)

    def test_php_and_firmware_define_the_same_setting_keys_and_types(self):
        firmware_keys = set(DEFAULT_SETTINGS) - {"latitude", "longitude"}
        self.assertEqual(set(self.schema), firmware_keys)

        for key, field in self.schema.items():
            self.assertIsInstance(DEFAULT_SETTINGS[key], PYTHON_TYPES[field["type"]])

    def test_shared_numeric_defaults_and_bounds_match_firmware_and_sql(self):
        schema_sql = (PROJECT_ROOT / "html" / "schema.sql").read_text()
        for key, field in self.schema.items():
            if key != "address":
                self.assertEqual(field["default"], DEFAULT_SETTINGS[key], key)
            if "min" not in field:
                continue

            constraint = re.search(
                rf"^\s*{re.escape(key)}\s+.*?CHECK\s*\(\s*{re.escape(key)}\s+BETWEEN\s+(-?\d+)\s+AND\s+(-?\d+)\s*\)",
                schema_sql,
                re.IGNORECASE | re.MULTILINE,
            )
            self.assertIsNotNone(constraint, "Missing SQL range for " + key)
            self.assertEqual((int(constraint.group(1)), int(constraint.group(2))), (field["min"], field["max"]), key)

            normalized_min = normalize_settings({key: field["min"] - 1})[key]
            normalized_max = normalize_settings({key: field["max"] + 1})[key]
            self.assertEqual(normalized_min, field["min"], key)
            self.assertEqual(normalized_max, field["max"], key)

    def test_interval_ui_bounds_remain_narrower_than_server_bounds(self):
        interval = self.schema["settings_update_interval"]

        self.assertEqual((interval["ui_min"], interval["ui_max"]), (5, 180))
        self.assertEqual((interval["min"], interval["max"]), (1, 10080))

    def test_checkin_payload_uses_schema_keys_and_types(self):
        row = {}
        for key, field in self.schema.items():
            value = field["default"]
            if field["type"] == "float":
                value = "2.5"
            elif field["type"] == "int":
                value = str(value)
            row[key] = value

        code = (
            'require "html/settings_schema.php"; '
            '$row = json_decode(stream_get_contents(STDIN), true); '
            'echo json_encode(lantern_settings_payload($row));'
        )
        payload = json.loads(run_php(code, json.dumps(row)))

        self.assertEqual(set(payload), set(self.schema))
        for key, field in self.schema.items():
            self.assertIsInstance(payload[key], PYTHON_TYPES[field["type"]], key)
        self.assertEqual(payload["flicker_intensity"], 2.5)


if __name__ == "__main__":
    unittest.main()
