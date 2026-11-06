import ast
import importlib.util
import itertools
import json
import sys
import types
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock, patch
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

        self.assertIn("Passphrase", parser.text)
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

    def test_successful_connection_survives_lost_http_response(self):
        class FakeWlan:
            def __init__(self):
                self.enabled = False

            def active(self, value=None):
                if value is not None:
                    self.enabled = value
                return self.enabled

            def config(self, *args, **kwargs):
                return b"\x00\x01\x02\x03\x04\x05"

        station, access_point = FakeWlan(), FakeWlan()
        conn = Mock()
        http, dns = Mock(), Mock()
        http.accept.side_effect = itertools.chain([(conn, None)], itertools.repeat(OSError()))
        fake_socket = types.SimpleNamespace(
            socket=Mock(side_effect=[http, dns]), SOL_SOCKET=1, SO_REUSEADDR=2, AF_INET=3, SOCK_DGRAM=4
        )
        ticks = iter(range(0, 100000, 1000))
        fake_time = types.SimpleNamespace(
            ticks_ms=lambda: next(ticks), ticks_add=lambda value, delta: value + delta,
            ticks_diff=lambda end, start: end - start, sleep=lambda seconds: None, sleep_ms=lambda milliseconds: None
        )
        fake_network = types.SimpleNamespace(STA_IF=0, AP_IF=1, WLAN=lambda interface: station if interface == 0 else access_point)
        states = []
        with patch.object(nature_api, "network", fake_network), patch.object(nature_api, "socket", fake_socket), \
             patch.object(nature_api, "time", fake_time), patch.object(self.client, "_scan_ssids", return_value=["Home"]), \
             patch.object(self.client, "_serve_dns"), patch.object(self.client, "_try_sta_connect", return_value=True), \
             patch.object(self.client, "_read_request", return_value=("POST", "/save", {"network": "0", "wifi_key": "password123"})), \
             patch.object(self.client, "_send_http", side_effect=OSError("connection lost")):
            result = self.client.provision_wifi(timeout=5, on_status=states.append)

        self.assertEqual(result, ("Home", "password123"))
        self.assertIn("success", states)


class ProvisioningFlowTests(unittest.TestCase):
    def run_flow(self, requests, outcomes, save=None, max_attempts=2, lose_response=False, timeout=60):
        events = []

        class FakeWlan:
            def __init__(self):
                self.enabled = False

            def active(self, value=None):
                if value is not None:
                    self.enabled = value
                return self.enabled

            def config(self, *args, **kwargs):
                return b"\x00\x01\x02\x03\x04\x05"

        class FakeConnection:
            def __init__(self, request, fail_write=False):
                self.request = request
                self.fail_write = fail_write
                self.response = None

            def settimeout(self, value):
                pass

            def sendall(self, payload):
                events.append("response:" + self.request[1])
                if self.fail_write:
                    raise OSError("connection lost")
                self.response = payload

            def close(self):
                pass

        connections = [FakeConnection(request, lose_response and index == 0) for index, request in enumerate(requests)]
        pending_connections = iter(connections)
        http, dns = Mock(), Mock()

        def accept():
            connection = next(pending_connections, None)
            if connection is None:
                raise OSError("no connection")
            return connection, None

        http.accept.side_effect = accept
        station, access_point = FakeWlan(), FakeWlan()
        fake_socket = types.SimpleNamespace(
            socket=Mock(side_effect=[http, dns]), SOL_SOCKET=1, SO_REUSEADDR=2, AF_INET=3, SOCK_DGRAM=4
        )
        ticks = itertools.count(step=250)
        fake_time = types.SimpleNamespace(
            ticks_ms=lambda: next(ticks), ticks_add=lambda value, delta: value + delta,
            ticks_diff=lambda end, start: end - start, sleep=lambda seconds: None, sleep_ms=lambda milliseconds: None
        )
        fake_network = types.SimpleNamespace(STA_IF=0, AP_IF=1, WLAN=lambda interface: station if interface == 0 else access_point)
        client = nature_api.Client("", "")
        results = iter(outcomes)

        def connect(*args):
            events.append("join")
            return next(results)

        def on_connected(ssid, password):
            events.append("save")
            if save:
                save(ssid, password)

        with patch.object(nature_api, "network", fake_network), patch.object(nature_api, "socket", fake_socket), \
             patch.object(nature_api, "time", fake_time), patch.object(client, "_scan_ssids", return_value=["Home"]), \
             patch.object(client, "_serve_dns"), patch.object(client, "_try_sta_connect", side_effect=connect), \
             patch.object(client, "_read_request", side_effect=lambda connection: connection.request):
            try:
                result = client.provision_wifi(timeout=timeout, max_attempts=max_attempts,
                                               on_connected=on_connected, on_status=events.append)
            except nature_api.WifiProvisioningError as exc:
                result = exc
        return result, connections, events, access_point

    def test_success_is_saved_before_reporting_and_waits_for_done(self):
        requests = [
            ("POST", "/save", {"network": "0", "wifi_key": "password123"}),
            ("GET", "/status", {}),
            ("POST", "/finish", {}),
        ]
        result, connections, events, access_point = self.run_flow(requests, [True])

        self.assertEqual(result, ("Home", "password123"))
        self.assertIn(b"Connecting to the network", connections[0].response)
        self.assertLess(events.index("response:/save"), events.index("join"))
        self.assertLess(events.index("save"), events.index("success"))
        status = json.loads(connections[1].response.split(b"\r\n\r\n", 1)[1])
        self.assertEqual((status["state"], status["ssid"]), ("success", "Home"))
        self.assertIn(b"Setup complete", connections[2].response)
        self.assertFalse(access_point.enabled)

    def test_disconnected_submit_still_saves_and_times_out_successfully(self):
        requests = [("POST", "/save", {"network": "0", "wifi_key": "password123"})]
        result, _, events, access_point = self.run_flow(requests, [True], lose_response=True)

        self.assertEqual(result, ("Home", "password123"))
        self.assertLess(events.index("save"), events.index("success"))
        self.assertFalse(access_point.enabled)

    def test_submission_accepted_before_timeout_is_processed(self):
        requests = [("POST", "/save", {"network": "0", "wifi_key": "password123"})]
        result, _, events, _ = self.run_flow(requests, [True], timeout=0.5)

        self.assertEqual(result, ("Home", "password123"))
        self.assertIn("save", events)

    def test_save_failure_is_reported_and_can_be_retried(self):
        def save(ssid, password):
            if not saved:
                saved.append(False)
                raise OSError("disk error")
            saved.append(True)

        saved = []
        submit = ("POST", "/save", {"network": "0", "wifi_key": "password123"})
        requests = [submit, ("GET", "/status", {}), submit, ("GET", "/status-page", {}), ("POST", "/finish", {})]
        result, connections, events, _ = self.run_flow(requests, [True, True], save=save)

        self.assertEqual(result, ("Home", "password123"))
        failure = json.loads(connections[1].response.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(failure["state"], "failed")
        self.assertIn("Could not save", failure["error"])
        self.assertIn(b"Connected", connections[3].response)
        self.assertEqual(saved, [False, True])
        self.assertEqual(events.count("success"), 1)

    def test_failed_connection_is_visible_before_setup_ends(self):
        requests = [("POST", "/save", {"network": "0", "wifi_key": "password123"}), ("GET", "/status", {})]
        result, connections, events, _ = self.run_flow(requests, [False], max_attempts=1)

        self.assertIsInstance(result, nature_api.WifiConnectError)
        failure = json.loads(connections[1].response.split(b"\r\n\r\n", 1)[1])
        self.assertEqual(failure["state"], "ended")
        self.assertNotIn("save", events)
        self.assertNotIn("success", events)

    def test_no_script_success_page_escapes_network_name(self):
        requests = [
            ("POST", "/save", {"network": "other", "ssid": '<Home & "Guest">', "wifi_key": "password123"}),
            ("GET", "/status-page", {}),
            ("POST", "/finish", {}),
        ]
        result, connections, _, _ = self.run_flow(requests, [True])

        self.assertEqual(result[0], '<Home & "Guest">')
        self.assertIn(b'&lt;Home &amp; &quot;Guest&quot;&gt;', connections[1].response)
        self.assertIn(b'action="/finish"', connections[1].response)

    def test_main_saves_during_provisioning_before_return(self):
        main_path = module_path.parent / "main.py"
        module = ast.parse(main_path.read_text())
        setup = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == "run_wifi_setup")
        save = Mock()

        def provision(**kwargs):
            kwargs["on_connected"]("Home", "password123")
            return "Home", "password123"

        reset = Mock()
        namespace = {
            "nature_client": types.SimpleNamespace(provision_wifi=provision),
            "get_lantern_mac": lambda: "ABCDEF12", "SETUP_AP_TIMEOUT_SECONDS": 600,
            "SETUP_AP_MAX_ATTEMPTS": 10, "setup_status_led": Mock(), "save_wifi_credentials": save,
            "version": "test", "clear_reboot_backoff": Mock(), "reset": reset,
        }
        exec(compile(ast.Module(body=[setup], type_ignores=[]), str(main_path), "exec"), namespace)
        namespace["run_wifi_setup"]()

        save.assert_called_once_with("Home", "password123")
        reset.assert_called_once()


if __name__ == "__main__":
    unittest.main()