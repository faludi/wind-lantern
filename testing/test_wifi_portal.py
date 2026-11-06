import importlib.util
import sys
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode


module_path = Path(__file__).resolve().parents[1] / "nature_api.py"
spec = importlib.util.spec_from_file_location("portal_nature_api", module_path)
nature_api = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {name: types.ModuleType(name) for name in ("network", "machine", "ntptime", "requests")}):
    spec.loader.exec_module(nature_api)


class InputParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            self.inputs.append(dict(attrs))

    def handle_data(self, data):
        self.text.append(data)


class WifiPortalTests(unittest.TestCase):
    def setUp(self):
        self.client = nature_api.Client("", "")

    def render(self, ssids, hint=""):
        parser = InputParser()
        parser.feed(self.client._portal_form(ssids, "", hint, "MAC", "1"))
        return parser

    def test_lists_all_networks_and_preserves_retry_selection(self):
        ssids = ["Network %d" % index for index in range(5)] + ['Cafe & "Guest"']
        parser = self.render(ssids, ssids[-1])
        choices = [item for item in parser.inputs if item.get("name") == "network"]

        self.assertEqual([item["value"] for item in choices], ["0", "1", "2", "3", "4", "5", "other"])
        self.assertIn("checked", choices[5])
        self.assertIn(ssids[-1], [text.strip() for text in parser.text])
        self.assertEqual(nature_api._provisioning_ssid({"network": "5", "ssid": ""}, ssids), ssids[-1])

    def test_manual_entry_and_empty_scan(self):
        parser = self.render([], "Hidden network")
        choice = next(item for item in parser.inputs if item.get("name") == "network")
        manual = next(item for item in parser.inputs if item.get("name") == "ssid")

        self.assertEqual(choice["value"], "other")
        self.assertIn("checked", choice)
        self.assertEqual(manual["value"], "Hidden network")
        self.assertEqual(nature_api._provisioning_ssid({"network": "other", "ssid": "Hidden network"}, []), "Hidden network")
        self.assertEqual(nature_api._provisioning_ssid({"network": "99", "ssid": ""}, []), "")

    def test_other_network_is_inside_list_after_scanned_networks(self):
        html = self.client._portal_form(["First", "Second"], "", "", "MAC", "1")
        network_list = html.split('<div class="networks">', 1)[1].split('</div>', 1)[0]

        self.assertLess(network_list.index('value="1"'), network_list.index('value="other"'))
        self.assertIn('id="manual"', html)
        self.assertIn('updateNetwork();', html)

    def test_password_uses_native_existing_password_field(self):
        parser = self.render(["Network"])
        password = next(item for item in parser.inputs if item.get("id") == "wifi-key")

        self.assertIn("Network key", parser.text)
        self.assertEqual(password["type"], "password")
        self.assertEqual(password["name"], "wifi_key")
        self.assertEqual(password["autocomplete"], "current-password")
        self.assertEqual(len([item for item in parser.inputs if item.get("name") == "wifi_key"]), 1)

    def test_submitted_form_resolves_selected_and_manual_names(self):
        class FakeConnection:
            def __init__(self, data):
                self.data = data

            def recv(self, size):
                chunk, self.data = self.data[:size], self.data[size:]
                return chunk

        ssids = ['Cafe & "Guest"', "Second network"]
        for form, expected in (
            ({"network": "0", "ssid": "", "wifi_key": "password123"}, ssids[0]),
            ({"network": "other", "ssid": "Hidden & cafe", "wifi_key": "password123"}, "Hidden & cafe"),
        ):
            body = urlencode(form).encode()
            request = b"POST /save HTTP/1.1\r\nContent-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
            method, path, parsed = self.client._read_request(FakeConnection(request))
            self.assertEqual((method, path), ("POST", "/save"))
            self.assertEqual(nature_api._provisioning_ssid(parsed, ssids), expected)
            self.assertEqual(parsed["wifi_key"], "password123")


if __name__ == "__main__":
    unittest.main()